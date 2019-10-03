#!/usr/bin/python3

import os
import configparser
import re
import time
import signal
import socket
import struct
import sys

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

stop_signal = ['TERM', 'HUP', 'INT', 'QUIT', 'KILL', 'USR1', 'SIGUSR2']

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
        self.connection, self.address = self.socket.accept()
    def send(self, msg):
        try:
            length = struct.pack('!I', len(msg))
            self.connection.sendall(length)
            self.connection.sendall(msg.encode())
        except OSError as err:
            sys.exit()    
    def recv(self):
        n = self.connection.recv(4)
        if not n: return None
        length, = struct.unpack('!I', n)
        message = self.connection.recv(length)
        return message.decode()
    def close_connection(self):
        self.connection.close()
    def close_socket(self):
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
        self.stopsignal = 'TERM'
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
            self.description = 'Process spawned with pid: ' + str(self.pid)
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
                proc.state = 'EXITED'
                proc.description = 'Process exited after: ' + str(int(exec_time)) + ' seconds'
                if proc.autorestart == 'true':
                    proc.start()
                if proc.autorestart == 'unexpected' and proc.exitcode not in list(proc.exitcodes.replace(',', '')):
                    proc.start()
        else:
            proc.state = state


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
        if request == 'status':
            for proc in processes.values():
                daemon.send(proc.name  + '  '  + proc.state + '   ' + proc.description) 
            daemon.send(END)
        elif request == 'pid':
            daemon.send(str(os.getpid()))
        elif request == 'quit':
            daemon.send('Killing child processes...')
            for proc in processes.values():
                if proc.state == 'RUNNING':
                    os.kill(proc.pid, signal.SIGINT) 
            daemon.send('DOne!')
            sys.exit()


def set_signals():
    signal.signal(signal.SIGCHLD, sig_handler)
    signal.siginterrupt(signal.SIGCHLD, False)


def sig_handler(sig, frame):
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
                state_handler(proc, 'EXITED')


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




