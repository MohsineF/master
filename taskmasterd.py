#!/usr/bin/python3

import os
import configparser
import re
import time
import signal
import socket
import struct 


process_state = ['STOPPED', 'STARTING', 'RUNNING', 'BACKOFF', 'STOPPING', 'EXITED', 'FATAL', 'UNKNOWN']

options_sample = {
        'command': '',
        'numprocs': 1,
        'autostart': 'true',
        'autorestart': 'unexpected',
        'exitcodes': '0',
        'startsecs': 1,
        'startretries': 3,
        'stopsignal': 'TERM',
        'stopwaitsecs': 10,
        'environment': '',
        'umask': '022',
        'stdout_logfile': '/tmp/stdout_logfile.log',
        'stderr_logfile': '/tmp/stderr_logfile.log',
        }

processes = dict()

END = 'DAEMON COPY'


class ServerSocket():
    def __init__(self):
        self.sock_address = "/tmp/sockd"
        try:
            os.remove(self.sock_address)
        except OSError:
            pass
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection = None
        self.address = None
        self.socket.bind(self.sock_address)
        self.socket.listen(1)
        self.connection, self.address = self.socket.accept()
    def close(self):
        self.socket.close()
    def send(self, msg):
        length = struct.pack('!I', len(msg))
        self.connection.sendall(length)
        self.connection.sendall(msg.encode())
    def recv(self):
        n = self.connection.recv(4)
        if not n: return None
        length, = struct.unpack('!I', n)
        message = self.connection.recv(length)
        return message.decode()

class Process():
    def __init__(self, name):
        self.name = name
        self.options = dict(options_sample)
        self.state = 'STOPPED'
        self.pid = None
        self.exitcode = -1
    def start(self):
        child = os.fork()
        if child == 0:
            #self._redirect()
            signal.alarm(int(self.options['startsecs']))
            cmd = self.options['command'].split(' ')
            os.execv(cmd[0], cmd)
        elif child > 0:
            self.state = 'STARTING'
            self.pid = child
    def change_state(self, state):
        self.state = state
    def _redirect(self):
        stdout_fd = os.open(self.options['stdout_logfile'], os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        stderr_fd = os.open(self.options['stderr_logfile'], os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)

def daemon_proc():
    child = os.fork()
    if child == 0:
        print('daemon :', os.getpid())
        set_signals()
        spawn_processes()
        daemon = ServerSocket()
        daemon_ear(daemon)

def daemon_ear(daemon):
    while True:
        request = daemon.recv()
        if request == 'status':
            for proc in processes.values():
                daemon.send(proc.name + ' state: ' + proc.state + ' exitcode:  ' + str(proc.exitcode))
            daemon.send(END)
        elif request == 'pid':
            daemon.send(str(os.getpid()))
        elif request == 'exit':
            daemon.close()
            exit(0)

def set_signals():
        signal.signal(signal.SIGCHLD, sig_handler)
        signal.signal(signal.SIGALRM, sig_handler)
        signal.siginterrupt(signal.SIGALRM, False)
        signal.siginterrupt(signal.SIGCHLD, False)


def sig_handler(sig, frame):
    if sig == signal.SIGCHLD:
        status = os.wait()
        pid = status[0]
        exitcode = status[1]
        [proc.change_state('EXITED') for proc in processes.values() if proc.pid == pid]
    elif sig == signal.SIGALRM:
        print('ALRM')
    

def spawn_processes():
    for proc_name in processes:
        if processes[proc_name].options['autostart'] == 'true':
            processes[proc_name].start()


def processes_obj(configfile):
    sections = configfile.sections()
    for section in sections:
        num_procs = int(configfile.get(section, 'numprocs')) # don't use configfile anymore use processes OBJECT
        proc_name = section.split(':')[1]
        for i in range(num_procs):
            name = proc_name
            if num_procs > 1:
                name += ':' + str(i)
            processes[name] = Process(name) 
            for option in configfile.options(section):
                processes[name].options[option] = configfile.get(section, option)

def config_checkr(configfile):
    #master section
    if not configfile.has_section('master') or not configfile.has_option('master', 'logfile') or len(configfile.options('master')) > 1:
        return (-1)                                     #'Error: config file error'
    logfile = configfile.get('master', 'logfile')       #logfile
    configfile.remove_section('master')
    #program sections 
    pattern = re.compile('program:')
    sections = configfile.sections() 
    for section in sections:
        if not pattern.match(section):
            return (-1)                                 #'Error: Forbidden section name'
    #options
    for section in sections:
        options = configfile.options(section)
        for option in options:
            if not option in options_sample.keys():
                return (-1)                             #'Error: Option not allowed'

def main():
    configfile = configparser.ConfigParser()
    try:
        configfile.read('taskmaster.conf')
    except OSError:
        print('Cannot open configuration file')
    config_checkr(configfile)
    processes_obj(configfile)
    daemon_proc()

if __name__ == "__main__":
    main()




