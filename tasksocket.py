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
            if err.errno == errno.EINTR:
                self.accept()
    def send(self, msg):
        try:
            length = struct.pack('!I', len(msg))
            self.connection.sendall(length)
            self.connection.sendall(msg.encode())
        except socket.error as err:
            if err.errno == errno.EBADF:
                self.accept()
            if err.errno == errno.EINTR:
                self.send(msg)
    def recv(self):
        try:
            n = self.connection.recv(4)
            if not n: return None
            length, = struct.unpack('!I', n)
            message = self.connection.recv(length)
            return message.decode()
        except socket.error as err:
            if err.errno == errno.EBADF:
                self.accept()
            if err.errno == errno.EINTR:
                pass
    def close_connection(self):
        if self.connection:
            self.connection.close()
    def close_socket(self):
        if self.socket:
            self.socket.close()

class ClientSocket():
    def __init__(self):
        self.sock_address = SOCKFILE
        self.connect()
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.sock_address)
        except socket.error as err:
            if  err.errno == errno.ECONNREFUSED:
                print('No Daemon , Try Starting It !')
                sys.exit()
    def send(self, msg):
        try:
            length = struct.pack('!I', len(msg))
            self.socket.sendall(length)
            self.socket.sendall(msg.encode())
        except (OSError, socket.error) as err:
            if  err.errno == errno.EPIPE or err.errno == errno.ENOTCONN:
                print('No Daemon , Try Starting It !')
                sys.exit()
    def recv(self):
        try:
            n = self.socket.recv(4)
            if not n: return None
            length, = struct.unpack('!I', n)
            message = self.socket.recv(length)
            return message.decode()
        except (OSError, socket.error) as err:
            if  err.errno == errno.EPIPE or err.errno == errno.ENOTCONN:
                print('No Daemon , Try Starting It !')
                sys.exit()
    def close(self):
        self.socket.close()
