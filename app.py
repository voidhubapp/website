import json
import sys
from typing import List
import requests
from flask import Flask, jsonify, request, redirect, render_template, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user,login_required,logout_user, current_user
from flask_socketio import SocketIO, emit
from apscheduler.schedulers.background import BackgroundScheduler
import bcrypt

def get_hashed_password(plain_text_password):
    # Hash a password for the first time
    #   (Using bcrypt, the salt is saved into the hash itself)
    return bcrypt.hashpw(plain_text_password, bcrypt.gensalt())

def check_password(plain_text_password, hashed_password):
    # Check hashed password. Using bcrypt, the salt is saved into the hash itself
    return bcrypt.checkpw(plain_text_password.encode(), hashed_password)


app = Flask(__name__)
app.config["SECRET_KEY"] = "nerndior3je4dmos984wjef9"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)
loginManager = LoginManager()
loginManager.init_app(app)
socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

class User(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100),nullable=False, unique=True)
    email = db.Column(db.String(120),nullable=False, unique=True)
    password = db.Column(db.String(1024),nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    karma = db.Column(db.Integer)
    awards = db.Column(db.String(1024))


@loginManager.user_loader
def load_user(user_id):
    return User.query.get(user_id)        


class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cname = db.Column(db.String(100),nullable=False, unique=True)
    members = db.Column(db.Integer)
    display_name = db.Column(db.String(120),nullable=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100),nullable=False)
    community = db.Column(db.String(100),nullable=False)
    title = db.Column(db.String(100),nullable=False)
    body = db.Column(db.String(100),nullable=True)
    upvotes = db.Column(db.Integer)
    downvotes = db.Column(db.Integer)

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/register")
def register():
    return render_template('register.html')

@app.errorhandler(401)
def unauthorized(error):
    return '<body bgcolor="#000"><img src="https://http.cat/401.jpg"></body>',401

@app.errorhandler(404)
def notfound(error):
    return '<body bgcolor="#000"><img src="https://http.cat/404.jpg"></body>',404


@app.route("/v/<community_n>")
def void(community_n):
    c = Community.query.filter_by(cname=community_n).first()
    posts = Post.query.filter_by(community=community_n).all()
    return render_template("community.html",community=c, posts=posts)


@app.route("/v/<community_n>/json")
def void_json(community_n):
    c:Community = Community.query.filter_by(cname=community_n).first()
    posts = Post.query.filter_by(community=community_n).all()
    posts:List[Post]
    d = {
        "meta":{
            "name":c.cname,
            "id":c.id,
            "display_name":c.display_name,
            "members":c.members
        },
        "posts":{}
    }
    for post in posts:
        d["posts"][post.id] = {
            "title":post.title,
            "community":post.community,
            "body":post.body,
            "upvotes":post.upvotes,
            "downvotes":post.downvotes
        }
    return jsonify(d)

def get_posts_XML(d:dict):
    final = """"""
    for key in d.keys():
        final += f"<POST_{key}>\n"

        if isinstance(d[key], dict):
            for _ in d[key].keys():
                final += f"<{_}>{d[key][_]}</{_}>\n"
        else:
                final += f"{d[key]}\n"
        final += f"</POST_{key}>\n"

    return final

@app.route("/v/<community_n>/xml")
def void_xml(community_n):
    c:Community = Community.query.filter_by(cname=community_n).first()
    posts = Post.query.filter_by(community=community_n).all()
    posts:List[Post]
    d = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<community>
<meta>
    <name>{c.cname}</name>
    <id>{c.id}</id>
    <display_name>{c.display_name}</display_name>
    <members>{c.members}</members>
</meta>    

    """
    D = {}
    for post in posts:
        D[post.id] = {
            "title":post.title,
            "community":post.community,
            "body":post.body,
            "upvotes":post.upvotes,
            "downvotes":post.downvotes
        }

    d += f"""<posts>
    {get_posts_XML(D)}
</posts>
</community>

    """
    r = Response(d, mimetype="application/xml")
    return r

@app.route("/v/<community_n>/new")
@login_required
def new(community_n):
    c = Community.query.filter_by(cname=community_n).first()
    return render_template("create-post.html",community=c)


@app.route("/v/<community_n>/new",methods=["POST"])
@login_required
def new_in(community_n):
    if community_n != "all":
        c = Community.query.filter_by(cname="all").first()
        alls = Post.query.filter_by(community="all").all()
        post = Post(id=len(alls)+1,user="anon",community="all",title=request.form.get("post-title"),body=request.form.get("post-content"),upvotes=0,downvotes=0)
        db.session.add(post)
        db.session.commit()
        
    c = Community.query.filter_by(cname=community_n).first()
    alls = Post.query.filter_by(community=c.cname).all()
    post = Post(id=len(alls)+1,user="anon",community=c.cname,title=request.form.get("post-title"),body=request.form.get("post-content"),upvotes=0,downvotes=0)
    db.session.add(post)
    db.session.commit()
    return redirect(f"/v/{c.cname}")


@app.route("/logoff")
@login_required
def logut():
    logout_user()
    return redirect(f"/")

@app.route("/comments/<community_n>/<int:comment_id>")
def comment(community_n,comment_id):
    c = Community.query.filter_by(cname=community_n).first()
    post = Post.query.filter_by(community=c.cname,id=comment_id).first()
    return render_template(f"post.html",post=post,community=c)

@app.route("/upvote/<community_n>/<int:comment_id>")
@login_required
def upvote(community_n,comment_id):
    c = Community.query.filter_by(cname=community_n).first()
    post = Post.query.filter_by(community=c.cname,id=comment_id).update({Post.upvotes: Post.upvotes+1})
    post = Post.query.filter_by(community=c.cname,id=comment_id).first()
    db.session.commit()
    print("yeet")
    socketio.emit('vote update',(community_n,comment_id,post.upvotes),broadcast=True)
    # return redirect(f"/comments/{community_n}/{comment_id}")
    return json.dumps({'result':200, 'new_vote_count':post.upvotes})

    
@app.route("/downvote/<community_n>/<int:comment_id>")
@login_required
def downvote(community_n,comment_id):
    c = Community.query.filter_by(cname=community_n).first()
    post = Post.query.filter_by(community=c.cname,id=comment_id).update({Post.upvotes: Post.upvotes-1})
    db.session.commit()
    post = Post.query.filter_by(community=c.cname,id=comment_id).first()
    # return redirect(f"/comments/{community_n}/{comment_id}")
    socketio.emit('vote update',(community_n,comment_id,post.upvotes),broadcast=True)
    return json.dumps({'result':200, 'new_vote_count':post.upvotes})
    
@app.route("/create-community")
@login_required
def create_void():
    return render_template("create-community.html")


@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/login",methods=["POST"])
def login_POST():
    username = request.form.get("username")
    password = request.form.get("password")
    user = User.query.filter_by(username=username).first()
    print(bool(user))
    if user is not None:
        if check_password(password, user.password):
            login_user(user)
            return redirect("/")

    else:
        return redirect("/login")
@app.route("/signup")
def signup():
    name = requests.get("https://random-data-api.com/api/internet_stuff/random_internet_stuff").json()["username"]
    return render_template("create-account.html",random_name=name)


@app.route("/signup",methods=["POST"])
def signup_POST():
    _ID = len(User.query.all())+1
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    usrname_found = User.query.filter_by(username=username).first()
    ml_found = User.query.filter_by(email=email).first()
    if usrname_found or ml_found:
        return redirect("/signup")
    
    usr = User(id=_ID,username=username,email=email,password=get_hashed_password(password.encode()),karma=0)
    login_user(usr)

    db.session.add(usr)
    db.session.commit()
    return redirect("/")


@app.route("/create-community",methods=["POST"])
@login_required
def create_community_POST():
    alls = Community.query.all()
    com = Community(id=len(alls)+1,cname=request.form.get("community-name"),display_name=request.form.get("community-display-name"),members=1)
    db.session.add(com)
    db.session.commit()
    return redirect(f"/v/{com.cname}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        if sys.argv[3] == "--dev":
            socketio.run(app,debug=True)
    socketio.run(app, "0.0.0.0", 80)