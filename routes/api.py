from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Student, Attendance, Department, User
from datetime import datetime, date

api_bp = Blueprint('api', __name__)

# Public endpoint to check user role (for login form)
@api_bp.route('/check-user-role/<username>', methods=['GET'])
def check_user_role(username):
    """Check if a user exists and return their role"""
    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'success': True, 'role': user.role, 'exists': True})
    return jsonify({'success': False, 'role': None, 'exists': False})

def student_to_dict(s):
    return {
        'id': s.id,
        'roll_number': s.roll_number,
        'full_name': s.full_name,
        'email': s.email,
        'phone': s.phone,
        'department': s.department.name if s.department else None,
        'year': s.year,
        'section': s.section,
        'cgpa': s.cgpa,
        'status': s.status,
        'attendance_percentage': s.get_attendance_percentage(),
        'created_at': s.created_at.isoformat() if s.created_at else None
    }

@api_bp.route('/students', methods=['GET'])
@login_required
def get_students():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    dept = request.args.get('department', '')

    query = Student.query
    if search:
        query = query.filter(
            db.or_(
                Student.full_name.ilike(f'%{search}%'),
                Student.roll_number.ilike(f'%{search}%')
            )
        )
    if dept:
        query = query.join(Department).filter(Department.name.ilike(f'%{dept}%'))

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'success': True,
        'data': [student_to_dict(s) for s in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page
    })

@api_bp.route('/students/<int:student_id>', methods=['GET'])
@login_required
def get_student(student_id):
    student = Student.query.get_or_404(student_id)
    return jsonify({'success': True, 'data': student_to_dict(student)})

@api_bp.route('/students', methods=['POST'])
@login_required
def create_student():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

    required = ['roll_number', 'full_name', 'email', 'department_id', 'year']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400

    if Student.query.filter_by(roll_number=data['roll_number']).first():
        return jsonify({'success': False, 'error': 'Roll number already exists'}), 409

    student = Student(
        roll_number=data['roll_number'].upper(),
        full_name=data['full_name'],
        email=data['email'],
        phone=data.get('phone', ''),
        department_id=data['department_id'],
        year=data['year'],
        section=data.get('section', ''),
        cgpa=data.get('cgpa', 0.0),
        status=data.get('status', 'active')
    )
    db.session.add(student)
    db.session.commit()
    return jsonify({'success': True, 'data': student_to_dict(student), 'message': 'Student created'}), 201

@api_bp.route('/students/<int:student_id>', methods=['PUT'])
@login_required
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No JSON data provided'}), 400

    for field in ['full_name', 'email', 'phone', 'year', 'section', 'cgpa', 'status']:
        if field in data:
            setattr(student, field, data[field])
    if 'department_id' in data:
        student.department_id = data['department_id']

    student.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'data': student_to_dict(student), 'message': 'Student updated'})

@api_bp.route('/students/<int:student_id>', methods=['DELETE'])
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Student deleted'})

@api_bp.route('/departments', methods=['GET'])
@login_required
def get_departments():
    departments = Department.query.all()
    return jsonify({
        'success': True,
        'data': [{'id': d.id, 'name': d.name, 'code': d.code, 'hod': d.hod} for d in departments]
    })

@api_bp.route('/attendance/stats', methods=['GET'])
@login_required
def attendance_stats():
    student_id = request.args.get('student_id', type=int)
    if not student_id:
        return jsonify({'success': False, 'error': 'student_id required'}), 400
    student = Student.query.get_or_404(student_id)
    records = student.attendance_records
    total = len(records)
    present = sum(1 for r in records if r.status == 'present')
    absent = total - present
    pct = round((present / total * 100), 2) if total else 0.0
    return jsonify({
        'success': True,
        'data': {
            'student': student.full_name,
            'roll_number': student.roll_number,
            'total_classes': total,
            'present': present,
            'absent': absent,
            'percentage': pct
        }
    })

@api_bp.route('/dashboard/stats', methods=['GET'])
@login_required
def dashboard_stats():
    total = Student.query.filter_by(status='active').count()
    today = date.today()
    today_records = Attendance.query.filter_by(date=today).all()
    present_today = sum(1 for r in today_records if r.status == 'present')
    dept_count = Department.query.count()
    return jsonify({
        'success': True,
        'data': {
            'total_students': total,
            'departments': dept_count,
            'present_today': present_today,
            'date': str(today)
        }
    })
