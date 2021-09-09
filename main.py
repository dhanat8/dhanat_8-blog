import flask
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar

# ----- admin decorator ----- #
from functools import wraps
from flask import abort


# Create admin-only decorator
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403, 'You cannot enter this area')
        # Otherwise continue with the route function
        return function(*args, **kwargs)

    return decorated_function


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# login manager
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(users_id):
    return Users.query.get(int(users_id))


# CONFIGURE TABLES
class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts protperty in the User class.
    author = relationship("Users",
                          back_populates="posts")  # to get a name --> BlogPost.author --> this is one of the Users' attributes --> BlogPost.author.name

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    comment_text = db.Column(db.Text, nullable=False)
    # *******Add child relationship*******#
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship('Users', back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        find_existing_user = Users.query.filter_by(email=register_form.email.data).first()
        if not find_existing_user:
            new_user = Users(
                email=register_form.email.data,
                password=generate_password_hash(register_form.password.data, method='pbkdf2:sha256', salt_length=8),
                name=register_form.name.data
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(user=new_user)
            next = flask.request.args.get('next')
            return redirect(next or url_for('get_all_posts'))
        else:
            flash("This email already exists please log in!")
            return redirect(url_for('login'))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["POST", "GET"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        email = login_form.email.data
        if Users.query.filter_by(email=email).first():
            user_who_login = Users.query.filter_by(email=email).first()
            his_or_her_password = user_who_login.password
            password = check_password_hash(his_or_her_password, login_form.password.data)
            if password:
                # print("login ok")
                print(user_who_login)
                login_user(user=user_who_login)
                next = flask.request.args.get('next')
                return redirect(next or url_for("get_all_posts"))
            else:
                # print("login not okay")
                flash("Password is incorrect!")
                return redirect(url_for("login"))
        else:
            # print("no mail")
            flash("Email does not exist! Please register")
            return redirect(url_for("register"))
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()

    if request.method == "POST":
        if form.validate_on_submit:
            if not current_user.is_authenticated:
                flash("You need to login or register to comment.")
                return redirect(url_for("login"))

            new_comment = Comment(
                comment_text=form.text.data,
                comment_author=current_user,
                parent_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
            return render_template("post.html", post=requested_post, form=form)

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
@login_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

"""To create a wrapper"""
# from functools import wraps
# from flask import abort --> it will render an error code (flash just pop a message up)

# Create admin-only decorator
# def admin_only(function):
#     @wraps(function) --> because our function already have a decorator
#     def decorated_function(*args, **kwargs):  --> *args, **kwargs from the function
#         #If id is not 1 then return abort with 403 error
#         if current_user.id != 1:
#             return abort(403,"optional:YOUR_MESSAGE")
#         #Otherwise continue with the route function
#         return function(*args, **kwargs)
#     return decorated_function


"""Relational databases"""
# In relational databases such as SQLite, MySQL or Postgresql we're able to define a relationship between tables
# using a ForeignKey and a relationship() method.

# e.g. If we wanted to create a One to Many relationship between the User Table
# and the BlogPost table, where One User can create Many BlogPost objects,
# we can use the SQLAlchemy docs to achieve this.
# https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html

# One to One Relationship (1:1)
# A single entity instance in one entity class is related to a single entity instance in another entity class.

# For example:
# Each student fills one seat and one seat is assigned to only one student.
# Each professor has one office space.
# One to Many Relationship (1:M)
# A single entity instance in one entity class (parent) is related to multiple entity instances in another entity class (child)

# For example:
# One instructor can teach many courses, but one course can only be taught by one instructor.
# One instructor may teach many students in one class, but all the students have one instructor for that class.
# Many to Many Relationship (M:M)
# Each entity instance in one entity class is related to multiple entity instances in another entity class; and vice versa.

# For example:
# Each student can take many classes, and each class can be taken by many students.
# Each consumer can buy many products, and each product can be bought by many consumers.
# The detailed Crow's Foot Relationship symbols can be found here. Crow's Foot Relationship Symbols

# Many to many relationships are difficult to represent. We need to decompose a many to many (M:M) relationship into two one-to-many (1:M) relationships.

# 1.from sqlalchemy import Table, Column, Integer, ForeignKey
#   from sqlalchemy.orm import relationship
#   from sqlalchemy.ext.declarative import declarative_base
#
# 2. Base = declarative_base()
# 3. class Parent(Base): --> we create a normal table first ( this is a parent)
#        __tablename__ = 'parent'
#        id = Column(Integer, primary_key=True)
#        children = relationship("Child", back_populates="parent") --> tell it, what's its child and a child can come back to a parent
# so if this is unidirectional, don't need to include back_populates
#
#     class Child(Base): --> create a child database
#        __tablename__ = 'child'
#        id = Column(Integer, primary_key=True)
#        parent_id = Column(Integer, ForeignKey('parent.id'))  --> foreign key = take the key of other database
#        parent = relationship("Parent", back_populates="children") --> tell the child who is his parent
#        and Child will get a parent attribute with many-to-one semantics. So if it's not bidirectional, this line is not needed.

# class Users(UserMixin, db.Model):
#     __tablename__ = "users"
#     id = db.Column(db.Integer, primary_key=True)
#     email = db.Column(db.String(100), unique=True)
#     password = db.Column(db.String(100))
#     name = db.Column(db.String(100))
#
#     # This will act like a List of BlogPost objects attached to each User.
#     # The "author" refers to the author property in the BlogPost class.
#     posts = relationship("BlogPost", back_populates="author") --> back_populates here has noting to do with author in BlogPost
#     posts is an attribute of Users class but it is an object from BlogPost
#
# class BlogPost(db.Model):
#     __tablename__ = "blog_posts"
#     id = db.Column(db.Integer, primary_key=True)
#
#     # Create Foreign Key, "users.id" the users refers to the table name of User.
#     author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
#     # Create reference to the User object, the "posts" refers to the posts protperty in the User class.
#     author = relationship("Users", back_populates="posts") # to get a name --> BlogPost.author --> this is one of the Users' attributes --> BlogPost.author.name
#     author is an attribute of BlogPost class but it is an object from Users ( also a pseudo class) + will populates posts in BlogPost (name of the back_populates and the other thing should match)
#     if you use backref="sth", instead of back_populates --> only place it one of the two classes. It is a shortcut
#     when create an author --> pass a Users object into it e.g. <users 1>. If we call Users.posts it will give us the list of all posts that he has posted

#     title = db.Column(db.String(250), unique=True, nullable=False)
#     subtitle = db.Column(db.String(250), nullable=False)
#     date = db.Column(db.String(250), nullable=False)
#     body = db.Column(db.Text, nullable=False)
#     img_url = db.Column(db.String(250), nullable=False)

"""Gravatar"""
# use it to add picture in a comment
# 1. $ pip install Flask-Gravatar
# 2. from flask_gravatar import Gravatar
# 3. gravatar = Gravatar(app,
#                     size=100,
#                     rating='g',
#                     default='retro',
#                     force_default=False,
#                     force_lower=False,
#                     use_ssl=False,
#                     base_url=None)
# 4. in the html file, <img src="{{ 'zzz.sochi@gmail.com' | gravatar }}"/>

"""Version Control"""
# Using git
# Stage 1 : Working Directory
# 1. cd Desktop --> where you are gonna create a new working directory
# 2. mkdir Name_of_your_folder
# 3. cd Name_of_your_folder
# 4. touch File_name_you_want_to_create
# 5. git init

# Stage 2 : Working Area
# git add + File_name_that_you_want_to_track or git add . --> use dot to say add all
# git status --> check the status of your files if they are tracked

# Stage 3 : Local Repository --> you will have a timeline of your commit (master branch)
# git commit + File_name_that_you_want_to_save -m"Present tense message to indicate what you have done"
# git diff File_name --> see the difference
# git checkout File_name --> restore to the latest version
# git log --> to see how many commits we have done

# Using git hub
# from local repository to your remote repository
# 1. Create a new repository on Github name it the same as the one created in github desktop
# 2. Upload working directory (make sure you add git innit)
# 3. if you change anything commit it in the desktop and you can publish it

# or in pycharm:
# 1. allow version control --> tools bar --> VCS --> git
# 2. click the directory --> tools var --> commit --> add
# 3 commit + add a message
# 4. add .gitignore file and go to gitignore.io --> search for flask --> copy the thing to this new file
# 5. Pycharm --> preferences --> version control --> github --> sign in
# 6. publish your project (tools bar)

# Then, """Use Heroku to deploy and host the code"""
# Then, set up a WSGI server with gunicorn
# 1. Pycharm --> preferences --> project name--> python interpreter --> gunicorn
# 2. tell Heroku about ourserver using Procfile
# 2.1 create a new file called Procfile --> type web: gunicorn main:app

