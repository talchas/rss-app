from __future__ import absolute_import, unicode_literals
from multiprocessing import Process, Pipe
from decorator import decorator
from rssapp import db
from datetime import datetime, timedelta
import feedparser
import sys
import os
import calendar
import socket

def runner(self):
    self.run()

def st_datetime(st):
    return datetime.utcfromtimestamp(calendar.timegm(st))
class Worker:
    events = []
    next_check_event = None
    is_child = False
    proc = None
    def __init__(self, debug = False):
        if debug:
            self.is_child = True
            return

    def start(self):
        self.start_pid = os.getpid()
        r, s = Pipe(False)
        self.q = r
        self.send = s
        self.proc = Process(target = runner, args=(self,) )
        self.proc.daemon = True
        self.proc.start()

    class Event:
        def __init__(self, function, when = None, offset = None):
            if when and offset:
                raise Exception("only one of when and offset please")
            if offset:
                when = datetime.utcnow() + offset
            self.when = when
            self.function = function

        def __cmp__(self, other):
            return cmp(self.when, other.when)
        def __str__(self):
            return "<%s: %s>" % (str(self.when), str(self.function))

    @decorator
    def rpc(f, *args, **kw):
        self = args[0]
        if not self.is_child:
            if not self.proc or not self.proc.is_alive():
                self.start()
            return self.send.send((f.__name__,args[1:], kw))
        else:
            return f(*args, **kw)

    def run(self):
        self.is_child = True
        print "worker2 %d" % os.getpid()
        socket.setdefaulttimeout(10.0)
        self.recheck_feeds()
        while True:
            if self.q.poll(self.next_timeout()):
                (fn, args, kw) = self.q.recv()
                self.__class__.__dict__[fn](self, *args, **kw)
            else:
                self.run_current_event() 

    def next_timeout(self):
        if len(self.events) == 0:
            return None
        return (self.events[0].when - datetime.utcnow()).total_seconds()

    def run_current_event(self):
        return self.events[0].function()

    def update_feed(self, feed, now, override_url = None, override_headers = None):
        p = feedparser.parse(override_url or feed.feed_url, request_headers = override_headers)
        #, etag = feed.etag, modified = feed.last_modified
        if p.get('status', 410) == 410: # dead
            feed.ttl *= 2
        elif p.status == 301: # moved permanently
            pass
            # feed.feed_url = p.href # honestly, probably more likely hax
        elif p.status == 304: # not modified
            pass
        elif not p.feed or p.status >= 400:
            feed.ttl *= 1.2
        else:
            feed.name = p.feed.get('title', feed.name)
            feed.link = p.feed.get('link', feed.link)
            try:
                feed.ttl = int(p.feed.get('ttl'))
            except:
                pass
            if p.get('modified_parsed'):
                feed.last_modified = st_datetime(p.modified_parsed)
            feed.etag = p.get('tag')
            p.entries.reverse() # most recent should have largest id
            for e in p.entries:
                id = e.get('original_id') or e.get('id')
                entry = None
                if not id:
                    id = e.get('link', e.get('title'))
                    if id:
                        id = 'tag:rssapp.talchas.net:'+id
                if id:
                    entry = db.session.query(db.Entry).filter_by(parsed_id = id).first()
                if not entry:
                    entry = db.Entry(owner = feed, parsed_id = id, date = now)
                    db.session.add(entry)
                if e.get('updated_parsed'):
                   entry.date = st_datetime(e.updated_parsed)
                entry.url = e.get('link', entry.url)
                entry.name = e.get('title', entry.name)

                db.session.flush()
        feed.next_check = now + timedelta(minutes = feed.ttl)


    def query_feeds(self):
        now = datetime.utcnow()
        for feed in db.session.query(db.Feed).filter(db.Feed.next_check <= now):
            try:
                self.update_feed(feed, now)
                db.session.commit()
            except:
                print 'error updating feed %s:' % feed.feed_url
                print sys.exc_info()
                db.session.rollback()
        else:
            print "no feeds for %s, despite event expiry" % str(now)
        self.recheck_feeds()

    @rpc
    def recheck_feeds(self):
        next_check = db.session.query(db.func.min(db.Feed.next_check)).scalar()
        if self.next_check_event:
            self.next_check_event.when = next_check
        else:
            self.next_check_event = self.Event(self.query_feeds, when = next_check)
            self.events.append(self.next_check_event)
        self.events.sort()

    @rpc
    def ping(self):
        pass

    @rpc
    def quit(self):
        sys.exit(0)

    def __del__(self):
        if not self.is_child and self.proc:
            self.quit()
