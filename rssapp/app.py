from __future__ import absolute_import, unicode_literals

# not using flask-login because do not trust their crypto. not sure /why/ separate cookie used, might be an issue with mine then. ah cookie longer life than session, duh, probably a good idea - into "from werkzeug.contrib.securecookie import SecureCookie" instead though, that's what session uses, alternatively just session.permenant I think.
# make sure urls start with http, or at least not javascript

from datetime import datetime
from flask import Flask, session, request, redirect, url_for, render_template, flash, g
from rssapp import db
from decorator import decorator
app = Flask("rssapp")

@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


@app.route("/login", methods = ["POST"])
def login_post():
    user = db.session.query(db.User).filter_by(name = request.form['name']).first()
    if user and user.password == request.form['password']:
        session['user_id'] = user.id
        session.permanent = True
        flash("login as '%s' successful" % user.name)
        return redirect(request.args['next'] or url_for("/"))
    else:
        flash("login as '%s' failed" % request.form['name'])
        return login()

@app.route("/login")
def login():
    return render_template('login.html')

@decorator
def require_login(page, *args, **kw):
    userid = session.get('user_id')
    if not userid:
        return redirect(url_for("login", next = request.path))
    g.user = db.session.query(db.User).filter_by(id = userid).one()
    return page(*args, **kw)

@app.route("/logout")
def logout():
    flash("logged out")
    session.pop('user', None)
    return redirect("/")


@app.route("/")
@require_login
def root():
    user = g.user
    unread = db.session.query(db.Entry).filter_by(read = False).join(db.Feed).filter(db.Feed.owner == user).all()
    return render_template("index.html", feeds=user.feeds, unread=unread)

@app.route("/add_feed", methods=["POST"])
@require_login
def add_feed_post():
    #todo csrf?, generally need csrf flask-wtf, sijax?
    user = g.user
    foo = db.Feed(name = request.form['name'], feed_url=request.form['url'], link=request.form['url'], ttl = 10, next_check=datetime.utcnow(), owner = user)
    db.session.add(foo)
    flash("added feed, total now %s" % repr(user.feeds))
    db.session.commit()
    return redirect("/")

@app.route("/add_feed")
@require_login
def add_feed():
    return render_template("add_feed.html")


@app.route("/add_entry/<int:feed_id>", methods=['POST'])
@require_login
def add_entry_post(feed_id):
    foo = db.Entry(name = request.form['name'], url=request.form['url'], date=datetime.utcnow(), _owner = feed_id, read = False)
    db.session.add(foo)
    db.session.commit()
    return redirect('/')


@app.route("/add_entry/<int:feed_id>")
@require_login
def add_entry(feed_id):
    return render_template("add_entry.html")

@app.route("/feed/<int:feed_id>")
@require_login
def feed(feed_id):
    feed = db.session.query(db.Feed).filter_by(id = feed_id).one()
    entries = db.session.query(db.Entry).filter_by(owner = feed).all()
    return render_template("feed.html", feed = feed, items = entries)

app.secret_key = b'\xf5\xdd\xbc\x8f\x83\x10Na\t\xd3\xe7C99\x80\xdb6\xc5G\x1f\'\xfb\x1e\x0f\xdez\xe9\x7f\x16\x02\x9e\x1f{(\x0f\x10\x01"\xfe\xd2\ny\x0b\xd8\x9d\x06\xc3\x9c\xf7B8\xf7\xdb\x80\xdc\xe2\xcf\x91[\n\x13eo\x15'

