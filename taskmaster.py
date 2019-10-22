#!/usr/bin/python3

import socket
import os
import struct
import signal
import sys
import errno
from tasksocket import *


client = ClientSocket()

def read_line():
    r, w = os.pipe()
    rd = os.fdopen(r) 
    read_pid = os.fork()
    if read_pid == 0:
        os.close(r)
        os.dup2(w, 2)
        os.close(w)
        os.execv("./a.out", list("./a.out"))
        sys.exit()
    os.close(w)
    time.sleep(1)
    while True:
        os.kill(read_pid, 30)
        line = rd.readline().split(' ')
        print("line: ", line)
        time.sleep(2)
        if len(line) > 2 or len(line) == 0:
            continue
        if line[0] == 'status':
            status_cmd(line)
        elif line[0] == 'pid':
            pid_cmd()
        elif line[0] == 'start':
            start_cmd(line)
        elif line[0] == 'restart':
            restart_cmd(line)
        elif line[0] == 'stop':
            stop_cmd(line)
        elif line[0] == 'reload':
            reload_cmd(line)
        elif line[0] == 'quit':
            quit_cmd()
        elif line[0] == 'help':
            help_cmd()
        elif line[0] == 'exit':
            exit_cmd()
        elif line[0] != '':
            print('No such command: type "help"')


def status_cmd(line):
    if len(line) > 1:
        print('Status has no second agrument')
        return 
    client.send('status')
    while True:
        data = client.recv()
        if not data or data == END:
            break
        print(data)

def start_cmd(line):
    if len(line) == 1 or len(line) > 2:
        print('start: <program name>')
        return
    client.send('start ' + line[1])
    print(client.recv())


def restart_cmd(line):
    if len(line) == 1 or len(line) > 2:
        print('restart: <program name>')
        return
    client.send('restart ' + line[1])
    print(client.recv())
    print(client.recv())


def stop_cmd(line):
    if len(line) == 1 or len(line) > 2:
        print('stop: <program name>')
        return
    client.send('stop ' + line[1])
    print(client.recv())
    print(client.recv())

def reload_cmd(line):
    if len(line) > 1:
        print('Reload has no second argument')
        return
    client.send('reload')
    print(client.recv())

def pid_cmd():
    client.send('pid')
    print('Daemon PID: ', client.recv())

def help_cmd():
    print("Default commands:")
    print("=================")
    print("status   start    restart")
    print("stop     reload   exit(shell)") 
    print("pid      quit(everything)") 

def quit_cmd():
    client.send('quit')
    print(client.recv())
    print(client.recv())
    client.close()
    sys.exit()


def exit_cmd():
    client.send('exit')
    client.close()
    sys.exit()

def sig_handler(sig, frame):
    exit_cmd()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTSTP, sig_handler)
    signal.signal(signal.SIGHUP, sig_handler)
    signal.signal(signal.SIGQUIT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    read_line()
