from __future__ import absolute_import, unicode_literals
from multiprocessing import Process, Pipe
from decorator import decorator
from rssapp import db
from datetime import datetime
import sys
import os

def runner(self):
    self.run()
class Worker:
    def __init__(self, debug = False):
        self.events = []
        if debug:
            self.send = None
            self.start_pid = False
            return
        self.start_pid = os.getpid()
        r, s = Pipe(False)
        self.q = r
        self.send = s
        self.proc = Process(target = runner, args=(self,) )
        self.proc.start()

    @decorator
    def rpc(f, *args, **kw):
        self = args[0]
        if self.send:
            return self.send.send((f.__name__,args[1:], kw)) #args, kw
        else:
            return f(*args, **kw)
    def run(self):
        self.send = None
        print "worker2 %d" % os.getpid()
        while True:
            if self.q.poll(self.next_timeout()):
                (fn, args, kw) = self.q.recv()
                self.__class__.__dict__[fn](self, *args, **kw)
            else:
                self.run_current_event() 

    def next_timeout(self):
        if len(self.events) == 0:
            return None
        return self.events[0]['time']

    def run_current_event(self):
        return self.events[0]['thunk']()

    @rpc
    def foo(self, v,y):
        print db.session.query(db.Entry).filter(db.Entry.id > v).all()

    @rpc
    def quit(self):
        sys.exit(0)

    def __del__(self):
        if self.start_pid == os.getpid():
            self.quit()
