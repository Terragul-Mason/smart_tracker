from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin@localhost/smart_tracker'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMINS = ['admin@tracker.local']

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    tickets = db.relationship('Ticket', backref='author', lazy=True)

class Ticket(db.Model):
    __tablename__ = 'ticket'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    urgency = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='новая')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.String(100))

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(email=email).first():
            flash('Пользователь уже существует')
            return redirect(url_for('register'))
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Успешная регистрация')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['is_admin'] = email in ADMINS
            return redirect(url_for('dashboard'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    query = Ticket.query

    if session.get('is_admin'):
        type_filter = request.args.get('type')
        urgency_filter = request.args.get('urgency')
        status_filter = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        if type_filter:
            query = query.filter_by(type=type_filter)
        if urgency_filter:
            query = query.filter_by(urgency=urgency_filter)
        if status_filter:
            query = query.filter_by(status=status_filter)
        if date_from:
            query = query.filter(Ticket.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        if date_to:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d")
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
            query = query.filter(Ticket.created_at <= dt_to)

        tickets = query.order_by(Ticket.created_at.desc()).all()
    else:
        tickets = Ticket.query.filter_by(user_id=session['user_id']).order_by(Ticket.created_at.desc()).all()

    comments = {}
    for t in tickets:
        comments[t.id] = Comment.query.filter_by(ticket_id=t.id).order_by(Comment.created_at).all()

    return render_template('dashboard.html', tickets=tickets, comments=comments)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        type_ = request.form['type']
        urgency = request.form['urgency']
        ticket = Ticket(title=title, description=description, type=type_, urgency=urgency, user_id=session['user_id'])
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('create_ticket.html')

@app.route('/update_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def update_ticket(ticket_id):
    if not session.get('is_admin'):
        flash('Нет доступа')
        return redirect(url_for('dashboard'))

    ticket = Ticket.query.get_or_404(ticket_id)
    ticket.status = request.form['status']
    ticket.assigned_to = request.form['assigned_to']
    db.session.commit()
    flash('Заявка обновлена')
    return redirect(url_for('dashboard'))

@app.route('/add_comment/<int:ticket_id>', methods=['POST'])
@login_required
def add_comment(ticket_id):
    if not session.get('is_admin'):
        flash('Нет доступа')
        return redirect(url_for('dashboard'))

    text = request.form['text']
    comment = Comment(text=text, ticket_id=ticket_id, user_email=session['user_email'])
    db.session.add(comment)
    db.session.commit()
    flash('Комментарий добавлен')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
