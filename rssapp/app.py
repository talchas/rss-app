from __future__ import absolute_import, unicode_literals

# not using flask-login because do not trust their crypto. not sure /why/ separate cookie used, might be an issue with mine then. ah cookie longer life than session, duh, probably a good idea - into "from werkzeug.contrib.securecookie import SecureCookie" instead though, that's what session uses, alternatively just session.permenant I think.
# make sure urls start with http, or at least not javascript

from datetime import datetime
from flask import Flask, session, request, redirect, url_for, render_template, flash, g
from rssapp import db, worker
from decorator import decorator
from flask.ext.wtf import Form
from wtforms import TextField, PasswordField, validators
from werkzeug.routing import Rule, Map, BaseConverter

app = Flask("rssapp")

class BooleanConverter(BaseConverter):

    def __init__(self, url_map, randomify=False):
        super(BooleanConverter, self).__init__(url_map)
        self.regex = '(?:yes|no)'

    def to_python(self, value):
        return value == 'yes'

    def to_url(self, value):
        return value and 'yes' or 'no'

app.url_map.converters['bool'] = BooleanConverter
@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


class LoginForm(Form):
    name = TextField('Name', validators=[validators.required()])
    password = PasswordField('Password', validators=[validators.required()])

@app.route("/login", methods = ["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(db.User).filter_by(name = form.name.data).first()
        if user and user.password == form.password.data:
            session['user_id'] = user.id
            session.permanent = True
            flash("login as '%s' successful" % user.name)
            return redirect(request.args['next'] or url_for("/"))
    flash("login as '%s' failed" % (form.name.data or ''))
    return render_template('login.html', form=form)

@decorator
def require_login(page, *args, **kw):
    userid = session.get('user_id')
    if not userid:
        return redirect(url_for("login", next = request.path))
    g.user = db.session.query(db.User).get(userid)
    return page(*args, **kw)

@app.route("/logout")
def logout():
    flash("logged out")
    session.pop('user_id', None)
    return redirect(url_for('main'))

def mark_read_stamp(items):
    x = 0
    for item in items:
        x = max(x, item.id)
    return x

@app.route("/")
def root():
    return redirect(url_for('main'))

def get_entries(user, feed = None, show_read = False, start = 0, count = 500):
    entries = db.session.query(db.Entry).order_by(db.Entry.date.desc())
    if not show_read:
        entries = entries.filter_by(read = False)
    if feed:
        entries = entries.filter_by(owner = feed)
    else:
        entries = entries.join(db.Feed).filter(db.Feed.owner == user)
    return entries[start:(start+count)]


@app.route("/main")
@app.route("/main/<bool:show_read>")
@require_login
def main(show_read = False):
    entries = get_entries(g.user, show_read = show_read)
    return render_template("index.html", feeds=user.feeds, entries=entries,
                           stamp=mark_read_stamp(entries), show_read = show_read)

class AddFeedForm(Form):
    name = TextField('Name', validators=[validators.required()])
    url = TextField('URL', validators=[validators.required(), validators.URL()])

@app.route("/add_feed", methods=["GET", "POST"])
@require_login
def add_feed():
    user = g.user
    form = AddFeedForm()
    if form.validate_on_submit():
        foo = db.Feed(name = request.form['name'], feed_url=request.form['url'], link=request.form['url'], ttl = 10, next_check=datetime.utcnow(), owner = user)
        db.session.add(foo)
        flash("added feed, total now %s" % repr(user.feeds))
        db.session.commit()
        return redirect(url_for('main'))
    for field in form.errors:
        flash("%s: %s" % (field,form.errors[field]))
    return render_template("add_feed.html", form=form)

@app.route("/add_entry/<int:feed_id>", methods=['POST'])
@require_login
def add_entry_post(feed_id):
    foo = db.Entry(name = request.form['name'], url=request.form['url'], date=datetime.utcnow(), _owner = feed_id, read = False)
    db.session.add(foo)
    db.session.commit()
    return redirect(url_for('main'))

@app.route("/add_entry/<int:feed_id>")
@require_login
def add_entry(feed_id):
    return render_template("add_entry.html")

@app.route("/feed/<int:feed_id>")
@app.route("/feed/<int:feed_id>/<bool:show_read>")
@require_login
def feed(feed_id, show_read = True):
    feed = db.session.query(db.Feed).get(feed_id)
    entries = get_entries(g.user, feed = feed, show_read = show_read)
    return render_template("feed.html", feed = feed, items = entries, stamp=mark_read_stamp(entries), show_read=show_read)

def mark_read(last, feed_id = None):
    entries = db.session.query(db.Entry).filter_by(read = False).filter(db.Entry.id <= last)
    if feed:
        entries = entries.filter(db.Entry._owner == feed_id)
    count = 0
    for e in entries:
        e.read = True
        count += 1
    db.session.commit()
    return count

@app.route("/read_feed/<int:feed_id>/<int:stamp>")
@require_login
def read_feed(feed_id, stamp):
    count = mark_read(stamp, feed_id)
    flash("Marked %d as read" % count)
    return redirect(url_for('feed', feed_id=feed_id))

@app.route("/read_all/<int:stamp>")
@require_login
def read_all(stamp):
    count = mark_read(stamp)
    flash("Marked %d as read" % count)
    return redirect(url_for('main'))

@decorator
def ajax_null(page, *args, **kw):
    value = page(*args, **kw)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return ""
    return value

@app.route("/toggle_read/<int:entry_id>")
@ajax_null
@require_login
def toggle_read(entry_id):
    entry = db.session.query(db.Entry).get(entry_id)
    entry.read = not entry.read
    db.session.commit()
    return redirect(request.referrer or url_for('feed', entry.owner.id))

@app.route("/read_and_go/<int:id>")
@ajax_null
@require_login
def read_and_go(id):
    entry = db.session.query(db.Entry).get(id)
    entry.read = True
    db.session.commit()
    return redirect(entry.url)

app.secret_key = b'\xf5\xdd\xbc\x8f\x83\x10Na\t\xd3\xe7C99\x80\xdb6\xc5G\x1f\'\xfb\x1e\x0f\xdez\xe9\x7f\x16\x02\x9e\x1f{(\x0f\x10\x01"\xfe\xd2\ny\x0b\xd8\x9d\x06\xc3\x9c\xf7B8\xf7\xdb\x80\xdc\xe2\xcf\x91[\n\x13eo\x15'
async = worker.Worker()

