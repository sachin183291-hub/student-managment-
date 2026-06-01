from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Student, Attendance, Department, TimetableEntry
from datetime import datetime, date

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

SUBJECTS = ['Mathematics', 'Physics', 'Chemistry', 'Computer Science',
            'English', 'Data Structures', 'Algorithms', 'Database Systems',
            'Software Engineering', 'Networks', 'Operating Systems', 'Machine Learning']

@attendance_bp.route('/')
@login_required
def index():
    departments = Department.query.all()
    today = date.today()
    return render_template('attendance/index.html', departments=departments, today=today, subjects=SUBJECTS)

@attendance_bp.route('/mark', methods=['GET', 'POST'])
@login_required
def mark():
    if current_user.role == 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))
        
    departments = Department.query.all()
    today = date.today()
    
    if request.method == 'POST':
        dept_id = request.form.get('department_id', type=int)
        year = request.form.get('year', type=int)
        subject = request.form.get('subject')
        period = request.form.get('period', type=int)
        att_date_str = request.form.get('date')
        
        if not all([dept_id, year, subject, period, att_date_str]):
            flash('Missing required fields.', 'danger')
            return render_template('attendance/mark.html', departments=departments, subjects=SUBJECTS, today=today)

        try:
            att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date()
        except:
            flash('Invalid date format.', 'danger')
            return render_template('attendance/mark.html', departments=departments, subjects=SUBJECTS, today=today)

        students_query = Student.query.filter_by(
            department_id=dept_id,
            year=year,
            status='active'
        )
        if current_user.role == 'teacher' and current_user.section:
            students_query = students_query.filter_by(section=current_user.section)
        students = students_query.all()

        records_added = 0
        records_updated = 0
        for student in students:
            status = request.form.get(f'status_{student.id}', 'absent')
            existing = Attendance.query.filter_by(
                student_id=student.id,
                date=att_date,
                period=period
            ).first()

            if existing:
                existing.status = status
                existing.subject = subject # Keep subject in sync with timetable
                existing.marked_by = current_user.id
                records_updated += 1
            else:
                record = Attendance(
                    student_id=student.id,
                    date=att_date,
                    period=period,
                    subject=subject,
                    status=status,
                    marked_by=current_user.id
                )
                db.session.add(record)
                records_added += 1

        db.session.commit()
        flash(f'Attendance marked for Period {period} ({subject})! {records_added} new, {records_updated} updated.', 'success')
        return redirect(url_for('attendance.view'))

    return render_template('attendance/mark.html', departments=departments, subjects=SUBJECTS, today=today)

@attendance_bp.route('/timetable-slots')
@login_required
def timetable_slots():
    dept_id = request.args.get('department_id', type=int)
    year = request.args.get('year', type=int)
    date_str = request.args.get('date')
    
    if not dept_id or not year or not date_str:
        return jsonify([])
        
    try:
        att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = att_date.strftime('%A')
    except Exception as e:
        return jsonify({'error': 'Invalid date format.'}), 400
        
    # Fetch schedule for this day
    entries = TimetableEntry.query.filter_by(
        department_id=dept_id,
        year=year,
        day_of_week=day_name
    ).order_by(TimetableEntry.period).all()
    
    # Check which periods have already been marked for this date
    marked_periods = db.session.query(Attendance.period).join(Student).filter(
        Student.department_id == dept_id,
        Student.year == year,
        Attendance.date == att_date
    ).distinct().all()
    marked_set = {r[0] for r in marked_periods}
    
    slots_data = []
    for entry in entries:
        slots_data.append({
            'period': entry.period,
            'subject': entry.subject,
            'marked': entry.period in marked_set
        })
        
    return jsonify(slots_data)

@attendance_bp.route('/get-students')
@login_required
def get_students():
    dept_id = request.args.get('department_id', type=int)
    year = request.args.get('year', type=int)
    date_str = request.args.get('date')
    period = request.args.get('period', type=int)
    
    if not dept_id or not year:
        return jsonify([])
        
    students_query = Student.query.filter_by(
        department_id=dept_id,
        year=year,
        status='active'
    )
    if current_user.role == 'teacher' and current_user.section:
        students_query = students_query.filter_by(section=current_user.section)
    students = students_query.all()
    
    status_map = {}
    if date_str and period:
        try:
            att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            records = Attendance.query.filter_by(date=att_date, period=period).all()
            status_map = {r.student_id: r.status for r in records}
        except Exception as e:
            print("Error loading existing attendance for get-students:", e)
            
    return jsonify([{
        'id': s.id, 
        'name': s.full_name, 
        'roll': s.roll_number,
        'status': status_map.get(s.id, 'present')
    } for s in students])

@attendance_bp.route('/view')
@login_required
def view():
    if current_user.role == 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('students.view', student_id=current_user.student_id))

    if current_user.role == 'teacher':
        dept_filter = current_user.department_id
        # Optional: restrict to their department only
    else:
        dept_filter = request.args.get('department', '')
        
    subject_filter = request.args.get('subject', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = db.session.query(Attendance, Student).join(Student, Attendance.student_id == Student.id)
    
    if current_user.role == 'teacher':
        query = query.filter(Student.department_id == current_user.department_id, Student.year == current_user.year)
        if current_user.section:
            query = query.filter(Student.section == current_user.section)


    if dept_filter:
        query = query.filter(Student.department_id == int(dept_filter))
    if subject_filter:
        query = query.filter(Attendance.subject == subject_filter)
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= df)
        except:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= dt)
        except:
            pass

    records = query.order_by(Attendance.date.desc()).limit(200).all()
    departments = Department.query.all()

    return render_template('attendance/view.html',
                           records=records,
                           departments=departments,
                           subjects=SUBJECTS,
                           dept_filter=dept_filter,
                           subject_filter=subject_filter,
                           date_from=date_from,
                           date_to=date_to)

@attendance_bp.route('/report')
@login_required
def report():
    students = Student.query.filter_by(status='active').order_by(Student.roll_number).all()
    report_data = []
    for s in students:
        pct = s.get_attendance_percentage()
        report_data.append({
            'student': s,
            'pct': pct,
            'status': 'Good' if pct >= 75 else ('Warning' if pct >= 60 else 'Critical')
        })
    return render_template('attendance/report.html', report_data=report_data)
