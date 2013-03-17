from __future__ import absolute_import, unicode_literals
from multiprocessing import Process, Pipe
from decorator import decorator
from rssapp import db
import os

child = None
send_pipe = None

def worker(q):
    global child
    child = None
    print "worker2 %d" % os.getpid()
    while True:
        (f, args, kw) = q.recv()
        f(*args, **kw)

@decorator
def in_child(f, *args, **kw):
    global child, send_pipe
    if child:
        return f(*args, **kw)
    else:
        return send_pipe.send((f, args, kw))


@in_child
def print_foo(v):
    print "%d, %s" % (os.getpid(), str(v))

@in_child
def foo(v):
    print db.session.query(db.Entry).all()

def start():
    global child, send_pipe
    if not child:
        a, b = Pipe(False)
        child = Process(target = worker, args=(a,) )
        send_pipe = b
        child.start()
        a.close()
