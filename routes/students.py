from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Student, Department, Attendance
from datetime import datetime, date
import json

students_bp = Blueprint('students', __name__, url_prefix='/students')

@students_bp.route('/')
@login_required
def index():
    if current_user.role == 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('students.view', student_id=current_user.student_id))

    search = request.args.get('search', '')
    
    if current_user.role == 'teacher':
        dept_filter = current_user.department_id
        year_filter = current_user.year
        status_filter = request.args.get('status', '')
    else:
        dept_filter = request.args.get('department', '')
        year_filter = request.args.get('year', '')
        status_filter = request.args.get('status', '')

    query = Student.query
    if current_user.role == 'teacher' and current_user.section:
        query = query.filter(Student.section == current_user.section)

    if search:
        query = query.filter(
            db.or_(
                Student.full_name.ilike(f'%{search}%'),
                Student.roll_number.ilike(f'%{search}%'),
                Student.email.ilike(f'%{search}%')
            )
        )
    if dept_filter:
        query = query.filter(Student.department_id == dept_filter)
    if year_filter:
        query = query.filter(Student.year == year_filter)
    if status_filter:
        query = query.filter(Student.status == status_filter)

    students = query.order_by(Student.roll_number).all()
    departments = Department.query.all()
    
    return render_template('students/index.html',
                           students=students,
                           departments=departments,
                           search=search,
                           dept_filter=dept_filter,
                           year_filter=year_filter,
                           status_filter=status_filter)

@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    departments = Department.query.all()
    
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip().upper()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department_id = request.form.get('department_id')
        year = request.form.get('year')
        section = request.form.get('section', '').strip().upper()
        dob_str = request.form.get('dob', '')
        address = request.form.get('address', '').strip()
        guardian_name = request.form.get('guardian_name', '').strip()
        guardian_phone = request.form.get('guardian_phone', '').strip()
        guardian_email = request.form.get('guardian_email', '').strip()
        cgpa = request.form.get('cgpa', 0.0)

        if not all([roll_number, full_name, email, department_id, year]):
            flash('Please fill all required fields.', 'danger')
            return render_template('students/add.html', departments=departments)

        if Student.query.filter_by(roll_number=roll_number).first():
            flash(f'Roll number {roll_number} already exists.', 'danger')
            return render_template('students/add.html', departments=departments)

        if Student.query.filter_by(email=email).first() or User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('students/add.html', departments=departments)

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        student = Student(
            roll_number=roll_number,
            full_name=full_name,
            email=email,
            phone=phone,
            department_id=int(department_id),
            year=int(year),
            section=section,
            dob=dob,
            address=address,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            guardian_email=guardian_email,
            cgpa=float(cgpa) if cgpa else 0.0
        )
        db.session.add(student)
        db.session.commit()

        # Auto-create User account for the new student
        from models import User
        from werkzeug.security import generate_password_hash
        user = User(
            username=roll_number,
            email=email,
            password_hash=generate_password_hash(roll_number),
            role='student',
            full_name=full_name,
            student_id=student.id,
            password_changed=False
        )
        db.session.add(user)
        db.session.commit()

        flash(f'Student {full_name} added successfully!', 'success')
        return redirect(url_for('students.index'))

    return render_template('students/add.html', departments=departments)

@students_bp.route('/<int:student_id>')
@login_required
def view(student_id):
    student = Student.query.get_or_404(student_id)

    # RBAC Checks
    if current_user.role == 'student' and current_user.student_id != student_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('students.view', student_id=current_user.student_id))
    
    if current_user.role == 'teacher':
        if student.department_id != current_user.department_id or student.year != current_user.year:
            flash('Access denied. This student is not in your assigned class.', 'danger')
            return redirect(url_for('dashboard.index'))
    
    # 1. Recent attendance list
    attendance_records = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc(), Attendance.period.asc()).limit(30).all()
    attendance_pct = student.get_attendance_percentage()
    
    # 2. Subject-wise attendance calculation
    from collections import defaultdict
    all_records = Attendance.query.filter_by(student_id=student_id).all()
    subject_groups = defaultdict(list)
    for r in all_records:
        subject_groups[r.subject].append(r)
        
    subject_stats = []
    for subj, recs in subject_groups.items():
        if subj in ['Lunch Break', 'Free Period']:
            continue
        tot = len(recs)
        pres = sum(1 for r in recs if r.status in ['present', 'late']) # Late counts as attended
        pct = round((pres / tot) * 100, 1) if tot > 0 else 0.0
        subject_stats.append({
            'subject': subj,
            'total': tot,
            'present': pres,
            'absent': tot - pres,
            'pct': pct
        })
    subject_stats.sort(key=lambda x: x['subject'])
    
    # 3. Heatmap Data (Last 7 active school days)
    from models import TimetableEntry
    dates_query = db.session.query(Attendance.date).filter_by(student_id=student_id).distinct().order_by(Attendance.date.desc()).limit(7).all()
    active_dates = sorted([r[0] for r in dates_query])
    
    heatmap_data = []
    for d in active_dates:
        day_name = d.strftime('%A')
        # Fetch the timetable entries for this day
        timetable_slots = TimetableEntry.query.filter_by(
            department_id=student.department_id,
            year=student.year,
            day_of_week=day_name
        ).order_by(TimetableEntry.period).all()
        slot_map = {slot.period: slot.subject for slot in timetable_slots}
        
        # Fetch actual attendance records for this date
        day_records = Attendance.query.filter_by(student_id=student_id, date=d).all()
        status_map = {r.period: r.status for r in day_records}
        
        period_data = []
        for period in range(1, 9):
            scheduled_subject = slot_map.get(period, 'Free Period')
            actual_status = status_map.get(period)
            
            # Determine visual class/status
            if actual_status:
                status = actual_status
            elif scheduled_subject == 'Lunch Break':
                status = 'lunch'
            else:
                status = 'free'
                
            period_data.append({
                'period': period,
                'subject': scheduled_subject,
                'status': status
            })
            
        heatmap_data.append({
            'date': d,
            'day_name': day_name,
            'periods': period_data
        })
        
    return render_template('students/view.html',
                           student=student,
                           attendance_records=attendance_records,
                           attendance_pct=attendance_pct,
                           subject_stats=subject_stats,
                           heatmap_data=heatmap_data)

@students_bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(student_id):
    # Students cannot edit any profile
    if current_user.role == 'student':
        flash('Access denied. Students cannot edit profiles.', 'danger')
        return redirect(url_for('students.view', student_id=current_user.student_id))
    
    student = Student.query.get_or_404(student_id)
    departments = Department.query.all()

    if request.method == 'POST':
        student.full_name = request.form.get('full_name', student.full_name).strip()
        student.email = request.form.get('email', student.email).strip()
        student.phone = request.form.get('phone', '').strip()
        student.department_id = int(request.form.get('department_id', student.department_id))
        student.year = int(request.form.get('year', student.year))
        student.section = request.form.get('section', '').strip().upper()
        student.address = request.form.get('address', '').strip()
        student.guardian_name = request.form.get('guardian_name', '').strip()
        student.guardian_phone = request.form.get('guardian_phone', '').strip()
        student.guardian_email = request.form.get('guardian_email', '').strip()
        student.cgpa = float(request.form.get('cgpa', 0.0))
        student.status = request.form.get('status', student.status)
        dob_str = request.form.get('dob', '')
        if dob_str:
            try:
                student.dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        student.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('students.view', student_id=student.id))

    return render_template('students/edit.html', student=student, departments=departments)

@students_bp.route('/<int:student_id>/delete', methods=['POST'])
@login_required
def delete(student_id):
    if current_user.role != 'admin':
        flash('Only admins can delete students.', 'danger')
        return redirect(url_for('students.index'))
    student = Student.query.get_or_404(student_id)
    name = student.full_name
    db.session.delete(student)
    db.session.commit()
    flash(f'Student {name} deleted successfully.', 'success')
    return redirect(url_for('students.index'))

@students_bp.route('/search-suggestions')
@login_required
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    results = Student.query.filter(
        db.or_(
            Student.full_name.ilike(f'%{q}%'),
            Student.roll_number.ilike(f'%{q}%')
        )
    ).limit(8).all()
    suggestions = [{'id': s.id, 'name': s.full_name, 'roll': s.roll_number} for s in results]
    return jsonify(suggestions)

@students_bp.route('/my-attendance')
@login_required
def my_attendance():
    if current_user.role != 'student':
        flash('Access denied. This page is only for students.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    student = Student.query.get_or_404(current_user.student_id)
    
    # Get filters from query parameters
    subject_filter = request.args.get('subject', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    query = Attendance.query.filter_by(student_id=student.id)
    
    if subject_filter:
        query = query.filter_by(subject=subject_filter)
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= start_date)
        except ValueError:
            pass
            
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= end_date)
        except ValueError:
            pass
            
    # Order by date descending, period ascending
    attendance_records = query.order_by(Attendance.date.desc(), Attendance.period.asc()).all()
    
    # Calculate stats
    total_records = len(attendance_records)
    present_count = sum(1 for r in attendance_records if r.status == 'present')
    absent_count = sum(1 for r in attendance_records if r.status == 'absent')
    late_count = sum(1 for r in attendance_records if r.status == 'late')
    
    # Late counts as attended
    attended_count = present_count + late_count
    attendance_pct = round((attended_count / total_records) * 100, 1) if total_records > 0 else 0.0
    
    # Get unique subjects for dropdown filter
    all_subjects_query = db.session.query(Attendance.subject).filter_by(student_id=student.id).distinct().all()
    unique_subjects = sorted([s[0] for s in all_subjects_query if s[0] not in ['Lunch Break', 'Free Period']])
    
    return render_template('students/my_attendance.html',
                           student=student,
                           attendance_records=attendance_records,
                           total_records=total_records,
                           present_count=present_count,
                           absent_count=absent_count,
                           late_count=late_count,
                           attendance_pct=attendance_pct,
                           unique_subjects=unique_subjects,
                           subject_filter=subject_filter,
                           start_date=start_date_str,
                           end_date=end_date_str)
