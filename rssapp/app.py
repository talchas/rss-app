from __future__ import absolute_import, unicode_literals

from flask import Flask, session, request, redirect, url_for, render_template
from rssapp import db
from decorator import decorator
app = Flask("rssapp")

@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


@app.route("/login", methods = ["POST"])
def login_post():
    user = db.session.query(db.User).filter_by(name = request.form['name']).one()
    if user and user.password == request.form['password']:
        session['user'] = user
        return redirect(request.args['next'] or url_for("/"))
    else:
        return login()

@app.route("/login")
def login():
    return render_template('login.html')

@decorator
def require_login(page, *args, **kw):
    if not 'user' in session:
        return redirect(url_for("login", next = request.path))
    return page(*args, **kw)

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect("/")


@app.route("/")
@require_login
def root():
    return "Wow this is totally useless so far!"

@app.route("/foo")
@require_login
def foo():
    return "Wow this is totally useless so far!"


app.secret_key = b'\xf5\xdd\xbc\x8f\x83\x10Na\t\xd3\xe7C99\x80\xdb6\xc5G\x1f\'\xfb\x1e\x0f\xdez\xe9\x7f\x16\x02\x9e\x1f{(\x0f\x10\x01"\xfe\xd2\ny\x0b\xd8\x9d\x06\xc3\x9c\xf7B8\xf7\xdb\x80\xdc\xe2\xcf\x91[\n\x13eo\x15'

