import errno
import os
import time

LOGFILE = '/tmp/taskmaster.log'
logs = {
        'DAEMON': ('INFO', 'daemon started with pid:'),
        'SPAWN': ('INFO', 'process spawned with pid:'),
        'BACKOFF': ('INFO', 'process backingoff, exit code:'),
        'EXIT': ('INFO', 'process exited, exit code:'),
        'WAITSTOP': ('INFO', 'waiting for process to stop with signal:'),
        'STOP': ('INFO','process stopped with signal:'),
        'KILL': ('WARN', 'process killed with SIGKILL :('),
        'FATAL': ('INFO', 'too many start retries too quickly, process entered FATAL state'),
        'RELOAD' : ('WARN', 'received command/signal indicating reload request'),
        'EACCES': ('WARN', 'couldn\'t open log file for process'),
        'CONFIG': ('ERROR', 'couldn\'t open configuration file'),
        'SECTION': ('ERROR', 'section naming format not allowed in your configuration file !'),
        'OPTION': ('ERROR', 'option Key or Value not allowed in your configuration file !'),
        'QUIT': ('INFO','quitting daemon process')
        }

def tasklog(log, proc, info):
    if os.path.exists(LOGFILE):
        logfile = open(LOGFILE, 'a')
    else:
        logfile = open(LOGFILE, 'w')
    logfile.write(time.asctime() + ' ' + logs[log][0] + ' ' + proc + ' : ' + logs[log][1] + ' ' + info +'\n')
