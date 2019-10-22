import errno
import os
import time

LOGFILE = '/tmp/taskmaster.log'
logs = {
        'DAEMON': ('INFO', 'daemon started with pid:'),
        'SPAWN': ('INFO', 'process spawned with pid:'),
        'BACKOFF': ('INFO', 'process backingoff, exitcode:'),
        'EXIT': ('INFO', 'process exited, exit code:'),
        'WAITSTOP': ('INFO', 'waiting for process to stop'),
        'STOP': ('INFO','process stopped,'),
        'KILL': ('WARN', 'killing process with SIGKILL'),
        'TERMINATED': ('INFO', 'process terminated by SIGKILL'),
        'FATAL': ('INFO', 'too many start retries too quickly, process entered FATAL state'),
        'EACCES': ('WARN', 'couldn\'t open log file for process'),
        'CONFIG': ('ERROR', 'couldn\'t open configuration file'),
        'SECTION': ('ERROR', 'section naming format not allowed in your configuration file !'),
        'OPTION': ('ERROR', 'option not allowed in your configuration file !'),
        'QUIT': ('INFO','quitting daemon process')
        }

def tasklog(log, proc):
    if os.path.exists(LOGFILE):
        logfile = open(LOGFILE, 'a')
    else:
        logfile = open(LOGFILE, 'w')
    logfile.write(time.asctime() + ' ' + logs[log][0] + ' ' + proc + ': ' + logs[log][1] + '\n')
