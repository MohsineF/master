#!/usr/bin/python3

import socket
import os
import struct
import signal

END = 'DAEMON COPY'

class ClientSocket():
    def __init__(self):
        self.sock_address = "/tmp/sockd"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket.connect(self.sock_address)
        except OSError as err:
            print('Daemon Connect: ', err)
            exit(0)
    def close(self):
        self.socket.close()
    def send(self, msg):
        length = struct.pack('!I', len(msg))
        self.socket.sendall(length)
        self.socket.sendall(msg.encode())
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
        elif line == 'help':
            help_cmd()
        elif line == 'exit':
            exit_cmd()

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
    print("stop     reload   exit") 
    print("pid (of daemon proc)") 

def exit_cmd():
    client.send('exit')
    client.close()
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sig_handler)
    read_line()
