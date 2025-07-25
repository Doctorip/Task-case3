from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = 'verysecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), nullable=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    date = db.Column(db.DateTime)
    tags = db.Column(db.String(200))
    is_private = db.Column(db.Boolean, default=False)
    user = db.relationship('User')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    text = db.Column(db.Text)
    date = db.Column(db.DateTime)
    user = db.relationship('User')

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    subscribed_id = db.Column(db.Integer, db.ForeignKey('user.id'))

def create_tables():
    db.create_all()
    if not User.query.first():
        u1 = User(name="Иван Иванов", email="ivan@example.com", password=generate_password_hash("123456"), avatar="https://randomuser.me/api/portraits/men/1.jpg")
        u2 = User(name="Мария Петрова", email="maria@example.com", password=generate_password_hash("123456"), avatar="https://randomuser.me/api/portraits/women/1.jpg")
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

@app.route('/')
def index():
    user = get_current_user()
    sort = request.args.get('sort', 'new')
    if user:
        posts_query = Post.query.filter(
            (Post.is_private == False) | (Post.user_id == user.id)
        )
    else:
        posts_query = Post.query.filter_by(is_private=False)

    if sort == 'old':
        posts_query = posts_query.order_by(Post.date.asc())
    elif sort == 'likes':
        posts_query = posts_query.outerjoin(Like, Post.id == Like.post_id)\
            .group_by(Post.id)\
            .order_by(func.count(Like.id).desc(), Post.date.desc())
    else:
        posts_query = posts_query.order_by(Post.date.desc())
    posts = posts_query.all()

    for post in posts:
        post.likes_count = Like.query.filter_by(post_id=post.id).count()

    likes = []
    if user:
        likes = [like.post_id for like in Like.query.filter_by(user_id=user.id)]

    all_tags = set()
    for post in posts:
        if post.tags:
            for tag in post.tags.split(','):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
    return render_template('index.html', posts=posts, user=user, likes=likes, all_tags=sorted(all_tags), sort=sort, current_tab='all')

@app.route('/feed/subscriptions')
def feed_subscriptions():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    subs_ids = [s.subscribed_id for s in Subscription.query.filter_by(subscriber_id=user.id)]
    posts = Post.query.filter(
        (Post.user_id.in_(subs_ids)) & ((Post.is_private == False) | (Post.user_id == user.id))
    ).order_by(Post.date.desc()).all()
    for post in posts:
        post.likes_count = Like.query.filter_by(post_id=post.id).count()
    likes = [like.post_id for like in Like.query.filter_by(user_id=user.id)]
    all_tags = set()
    for post in posts:
        if post.tags:
            for tag in post.tags.split(','):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
    return render_template(
        'index.html',
        posts=posts,
        user=user,
        likes=likes,
        all_tags=sorted(all_tags),
        feed_type='subscriptions',
        current_tab='subscriptions'
    )

@app.route('/feed/recommendations')
def feed_recommendations():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    subs_ids = [s.subscribed_id for s in Subscription.query.filter_by(subscriber_id=user.id)]
    ignore_ids = subs_ids + [user.id]
    posts = Post.query.filter(
        (Post.is_private == False) & (~Post.user_id.in_(ignore_ids))
    ).order_by(Post.date.desc()).all()
    for post in posts:
        post.likes_count = Like.query.filter_by(post_id=post.id).count()
    likes = [like.post_id for like in Like.query.filter_by(user_id=user.id)]
    all_tags = set()
    for post in posts:
        if post.tags:
            for tag in post.tags.split(','):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
    return render_template(
        'index.html',
        posts=posts,
        user=user,
        likes=likes,
        all_tags=sorted(all_tags),
        feed_type='recommendations',
        current_tab='recommendations'
    )

@app.route('/tag/<tag>')
def posts_by_tag(tag):
    user = get_current_user()
    sort = request.args.get('sort', 'new')
    if user:
        posts_query = Post.query.filter(
            ((Post.is_private == False) | (Post.user_id == user.id)) &
            (Post.tags.ilike(f"%{tag}%"))
        )
    else:
        posts_query = Post.query.filter(
            (Post.is_private == False) &
            (Post.tags.ilike(f"%{tag}%"))
        )
    if sort == 'old':
        posts_query = posts_query.order_by(Post.date.asc())
    elif sort == 'likes':
        posts_query = posts_query.outerjoin(Like, Post.id == Like.post_id)\
            .group_by(Post.id)\
            .order_by(func.count(Like.id).desc(), Post.date.desc())
    else:
        posts_query = posts_query.order_by(Post.date.desc())
    posts = posts_query.all()
    for post in posts:
        post.likes_count = Like.query.filter_by(post_id=post.id).count()
    likes = []
    if user:
        likes = [like.post_id for like in Like.query.filter_by(user_id=user.id)]
    all_tags = set()
    for post in posts:
        if post.tags:
            for t in post.tags.split(','):
                t = t.strip()
                if t:
                    all_tags.add(t)
    return render_template('index.html', posts=posts, user=user, likes=likes, all_tags=sorted(all_tags), current_tag=tag, sort=sort, current_tab='all')

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    if User.query.filter_by(email=email).first():
        return render_template('login.html', error="Email уже используется")
    avatar = f"https://randomuser.me/api/portraits/men/{User.query.count()+1}.jpg"
    new_user = User(name=name, email=email, password=generate_password_hash(password), avatar=avatar)
    db.session.add(new_user)
    db.session.commit()
    session['user_id'] = new_user.id
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Неверный email или пароль")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/post/new', methods=['GET', 'POST'])
def new_post():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags = request.form['tags']
        is_private = 'is_private' in request.form
        post = Post(user_id=user.id, title=title, content=content, tags=tags, date=datetime.now(), is_private=is_private)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('post_form.html', user=user)

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_view(post_id):
    post = Post.query.get_or_404(post_id)
    user = get_current_user()
    if post.is_private and (not user or post.user_id != user.id):
        return "Этот пост доступен только автору.", 403
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.date.asc()).all()
    liked = False
    if user:
        liked = Like.query.filter_by(user_id=user.id, post_id=post.id).first() is not None
    if request.method == 'POST':
        if not user:
            return redirect(url_for('login'))
        text = request.form['text']
        c = Comment(post_id=post.id, user_id=user.id, text=text, date=datetime.now())
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('post_view', post_id=post.id))
    likes_count = Like.query.filter_by(post_id=post.id).count()
    return render_template('post.html', post=post, comments=comments, user=user, liked=liked, likes_count=likes_count)

@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=user.id, post_id=post.id).first()
    if not existing_like:
        db.session.add(Like(user_id=user.id, post_id=post.id))
        db.session.commit()
    return redirect(url_for('post_view', post_id=post.id))

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    user = get_current_user()
    post = Post.query.get_or_404(post_id)
    if not user or user.id != post.user_id:
        return "Нет доступа", 403
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.tags = request.form['tags']
        post.is_private = 'is_private' in request.form
        db.session.commit()
        return redirect(url_for('post_view', post_id=post.id))
    return render_template('post_form.html', post=post, user=user, editing=True)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    user = get_current_user()
    post = Post.query.get_or_404(post_id)
    if not user or user.id != post.user_id:
        return "Нет доступа", 403
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('profile'))

@app.route('/user/<int:user_id>')
def view_user(user_id):
    target = User.query.get_or_404(user_id)
    user = get_current_user()
    posts = Post.query.filter_by(user_id=target.id).order_by(Post.date.desc()).all()
    is_subscribed = False
    if user and user.id != target.id:
        is_subscribed = Subscription.query.filter_by(subscriber_id=user.id, subscribed_id=target.id).first() is not None
    return render_template('user.html', user=user, target=target, posts=posts, is_subscribed=is_subscribed)

@app.route('/subscribe/<int:user_id>', methods=['POST'])
def subscribe(user_id):
    user = get_current_user()
    if not user or user.id == user_id:
        return redirect(url_for('view_user', user_id=user_id))
    sub = Subscription.query.filter_by(subscriber_id=user.id, subscribed_id=user_id).first()
    if sub:
        db.session.delete(sub)
    else:
        db.session.add(Subscription(subscriber_id=user.id, subscribed_id=user_id))
    db.session.commit()
    return redirect(url_for('view_user', user_id=user_id))

@app.route('/profile')
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.date.desc()).all()
    subs = Subscription.query.filter_by(subscriber_id=user.id).all()
    subs_users = [User.query.get(s.subscribed_id) for s in subs]
    return render_template('profile.html', user=user, posts=posts, subs_users=subs_users)

if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
