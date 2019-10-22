#!/usr/bin/python3

import os
import configparser
import re
import time
import signal
import socket
import struct
import sys
import errno
from tasksocket import *
from tasklog import tasklog

CONFIGFILE = './taskmaster.conf'

process_state = ['STOPPED', 'RUNNING', 'EXITED', 'STOPPING' ,'FATAL']

options_sample = [
        'command',
        'numprocs',
        'autostart',
        'autorestart',
        'exitcodes',
        'startsecs',
        'startretries',
        'stopsignal',
        'stopwaitsecs',
        'environment',
        'umask',
        'stdout',
        'stderr',
        'directory'
        ]

stop_signals = {
        'SIGTERM': 15,
        'SIGHUP': 1,
        'SIGINT': 2,
        'SIGQUIT': 3,
        'SIGKILL': 9,
        'SIGUSR1': 30,
        'SIGUSR2': 31
        }

processes = dict()


class Process():
    def __init__(self, name):
        self.name = name
        self.command = None
        self.state = 'STOPPED'
        self.pid = None
        self.startime = None
        self.exitcode = None
        self.numprocs =  1
        self.startsecs = 3
        self.startretries = 3
        self.autostart =  'true'
        self.autorestart =  'unexpected'
        self.exitcodes = 0
        self.stopsignal = 'SIGTERM'
        self.stopwaitsecs = 10
        self.environment = ''
        self.umask = '022'
        self.directory = './'
        self.stdout = '/tmp/stdout_logfile.log'
        self.stderr = '/tmp/stderr_logfile.log'
        self.description = 'Program not started yet !'
        self.retries_counter = 0
        self.stopwait_counter = 0
    def start(self):
        child = os.fork()
        if child == 0:
            os.chdir(self.directory)
            os.umask(int(self.umask))
            self._env()
            self._redirect()
            cmd = self.command.split(' ')
            try:
                os.execv(cmd[0], cmd)
            except FileNotFoundError as err:
                sys.stderr.write("No such command !\n")
                sys.exit()
        elif child > 0:
            self.startime = time.time()
            self.pid = child
            if self.state != 'RUNNING': 
                self.retries_counter = 0
            state_handler(self, 'RUNNING')
    def stop(self):                                            
        state_handler(self, 'STOPPING')                        
        os.kill(self.pid, stop_signals[self.stopsignal])        
        time.sleep(float(self.stopwaitsecs))
        if self.state == 'STOPPING':
            tasklog('KILL', self.name)
            os.kill(self.pid, stop_signals['SIGKILL'])
    def _redirect(self):
        try:
            if self.stdout == 'NONE':
                os.close(1)
            else:
                stdout_fd = os.open(self.stdout, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
                os.dup2(stdout_fd, 1)
        except OSError as err:
            if err.errno == errno.EACCES:
                tasklog('EACCES', 'configfile')
                os.close(1)
        try:
            if self.stderr == 'NONE':
                os.close(2)
            else:
                stderr_fd = os.open(self.stderr, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
                os.dup2(stderr_fd, 2)
        except OSError as err:
            if err.errno == errno.EACCES:
                tasklog('EACCES','configfile')
                os.close(2)
    def _env(self):
        env = self.environment.split(',')
        if env[0]:
            for var in env:
                pair = var.split('=')
                os.environ[pair[0]] = pair[1].replace("\"", "")


def daemon_proc():
    child = os.fork()
    if child == 0:
        print('Daemon PID:', os.getpid())
        tasklog('DAEMON', 'taskmasterd')
        set_signals()
        spawn_processes()
        daemon = ServerSocket()
        daemon_ear(daemon) 


def daemon_ear(daemon):
    while True:
        request = daemon.recv()
        if request == None:
            continue
        request = list(request.split(' '))
        request_handler(daemon, request)


def set_signals():
    signal.signal(signal.SIGCHLD, sig_handler)
    signal.signal(signal.SIGHUP, sig_handler)


def sig_handler(sig, frame):
    if sig == signal.SIGCHLD:
        while True:
            try:
                status = os.waitpid(-1, os.WNOHANG)
            except:
                break
            if status[0] <= 0:
                break
            pid = status[0]
            exitcode = status[1]
            for proc in processes.values():
                if proc.pid == pid:
                    proc.exitcode = exitcode
                    if proc.state == 'STOPPING':
                        state_handler(proc,'STOPPED')
                    else:
                        state_handler(proc, 'EXITED')
    elif sig == signal.SIGHUP:
        kill_processes()
        if setup_config():
            spawn_processes()
        else:
            sys.exit()

def state_handler(proc, state):
    if state == 'EXITED':
        exitime = time.time()
        exec_time = exitime - proc.startime
        if proc.retries_counter < int(proc.startretries) and exec_time < int(proc.startsecs):
            tasklog('BACKOFF', proc.name)
            proc.retries_counter += 1
            proc.start()
        elif proc.retries_counter == int(proc.startretries) and exec_time < int(proc.startsecs):
            tasklog('FATAL', proc.name)
            proc.state = 'FATAL'
            proc.description = 'Process could not be started successfully'
        else:     
            tasklog('EXIT', proc.name)
            proc.state = state
            proc.description = 'Process exited after: ' + str(int(exec_time)) + ' seconds'
            if proc.autorestart == 'true':
                proc.start()
            elif proc.autorestart == 'unexpected' and proc.exitcode not in list(proc.exitcodes.replace(',', '')):
                proc.start()
    elif state == 'STOPPED':
        tasklog('STOP', proc.name)
        proc.state = state
        proc.description = 'Process stopped after a stop request'
    elif state == 'RUNNING':
        tasklog('SPAWN', proc.name)
        proc.state = state
        proc.description = 'Process spawned with pid: ' + str(proc.pid)
    elif state == 'STOPPING':
        tasklog('WAITSTOP', proc.name)
        proc.state = state
        proc.description = 'Process stopping with a signal' 


def request_handler(daemon, request):
    if len(request) == 2 and request[1] not in processes.keys():
        daemon.send('No such program name ! type "status"')
    elif request[0] == 'status':
        status_request(daemon)
    elif request[0] == 'start':
        start_request(daemon, request)
    elif request[0] == 'stop':
        stop_request(daemon, request)
    elif request[0] == 'restart':
        restart_request(daemon, request)
    elif request[0] == 'reload':
        reload_request(daemon)
    elif request[0] == 'pid':
        daemon.send(str(os.getpid()))
    elif request[0] == 'exit':
        daemon.close_connection()
    elif request[0] == 'quit':
        quit_request(daemon)


def status_request(daemon):
    for proc in processes.values():
        daemon.send(proc.name  + '  '  + proc.state + '   ' + proc.description) 
    daemon.send(END)

def start_request(daemon, request):
    if processes[request[1]].state != 'RUNNING':
        daemon.send('Starting program...')
        processes[request[1]].start()
    else:
        daemon.send('Program already Running !')

def stop_request(daemon, request):
    if processes[request[1]].state == 'RUNNING':
        daemon.send('Stopping program gracefully...(or killing it !)')
        processes[request[1]].stop()
        daemon.send('Program stopped !')
    else:
        daemon.send('Program not running !')

def restart_request(daemon, request):
    daemon.send('Restarting program...')
    if processes[request[1]].state == 'RUNNING':
        processes[request[1]].stop()
    processes[request[1]].start()
    daemon.send('Program started !')


def reload_request(daemon):
    kill_processes()
    if setup_config():
        spawn_processes()
        daemon.send('Programs reloaded !') 
    else:
        daemon.send('Configfile Error !(Check logfile: /tmp/taskmaster.log)') 
        sys.exit()


def quit_request(daemon):
    daemon.send('Killing child processes...')
    kill_processes()
    tasklog('QUIT', 'taskmasterd')
    daemon.send('DOne!')
    daemon.close_socket()
    sys.exit()


def spawn_processes():
    for proc in processes.values():
        if proc.autostart == 'true':
            proc.start()


def kill_processes():
    for proc in processes.values():
        if proc.state == 'RUNNING' or proc.state == 'STOPPING':
            proc.stop()
    processes.clear()


def processes_obj(configfile):
    sections = configfile.sections()
    for section in sections:
        try:
            num_procs = int(configfile.get(section, 'numprocs'))
        except:
            num_procs = 1
            pass
        proc_name = section.split(':')[1]
        for i in range(num_procs):
            name = proc_name
            if num_procs > 1:
                name += ':' + str(i)
            processes[name] = Process(name) 
            for option in configfile.options(section):
                setattr(processes[name], option, configfile.get(section, option))


def config_checkr():
    configfile = configparser.RawConfigParser()
    conf = configfile.read(CONFIGFILE)
    if not conf:
        tasklog('CONFIG', 'config')
        return (0)
    pattern = re.compile('program:')
    sections = configfile.sections() 
    for section in sections:
        if not pattern.match(section):
            tasklog('SECTION', 'config')
            return (0)                                
    for section in sections:
        options = configfile.options(section)
        for option in options:
            if option not in options_sample:
                tasklog('OPTION', 'config')
                return (0)                              
    return (configfile)


def setup_config():
    configfile = config_checkr()
    if not configfile:
        return (0)
    processes_obj(configfile)
    return (1)


def main():
    if setup_config(): 
        daemon_proc()
    else:
        print('Configfile Error !(Check logfile: /tmp/taskmaster.log)')


if __name__ == "__main__":
    main()


