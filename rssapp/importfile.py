from __future__ import absolute_import, unicode_literals
from rssapp import db

def fromfile(path, user):
    for line in file(path):
        line = line.strip()
        db.session.add(db.Feed(name = '[]', feed_url = line, owner = user))
