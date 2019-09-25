#!/usr/bin/python

import socket
import os
import struct

class ServerSocket():
    def __init__(self):
        self.sock_address = "/tmp/sockd"
        os.remove(self.sock_address)
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
        length, = struct.unpack('!I', n)
        message = self.connection.recv(length)
        return message.decode()

if __name__ == "__main__":

    daemon = ServerSocket() 
    while 1:
        data = daemon.recv()
        dt = 'server read: ' + data.decode()
        daemon.send(dt)
    daemon.close()
