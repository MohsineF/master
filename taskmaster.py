# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    taskmaster.py                                      :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: mfetoui <marvin@42.fr>                     +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2019/09/19 17:45:21 by mfetoui           #+#    #+#              #
#    Updated: 2019/09/25 15:54:41 by mfetoui          ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

import os
import configparser
import re
import time
import signal
import socket

#def spawn_process():
#def error_checkr();

process_state = ['STOPPED', 'STARTING', 'RUNNING', 'BACKOFF', 'STOPPING', 'EXITED', 'FATAL', 'UNKNOWN']

options_sample = {
        'command': '',
        'numprocs': 1,
        'autostart': 'true',
        'autorestart': 'unexpected',
        'exitcodes': '0',
        'startsecs': 1,
        'startretries': 3,
        'stopsignal': 'TREM',
        'stopwaitsecs': 10,
        'environment': '',
        'umask': '022',
        'stdout_logfile': '/tmp/stdout_logfile.log',
        'stderr_logfile': '/tmp/stderr_logfile.log',
        }

processes = dict()

class process():
    def __init__(self, name):
        self.name = name
        self.options = dict(options_sample)
        self.state = 'STOPPED'
        self.pid = None
        self.startsecs = None
    def start(self):
        child = os.fork()
        if child == 0:
            cmd = self.options['command'].split(' ')
            self.redirect()
            self.state = 'STARTING'
            os.execv(cmd[0], cmd)
        elif child > 0:
            self.pid = child
    def redirect(self):
        stdout_fd = os.open(self.options['stdout_logfile'], os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        stderr_fd = os.open(self.options['stderr_logfile'], os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)

class daemon():
    def __init__(self):
        self.sock_address = "/tmp/sockd"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection = None
        self.address = None
    def server(self):
        os.remove(sock_address)
        self.socket.bind(sock_address)
        self.socket.listen(1)
        self.connection, self.address = self.socket.accept()
    def client(self):
        self.socket.connect(self.sock_address)
    def send_data(self, msg):
        self.socket.sendall(str.encode(msg))
    def recv_data(self):
        return self.connection.recv(1024)



def spawn_processes():
    for proc_name in processes:
        if processes[proc_name].options['autostart'] == 'true':
            processes[proc_name].start()

def master_proc():
    master = os.fork()
    if master == 0:
        spawn_processes()
    return master

def processes_obj(configfile):
    sections = configfile.sections()
    for section in sections:
        num_procs = int(configfile.get(section, 'numprocs'))
        proc_name = section.split(':')[1]
        for i in range(num_procs):
            name = proc_name
            if num_procs > 1:
                name += ':' + str(i)
            processes[name] = process(name) 
            for option in configfile.options(section):
                processes[name].options[option] = configfile.get(section, option)

def read_line(daemon):
    while 1:
        line = input('taskmaster> ').strip()
        if line == 'status':
            status_cmd(daemon)
        elif line == 'help':
            help_cmd()
        elif line == 'exit':
            exit_cmd()
        else:
            print('* Unkown Syntax: ',line)

def status_cmd(daemon):
    for proc in processes:
        request = proc + '.state'
        daemon.send_data(request)
        print('client sending:')

def help_cmd():
    print("Default commands:")
    print("==================")
    print("status   start    restart")
    print("stop     reload   exit") 

def exit_cmd():
    exit(0)

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
    daemon = socket()
    daemon.client()
    read_line(daemon)


if __name__ == "__main__":
    main()




