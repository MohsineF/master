#!/usr/bin/python3

import os
import configparser
import re
import time
import signal
import socket
import struct
import copy
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

# Main Class

class Process():
    def __init__(self, name):
        self.title = str()
        self.name = name
        self.command = str()
        self.numprocs =  1
        self.startsecs = 1
        self.startretries = 3
        self.autostart =  'true'
        self.autorestart =  'unexpected'
        self.exitcodes = '0'
        self.stopsignal = 'SIGTERM'
        self.stopwaitsecs = 10
        self.environment = str()
        self.umask = '022'
        self.directory = './'
        self.stdout = '/tmp/task_stdout.log'
        self.stderr = '/tmp/task_stderr.log'
        self.pid = int()
        self.state = 'STOPPED'
        self.description = 'Program not started yet !'
        self.retries_counter = 0
        self.startime = float()
        self.exit = int()
    def __eq__(self, other):
        return (self.name == other.name and self.command == other.command and self.numprocs == other.numprocs
        and self.startsecs == other.startsecs and self.startretries == other.startretries
        and self.autostart == other.autostart and self.autorestart == other.autorestart and self.exitcodes == other.exitcodes
        and self.stopsignal == other.stopsignal and self.stopwaitsecs == other.stopwaitsecs
        and self.environment == other.environment and  self.umask == other.umask and self.directory == other.directory
        and self.stdout == other.stdout and self.stderr == other.stderr)
    def start(self): 
        self.startime = time.time()
        try:
            self.pid = os.fork()
        except BlockingIOError as err:
            pass
        if self.pid == 0:
            self._env()
            self._redirect()
            os.umask(int(self.umask))
            try:
                os.chdir(self.directory)
            except FileNotFoundError:
                sys.stderr.write(self.name + ":" + self.directory + " : Directory name Not Found!\n")
            cmd = self.command.split(' ')
            try:
                time.sleep(1)
                os.execv(cmd[0], cmd)
            except FileNotFoundError:
                sys.stderr.write(self.name + ":" + self.command + " : Program name Not Found!\n")
                sys.exit(127)
        elif self.pid > 0:
            if self.state != 'RUNNING': 
                self.retries_counter = 0
            state_handler(self, 'RUNNING')
    def stop(self):                                            
        state_handler(self, 'STOPPING')
        try:
            os.kill(self.pid, stop_signals[self.stopsignal])        
            time.sleep(float(self.stopwaitsecs))
            if self.state == 'STOPPING':
                tasklog('KILL', self.name, '')
                os.kill(self.pid, stop_signals['SIGKILL'])
            else:
                tasklog('STOP', self.name, self.stopsignal)
        except ProcessLookupError:
            pass
    def _redirect(self):
        try:
            if self.stdout == 'NONE':
                os.close(1)
            else:
                stdout_fd = os.open(self.stdout, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
                os.dup2(stdout_fd, 1)
        except OSError as err:
            if err.errno == errno.EACCES:
                tasklog('EACCES', 'configfile', '')
                os.dup2(os.open("/dev/null", os.O_WRONLY), 1)
        try:
            if self.stderr == 'NONE':
                os.close(2)
            else:
                stderr_fd = os.open(self.stderr, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
                os.dup2(stderr_fd, 2)
        except OSError as err:
            if err.errno == errno.EACCES:
                tasklog('EACCES','configfile', '')
                os.dup2(os.open("/dev/null", os.O_WRONLY), 2)
    def _env(self):
        env = self.environment.split(',')
        if env[0]:
            for var in env:
                pair = var.split(':')
                os.environ[pair[0]] = pair[1].replace("\"", "")


# Signals Handling

def set_signals():
    signal.signal(signal.SIGCHLD, sig_handler)
    signal.signal(signal.SIGHUP, sig_handler)


def sig_handler(sig, frame):
    if sig == signal.SIGCHLD:
        while True:
            try:
                status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError as err:
                break
            if status[0] <= 0:
                break
            pid = status[0]
            exitcode = os.WEXITSTATUS(status[1])
            for proc in processes.values():
                if proc.pid == pid:
                    proc.exit = exitcode
                    if proc.state == 'STOPPING':
                        state_handler(proc,'STOPPED')
                    else:
                        state_handler(proc, 'EXITED')
    elif sig == signal.SIGHUP:  #reload 
        reload_request()
       

# Process state handling

def state_handler(proc, state):
    if state == 'EXITED':
        exec_time = int(time.time() - proc.startime) - 1
        if proc.retries_counter < int(proc.startretries) and int(exec_time) < int(proc.startsecs):
            tasklog('BACKOFF', proc.name, str(proc.exit))
            proc.retries_counter += 1
            proc.start()
        elif proc.retries_counter == int(proc.startretries) and int(exec_time) < int(proc.startsecs):
            tasklog('FATAL', proc.name, '')
            proc.state = 'FATAL'
            proc.description = 'Process could not be started successfully'
        else:     
            tasklog('EXIT', proc.name, str(proc.exit))
            proc.state = 'EXITED'
            proc.description = 'Process exited after: ' + str(int(exec_time)) + ' seconds'
            if proc.autorestart == 'true':
                proc.start()
            elif proc.autorestart == 'unexpected' and str(proc.exit) not in list(proc.exitcodes.split(',')):
                proc.start()
    elif state == 'STOPPED':
        proc.state = state
        proc.description = 'Process stopped after a stop request'
    elif state == 'RUNNING':
        tasklog('SPAWN', proc.name, str(proc.pid))
        proc.state = state
        proc.description = 'Process spawned with pid: ' + str(proc.pid)
    elif state == 'STOPPING':
        tasklog('WAITSTOP', proc.name, proc.stopsignal)
        proc.state = state
        proc.description = 'Process stopping with a signal'


# Command requests Handling

def request_handler(daemon, request):
    if len(request) == 2 and request[1] not in processes.keys():
        daemon.send('No such program name ! type "status"')
    elif request[0] == 'status':
        status_request(daemon)
    elif request[0] == 'start':
        start_request(daemon, request[1])
    elif request[0] == 'stop':
        stop_request(daemon, request[1])
    elif request[0] == 'restart':
        restart_request(daemon, request[1])
    elif request[0] == 'reload':
        daemon.send('Reloading programs...')
        reload_request()
        daemon.send('Programs reloaded !') 
    elif request[0] == 'pid':
        daemon.send(str(os.getpid()))
    elif request[0] == 'exit':
        daemon.close_connection()
    elif request[0] == 'quit':
        quit_request(daemon)
    daemon.send(END)

def status_request(daemon):
    for proc in processes.values():
        daemon.send(proc.name  + '  '  + proc.state + '   ' + proc.description) 

def start_request(daemon, name):
    if processes[name].state != 'RUNNING':
        daemon.send('Starting program...')
        processes[name].start()
        daemon.send('Program started !')
    else:
        daemon.send('Program already Running !')

def stop_request(daemon, name):
    if processes[name].state == 'RUNNING':
        daemon.send('Stopping program gracefully...(or killing it !)')
        processes[name].stop()
        daemon.send('Program stopped !')
    else:
        daemon.send('Program not running !')

def restart_request(daemon, name):
    daemon.send('Restarting program...')
    if processes[name].state == 'RUNNING':
        processes[name].stop()
    processes[name].start()
    daemon.send('Program started !')

def reload_request():
    tasklog('RELOAD', 'taskmasterd', '')
    configfile = config_checkr()
    if not configfile:
        kill_processes()
        sys.exit()
    objc = create_processes(configfile)
    unchanged_run_procs = [proc.name for proc in processes.values() for obj in objc.values() if obj.title == proc.title and obj == proc and proc.state == 'RUNNING']
    deleted_procs = [proc.name for proc in processes.values() if proc.name not in unchanged_run_procs] #changed programs should get deleted
    for name in deleted_procs:
        if processes[name].state == 'RUNNING':
            processes[name].stop()
        del processes[name]
    for new in objc.values():
        if new.name not in unchanged_run_procs:
            processes[new.name] = copy.deepcopy(new)
            if processes[new.name].autostart == 'true':
                processes[new.name].start()

def quit_request(daemon):
    daemon.send('Killing child processes...')
    kill_processes()
    tasklog('QUIT', 'taskmasterd', '')
    daemon.send('DOne!')
    daemon.close_socket()
    sys.exit()


# Daemon process

def daemon_proc():
    child = os.fork()
    if child == 0:
        print('Daemon PID:', os.getpid())
        tasklog('DAEMON', 'taskmasterd', str(os.getpid()))
        os.setsid()
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


# Processes main commands START/KILL

def spawn_processes():
    for proc in processes.values():
        if proc.autostart == 'true':
            proc.start()


def kill_processes():
    for proc in processes.values():
        if proc.state == 'RUNNING':
            proc.stop()
    processes.clear()


# Configuration file source

def create_processes(configfile):
    proc_obj = dict()
    sections = configfile.sections()
    for section in sections:
        proc_name = section.split(':')[1]
        try:
            num_procs = int(configfile.get(section, 'numprocs'))
        except:
            num_procs = 1
        for i in range(num_procs):
            name = proc_name
            if num_procs > 1:
                name += ':' + str(i)
            proc_obj[name] = Process(name) 
            proc_obj[name].title = proc_name
            for option in configfile.options(section):
                setattr(proc_obj[name], option, configfile.get(section, option))
    return (copy.deepcopy(proc_obj))


def option_value(config, section, option):
    if option in ['numprocs', 'startsecs', 'startretries', 'stopwaitsecs', 'umask']:
        try:
            config.getint(section, option)
        except:
            return (0)
    elif option == 'stopsignal' and config.get(section, option) not in stop_signals.keys():
        return (0)    
    elif option in ['autorestart', 'autostart'] and config.get(section, option) not in ['true', 'false', 'unexpected']:
        return (0)
    return (1) 


def config_checkr():
    configfile = configparser.RawConfigParser()
    conf = configfile.read(CONFIGFILE)
    if not conf:
        tasklog('CONFIG', 'config', '')
        return (0)
    pattern = re.compile('program:')
    sections = configfile.sections() 
    for section in sections:
        if not pattern.match(section):
            tasklog('SECTION', 'config', '')
            return (0) 
        options = configfile.options(section)
        for option in options:            
            if option not in options_sample or not option_value(configfile, section, option):
                tasklog('OPTION', 'config', '')
                return (0)
    return (configfile)


def main():
    global processes
    configfile = config_checkr()
    if  configfile:
        processes = create_processes(configfile)
        daemon_proc()

if __name__ == "__main__":
    main()
