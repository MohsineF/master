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

process_state = ['STOPPED', 'RUNNING', 'EXITED', 'STOPPING' ,'FATAL', 'UNKNOWN']

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

END = 'DAEMON COPY'

SOCKFILE = '/tmp/taskmaster.sock'

LOGFILE = 'tmp/taskmaster.log'

class ServerSocket():
    def __init__(self):
        self.sock_address = SOCKFILE
        try:
            os.remove(self.sock_address)
        except OSError:
            pass
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection = None
        self.address = None
        self.socket.bind(self.sock_address)
        self.socket.listen(1)
        self.accept()
    def accept(self):
        try:
            self.connection, self.address = self.socket.accept()
        except socket.error as err:
            if err == errno.EINTR:
                pass
    def send(self, msg):
        try:
            length = struct.pack('!I', len(msg))
            self.connection.sendall(length)
            self.connection.sendall(msg.encode())
        except (OSError ,socket.error) as err:
            if err == errno.EINTR:
                pass
            sys.exit()    
    def recv(self):
        try:
            n = self.connection.recv(4)
            if not n: return None
        except (OSError, socket.error, AttributeError) as err:
            pass
            return None
        length, = struct.unpack('!I', n)
        message = self.connection.recv(length)
        return message.decode()
    def close_connection(self):
        if self.connection is not None:
            self.connection.close()
    def close_socket(self):
        if self.socket is not None:
            self.socket.close()

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
        self.autostart =  True
        self.autorestart =  'unexpected'
        self.exitcodes = 0
        self.stopsignal = 'SIGTERM'
        self.stopwaitsecs = 10
        self.environment = ''
        self.umask = '022'
        self.directory = './'
        self.stdout = '/tmp/stdout_logfile.log'
        self.stderr = '/tmp/stderr_logfile.log'
        self.description = str()
    def start(self):
        child = os.fork()
        if child == 0:
            os.chdir(self.directory)
            self._redirect()
            cmd = self.command.split(' ')
            os.execv(cmd[0], cmd)
        elif child > 0:
            self.startime = time.time()
            self.pid = child
            state_handler(self, 'RUNNING')
    def stop(self):
        state_handler(self, 'STOPPING')
        print(stop_signals[self.stopsignal])
        os.kill(self.pid, stop_signals[self.stopsignal])
    def restart(self):
        if self.state == 'RUNNING':
            self.stop()
        if self.state == 'STOPPING':
            self.pid, self.exitcode = os.waitpid(self.pid, 0)
            print(self.pid, self.exitcode)
            state_handler(self, 'STOPPED')
        self.start()
    def _redirect(self):
        stdout_fd = os.open(self.stdout, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        stderr_fd = os.open(self.stderr, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)


def state_handler(proc, state):
        if state == 'EXITED':
            exitime = time.time()
            exec_time = exitime - proc.startime
            if proc.startretries and exec_time < int(proc.startsecs):        
                proc.startretries = int(proc.startretries) - 1
                proc.start()
            elif not proc.startretries and exec_time < int(proc.startsecs):  
                proc.state = 'FATAL'
                proc.description = 'Process could not be started successfully'
            else:     
                proc.state = state
                proc.description = 'Process exited after: ' + str(int(exec_time)) + ' seconds'
                if proc.autorestart == 'true':
                    proc.start()
                elif proc.autorestart == 'unexpected' and proc.exitcode not in list(proc.exitcodes.replace(',', '')):
                    proc.start()
        elif state == 'STOPPED':
            if proc.state == 'STOPPING':
                proc.state = state
                proc.description = 'Process stopped with ' + proc.stopsignal + ' signal'
        elif state == 'RUNNING':
            proc.state = state
            proc.description = 'Process spawned with pid: ' + str(proc.pid) 
        elif state == 'STOPPING':
            proc.state = state
            proc.description = 'Process stopping ' + proc.stopsignal + ' signal' 


def daemon_proc():
    child = os.fork()
    if child == 0:
        print('Daemon PID:', os.getpid())
        set_signals()
        spawn_processes()
        daemon = ServerSocket()
        daemon_ear(daemon) 

def daemon_ear(daemon):
    while True:
        request = daemon.recv()
        if request == None:
            daemon.close_connection()
            daemon.accept()
            continue 
        request = list(request.split(' '))
        request_handling(daemon, request)

def set_signals():
    signal.signal(signal.SIGCHLD, sig_handler)


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
            print(pid)
            for proc in processes.values():
                if proc.pid == pid:
                    proc.exitcode = exitcode
                    if proc.state == 'STOPPING':
                        state_handler(proc,'STOPPED')
                    else:
                        state_handler(proc, 'EXITED')


def request_handling(daemon, request):
    if len(request) == 2 and request[1] not in processes.keys():
        daemon.send('No such program name ! type "status"')
    elif request[0] == 'status':
        for proc in processes.values():
            daemon.send(proc.name  + '  '  + proc.state + '   ' + proc.description) 
        daemon.send(END)
    elif request[0] == 'start':
        if processes[request[1]].state != 'RUNNING':
            daemon.send('Starting program...')
            processes[request[1]].start()
        else:
            daemon.send('Program already Running !')
    elif request[0] == 'stop':
        if processes[request[1]].state == 'RUNNING':
            daemon.send('Stopping program...')
            processes[request[1]].stop()
        else:
            daemon.send('Program not running !')
    elif request[0] == 'restart':
        daemon.send('Restarting program: ' + request[1])
        processes[request[1]].restart()
    elif request[0] == 'pid':
        daemon.send(str(os.getpid()))
    elif request[0] == 'quit':
        daemon.send('Killing child processes...')
        for proc in processes.values():
            if proc.state == 'RUNNING':
                os.kill(proc.pid, signal.SIGKILL) 
        daemon.send('DOne!')
        sys.exit()


def spawn_processes():
    for proc in processes.values():
        if proc.autostart == 'true':
            proc.start()


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


def config_checkr(configfile):
    pattern = re.compile('program:')
    sections = configfile.sections() 
    for section in sections:
        if not pattern.match(section):
            print('Forbidden section naming format! [', section, ']')
            return (0)                                 #'Error: Forbidden section name'
    for section in sections:
        options = configfile.options(section)
        for option in options:
            if option not in options_sample:
                print('Option Not Allowed : [', option, '] in [', section , '] section !' )
                return (0)                              #'Error: Option not allowed'
    return (1)


def main():
    configfile = configparser.ConfigParser()
    configfile.read('./taskmaster.conf')

    if not config_checkr(configfile):
        sys.exit()

    processes_obj(configfile)
    daemon_proc()


if __name__ == "__main__":
    main()




