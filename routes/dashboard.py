from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models import Student, Attendance, Department, ActivityLog
from datetime import datetime, timedelta, date
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    if current_user.role == 'teacher' and (current_user.department_id is None or current_user.year is None):
        return redirect(url_for('auth.teacher_setup'))

    # Base queries for RBAC
    student_query = Student.query.filter_by(status='active')
    attendance_query = Attendance.query
    log_query = ActivityLog.query
    
    if current_user.role == 'teacher':
        student_query = student_query.filter_by(department_id=current_user.department_id, year=current_user.year)
        if current_user.section:
            student_query = student_query.filter_by(section=current_user.section)
        
        # Get list of student IDs for this teacher
        teacher_student_ids = [s.id for s in student_query.all()]
        
        # Filter attendance to only these students
        if teacher_student_ids:
            attendance_query = attendance_query.filter(Attendance.student_id.in_(teacher_student_ids))
        else:
            # Prevent showing all attendance if teacher has no students
            attendance_query = attendance_query.filter(Attendance.student_id == -1)

    # Basic stats
    total_students = student_query.count()
    total_departments = Department.query.count() if current_user.role == 'admin' else 1
    today = date.today()

    # Attendance today
    today_attendance = attendance_query.filter_by(date=today).all()
    today_present = sum(1 for a in today_attendance if a.status == 'present')
    today_total = len(set(a.student_id for a in today_attendance))

    # Monthly attendance for chart (last 30 days)
    thirty_days_ago = today - timedelta(days=29)
    monthly_records = attendance_query.filter(
        Attendance.date >= thirty_days_ago,
        Attendance.date <= today
    ).all()

    # Group by date
    date_map = {}
    for r in monthly_records:
        ds = str(r.date)
        if ds not in date_map:
            date_map[ds] = {'present': 0, 'absent': 0, 'total': 0}
        date_map[ds]['total'] += 1
        if r.status == 'present':
            date_map[ds]['present'] += 1
        else:
            date_map[ds]['absent'] += 1

    chart_labels = []
    chart_present = []
    chart_absent = []
    for i in range(30):
        d = thirty_days_ago + timedelta(days=i)
        ds = str(d)
        chart_labels.append(d.strftime('%d %b'))
        chart_present.append(date_map.get(ds, {}).get('present', 0))
        chart_absent.append(date_map.get(ds, {}).get('absent', 0))

    # Department-wise student count
    if current_user.role == 'admin':
        dept_data = db.session.query(
            Department.name, func.count(Student.id)
        ).join(Student, Department.id == Student.department_id, isouter=True) \
         .group_by(Department.name).all()
        dept_labels = [d[0] for d in dept_data]
        dept_counts = [d[1] for d in dept_data]
    else:
        # Teacher: just show their own department's count
        dept_obj = Department.query.get(current_user.department_id)
        dept_labels = [dept_obj.name] if dept_obj else ["Your Dept"]
        dept_counts = [total_students]

    # Year-wise students
    if current_user.role == 'admin':
        year_data = db.session.query(Student.year, func.count(Student.id)) \
            .filter(Student.status == 'active') \
            .group_by(Student.year).order_by(Student.year).all()
        year_labels = [f'Year {y[0]}' for y in year_data]
        year_counts = [y[1] for y in year_data]
    else:
        # Teacher: just show their own year
        year_labels = [f'Year {current_user.year}']
        year_counts = [total_students]

    # Low attendance students (< 75%)
    all_students = student_query.all()
    low_attendance = []
    for s in all_students:
        pct = s.get_attendance_percentage()
        if pct < 75 and pct > 0:
            low_attendance.append({'student': s, 'pct': pct})
    low_attendance.sort(key=lambda x: x['pct'])

    # Recent activities
    if current_user.role == 'admin':
        recent_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
    else:
        recent_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(10).all()

    # Recent students
    recent_students = student_query.order_by(Student.created_at.desc()).limit(5).all()

    return render_template('dashboard/index.html',
        total_students=total_students,
        total_departments=total_departments,
        today_present=today_present,
        today_total=today_total,
        chart_labels=chart_labels,
        chart_present=chart_present,
        chart_absent=chart_absent,
        dept_labels=dept_labels,
        dept_counts=dept_counts,
        year_labels=year_labels,
        year_counts=year_counts,
        low_attendance=low_attendance[:5],
        recent_logs=recent_logs,
        recent_students=recent_students,
        today=today
    )
