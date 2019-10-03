#!/usr/bin/python3

import socket
import os
import struct
import signal
import sys

END = 'DAEMON COPY'

SOCKFILE = '/tmp/taskmaster.sock'

class ClientSocket():
    def __init__(self):
        self.sock_address = SOCKFILE
        self.connect()
    def connect(self):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket.connect(self.sock_address)
        except OSError as err:
            print('No Daemon. Try Starting It!')
            sys.exit()
    def close(self):
        self.socket.close()
    def send(self, msg):
        try:
            length = struct.pack('!I', len(msg))
            self.socket.sendall(length)
            self.socket.sendall(msg.encode())
        except OSError as err:
            print('Daemon process killed :( . Try Restarting It!')
            sys.exit()
    def recv(self):
        n = self.socket.recv(4)
        if not n: return None
        length, = struct.unpack('!I', n)
        message = self.socket.recv(length)
        return message.decode()

client = ClientSocket()

def sig_handler(sig, frame):
    exit_cmd()

def read_line():
    while True:
        line = input('taskmaster> ').strip()
        if line == 'status':
            status_cmd()
        elif line == 'pid':
            pid_cmd()
        elif line == 'quit':
            quit_cmd()
        elif line == 'help':
            help_cmd()
        elif line == 'exit':
            exit_cmd()

def quit_cmd():
    client.send('quit')
    print(client.recv())
    print(client.recv())
    sys.exit()

def status_cmd():
    client.send('status')
    while True:
        data = client.recv()
        if not data or data == END:
            break
        print(data)

def pid_cmd():
    client.send('pid')
    pid = client.recv()
    print('Daemon PID: ',pid)

def help_cmd():
    print("Default commands:")
    print("==================")
    print("status   start    restart")
    print("stop     reload   exit(shell)") 
    print("pid      quit(everything)") 

def exit_cmd():
    client.close()
    sys.exit()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sig_handler)
    read_line()
