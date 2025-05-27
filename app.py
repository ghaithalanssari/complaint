from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import make_response
from weasyprint import HTML

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
db = SQLAlchemy(app)

# نموذج المستخدم
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    complaints = db.relationship('Complaint', backref='user', lazy=True)

# نموذج البلاغ
class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='قيد المراجعة')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    def __repr__(self):
        return f'<User {self.username}>'

# إنشاء جداول قاعدة البيانات وإنشاء أدمن
def initialize_database():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                national_id='0000000000',
                phone='0123456789',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

# استدعاء الدالة عند بدء التشغيل
initialize_database()

# الروابط الأساسية
@app.route('/')
def home():
    return render_template('index.html')

@app.errorhandler(500)
def handle_errors(e):
    db.session.rollback()
    return render_template('error.html'), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # التحقق من عدم وجود تكرار في البيانات
        existing_user = User.query.filter(
            (User.username == request.form['username']) | 
            (User.national_id == request.form['national_id'])
        ).first()
        
        if existing_user:
            if existing_user.username == request.form['username']:
                return 'اسم المستخدم موجود مسبقاً!'
            else:
                return 'الرقم الوطني مسجل بالفعل!'
        
        try:
            new_user = User(
                username=request.form['username'],
                password=generate_password_hash(request.form['password']),
                national_id=request.form['national_id'],
                phone=request.form['phone']
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            return f'حدث خطأ: {str(e)}'
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            return redirect(url_for('dashboard'))
        return 'بيانات الدخول غير صحيحة'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['is_admin']:
        complaints = Complaint.query.all()
        users = User.query.all()
        return render_template('admin_dashboard.html', complaints=complaints, users=users)
    else:
        user = User.query.get(session['user_id'])
        return render_template('user_dashboard.html', user=user)
    
@app.route('/admin/print/<int:id>')
def print_complaint(id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    complaint = Complaint.query.get(id)
    user = User.query.get(complaint.user_id)
    
    html = render_template('print_template.html', 
                         complaint=complaint,
                         user=user)
    
    pdf = HTML(string=html).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=report_{id}.pdf'
    return response    

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_complaint = Complaint(
        type=request.form['type'],
        location=request.form['location'],
        description=request.form['description'],
        user_id=session['user_id']
    )
    db.session.add(new_complaint)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/admin/delete/<int:id>')
def delete_complaint(id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    complaint = Complaint.query.get(id)
    db.session.delete(complaint)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/admin/search', methods=['POST'])
def search():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    search_term = request.form['search_term']
    results = Complaint.query.filter(
        (Complaint.description.contains(search_term)) | 
        (Complaint.location.contains(search_term))
    ).all()
    return render_template('admin_dashboard.html', complaints=results)

if __name__ == '__main__':
    app.run(debug=True)