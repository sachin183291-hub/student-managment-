from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Student, Department, User, ActivityLog, TimetableEntry
from werkzeug.security import generate_password_hash
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/')
@admin_required
def index():
    total_students = Student.query.count()
    total_users = User.query.count()
    total_departments = Department.query.count()
    recent_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(20).all()
    return render_template('admin/index.html',
                           total_students=total_students,
                           total_users=total_users,
                           total_departments=total_departments,
                           recent_logs=recent_logs)

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)

@admin_bp.route('/users/<int:user_id>/toggle')
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot deactivate yourself.', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active_user = not user.is_active_user
    db.session.commit()
    status = 'activated' if user.is_active_user else 'deactivated'
    flash(f'User {user.username} {status}.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/departments', methods=['GET', 'POST'])
@admin_required
def departments():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip().upper()
        hod = request.form.get('hod', '').strip()

        if not name or not code:
            flash('Name and code are required.', 'danger')
        elif Department.query.filter_by(code=code).first():
            flash(f'Department code {code} already exists.', 'danger')
        else:
            dept = Department(name=name, code=code, hod=hod)
            db.session.add(dept)
            db.session.commit()
            flash(f'Department {name} added successfully!', 'success')
        return redirect(url_for('admin.departments'))

    all_depts = Department.query.order_by(Department.name).all()
    return render_template('admin/departments.html', departments=all_depts)

@admin_bp.route('/departments/<int:dept_id>/delete', methods=['POST'])
@admin_required
def delete_department(dept_id):
    dept = Department.query.get_or_404(dept_id)
    if dept.students:
        flash(f'Cannot delete {dept.name}: it has {len(dept.students)} students.', 'danger')
    else:
        db.session.delete(dept)
        db.session.commit()
        flash(f'Department {dept.name} deleted.', 'success')
    return redirect(url_for('admin.departments'))

@admin_bp.route('/seed-data')
@admin_required
def seed_data():
    """Seed demo data for testing"""
    depts_data = [
        ('Computer Science Engineering', 'CSE'),
        ('Electronics & Communication', 'ECE'),
        ('Mechanical Engineering', 'ME'),
        ('Civil Engineering', 'CE'),
        ('Information Technology', 'IT'),
    ]
    created_depts = {}
    for name, code in depts_data:
        if not Department.query.filter_by(code=code).first():
            dept = Department(name=name, code=code, hod=f'Dr. {name.split()[0]} Professor')
            db.session.add(dept)
            db.session.flush()
            created_depts[code] = dept.id
        else:
            created_depts[code] = Department.query.filter_by(code=code).first().id

    db.session.commit()

    # Seed sample students
    import random
    from datetime import date, timedelta
    names = ['Aarav Sharma', 'Priya Patel', 'Rohan Verma', 'Sneha Gupta', 'Arjun Kumar',
             'Deepika Singh', 'Rahul Nair', 'Ananya Reddy', 'Vikram Joshi', 'Kavya Mehta',
             'Siddharth Das', 'Pooja Iyer', 'Aditya Rao', 'Ishita Kapoor', 'Nikhil Malhotra',
             'Shreya Pandey', 'Kartik Bajaj', 'Tanvi Shah', 'Yash Agarwal', 'Divya Saxena']

    dept_codes = list(created_depts.keys())
    count = 0
    for i, name in enumerate(names):
        roll = f'2024{random.choice(dept_codes)}{str(i+1).zfill(3)}'
        if not Student.query.filter_by(roll_number=roll).first():
            email_part = name.lower().replace(' ', '.').replace("'", '')
            dept_code = random.choice(dept_codes)
            s = Student(
                roll_number=roll,
                full_name=name,
                email=f'{email_part}{i}@college.edu',
                phone=f'9{random.randint(100000000, 999999999)}',
                department_id=created_depts[dept_code],
                year=random.randint(1, 4),
                section=random.choice(['A', 'B', 'C']),
                cgpa=round(random.uniform(5.5, 9.8), 2),
                guardian_name=f'Mr. {name.split()[1]} Sr.',
                status='active'
            )
            db.session.add(s)
            count += 1

    db.session.commit()
    flash(f'Demo data seeded successfully! Added departments and {count} students.', 'success')
    return redirect(url_for('dashboard.index'))

@admin_bp.route('/logs')
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=30)
    users_map = {u.id: u.username for u in User.query.all()}
    return render_template('admin/logs.html', logs=logs, users_map=users_map)

@admin_bp.route('/timetable', methods=['GET'])
@admin_required
def timetable():
    departments = Department.query.all()
    if not departments:
        flash('Please create a department first.', 'warning')
        return redirect(url_for('admin.index'))
        
    dept_id = request.args.get('department_id', departments[0].id, type=int)
    year = request.args.get('year', 1, type=int)
    
    current_dept = Department.query.get_or_404(dept_id)
    
    # Fetch all timetable entries for this department and year
    entries = TimetableEntry.query.filter_by(department_id=dept_id, year=year).all()
    
    # Group entries by day of week and period
    days_list = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    periods_list = list(range(1, 9))
    
    # Initialize schedule grid: schedule[day][period] = TimetableEntry
    schedule = {day: {p: None for p in periods_list} for day in days_list}
    for entry in entries:
        if entry.day_of_week in schedule and entry.period in schedule[entry.day_of_week]:
            schedule[entry.day_of_week][entry.period] = entry
            
    return render_template('admin/timetable.html',
                           departments=departments,
                           current_dept=current_dept,
                           current_year=year,
                           schedule=schedule,
                           days_list=days_list,
                           periods_list=periods_list)

@admin_bp.route('/timetable/update', methods=['POST'])
@admin_required
def update_timetable():
    dept_id = request.form.get('department_id', type=int)
    year = request.form.get('year', type=int)
    day_of_week = request.form.get('day_of_week')
    period = request.form.get('period', type=int)
    subject = request.form.get('subject', '').strip()
    
    if not all([dept_id, year, day_of_week, period, subject]):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        
    entry = TimetableEntry.query.filter_by(
        department_id=dept_id,
        year=year,
        day_of_week=day_of_week,
        period=period
    ).first()
    
    if entry:
        entry.subject = subject
    else:
        entry = TimetableEntry(
            department_id=dept_id,
            year=year,
            day_of_week=day_of_week,
            period=period,
            subject=subject
        )
        db.session.add(entry)
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Timetable updated successfully!', 'subject': subject})
