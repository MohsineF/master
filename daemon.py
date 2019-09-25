#!/usr/bin/python

import socket
import os

class socket():
    def __init__(self):
        self.sock_address = "/tmp/sockd"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.connection = None
        self.address = None
    def server(self):
        os.remove(self.sock_address)
        self.socket.bind(self.sock_address)
        self.socket.listen(1)
        self.connection, self.address = self.socket.accept()
    def client(self):
        self.socket.connect(self.sock_address)
    def send_data(self, msg):
        self.connection.sendall(str.encode(msg))
    def recv_data(self):
        return self.connection.recv(1024)

if __name__ == "__main__":
        data = conn.recv(1024)

    daemon = socket()
    daemon.server()
    while 1:
        data = daemon.recv_data()
        print('server read: ', data)

