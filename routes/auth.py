from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, ActivityLog, Department
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def log_activity(user_id, action, details='', ip=None):
    log = ActivityLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(log)
    db.session.commit()

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('students.view', student_id=current_user.student_id))
        if current_user.role == 'teacher' and (current_user.department_id is None or current_user.year is None):
            return redirect(url_for('auth.teacher_setup'))
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('students.view', student_id=current_user.student_id))
        return redirect(url_for('dashboard.index'))
    
    # Get all departments for the form
    departments = Department.query.all()
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Get optional teacher setup fields
        department_id = request.form.get('department_id', '').strip()
        year = request.form.get('year', '').strip()
        section = request.form.get('section', '').strip().upper()

        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_active_user:
            login_user(user, remember=True)  # Always remember to survive Vercel container restarts
            session.permanent = True         # Mark session as permanent (7-day lifetime)
            log_activity(user.id, 'LOGIN', f'User {username} logged in', request.remote_addr)
            
            # If it's a teacher and they provided class configuration, save it
            if user.role == 'teacher' and department_id and year and section:
                user.department_id = int(department_id)
                user.year = int(year)
                user.section = section
                db.session.add(user)
                db.session.commit()
                
                # Clear cache to ensure fresh user data
                db.session.expire_all()
                session.modified = True
                
                log_activity(user.id, 'TEACHER_SETUP', f'Teacher configured: dept={department_id}, year={year}, section={section}')
                flash(f'Welcome! Class configured: Year {year} Section {section}.', 'success')
            else:
                flash(f'Welcome back, {user.full_name}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'student':
                return redirect(url_for('students.view', student_id=user.student_id))
            if user.role == 'teacher' and (user.department_id is None or user.year is None):
                return redirect(url_for('auth.teacher_setup'))
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    
    return render_template('auth/login.html', departments=departments)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'teacher')

        if not all([username, email, full_name, password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role=role
        )
        db.session.add(user)
        db.session.commit()
        log_activity(user.id, 'REGISTER', f'New user registered: {username}')
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'LOGOUT', f'User {current_user.username} logged out', request.remote_addr)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/force-change-password', methods=['GET', 'POST'])
@login_required
def force_password_change():
    if current_user.role != 'student' or current_user.password_changed:
        return redirect(url_for('dashboard.index') if current_user.role != 'student' else url_for('students.view', student_id=current_user.student_id))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            flash('Please fill out all fields.', 'danger')
        elif new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
        elif len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
        elif check_password_hash(current_user.password_hash, new_password):
            flash('New password must be different from the default password.', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_password)
            current_user.password_changed = True
            db.session.commit()
            log_activity(current_user.id, 'PASSWORD_CHANGE', 'Student changed default password on first login')
            flash('Password updated successfully. Welcome to your portal!', 'success')
            return redirect(url_for('students.view', student_id=current_user.student_id))
            
    return render_template('auth/force_password_change.html')

@auth_bp.route('/teacher/setup', methods=['GET', 'POST'])
@login_required
def teacher_setup():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard.index'))
        
    departments = Department.query.all()
    
    if request.method == 'POST':
        department_id = request.form.get('department_id')
        year = request.form.get('year')
        section = request.form.get('section', '').strip().upper()
        
        if department_id and year and section:
            # Explicitly fetch from DB and update to ensure SQLAlchemy tracks changes
            user = User.query.get(current_user.id)
            user.department_id = int(department_id)
            user.year = int(year)
            user.section = section
            db.session.add(user)
            db.session.commit()
            
            # CRITICAL: Refresh the database session to clear the cache
            # This ensures Flask-Login will load fresh data on the next request
            db.session.expire_all()
            
            # Mark session as modified to ensure persistence
            session.modified = True
            
            log_activity(current_user.id, 'TEACHER_SETUP', f'Teacher configured: dept={department_id}, year={year}, section={section}')
            flash(f'Class configured: Year {year} Section {section}. Welcome to your dashboard!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Please fill in all fields to continue.', 'danger')
            
    return render_template('auth/teacher_setup.html', departments=departments)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')

        if full_name:
            current_user.full_name = full_name
        if email:
            current_user.email = email

        if current_password and new_password:
            if check_password_hash(current_user.password_hash, current_password):
                current_user.password_hash = generate_password_hash(new_password)
                flash('Password updated successfully.', 'success')
            else:
                flash('Current password is incorrect.', 'danger')
                return render_template('auth/profile.html')

        db.session.commit()
        flash('Profile updated successfully.', 'success')

    return render_template('auth/profile.html')

@auth_bp.route('/set-theme/<theme>')
@login_required
def set_theme(theme):
    if theme in ['light', 'dark']:
        current_user.theme = theme
        db.session.commit()
    return redirect(request.referrer or url_for('dashboard.index'))
