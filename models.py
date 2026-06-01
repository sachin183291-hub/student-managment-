from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='teacher')  # admin, teacher, student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_user = db.Column(db.Boolean, default=True)
    password_changed = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(10), default='light')

    # RBAC fields for Teachers
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    section = db.Column(db.String(5), nullable=True)

    # RBAC fields for Students
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    hod = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    students = db.relationship('Student', backref='department', lazy=True)

    def __repr__(self):
        return f'<Department {self.name}>'


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)  # 1, 2, 3, 4
    section = db.Column(db.String(5))
    dob = db.Column(db.Date)
    address = db.Column(db.Text)
    guardian_name = db.Column(db.String(120))
    guardian_phone = db.Column(db.String(15))
    guardian_email = db.Column(db.String(120))
    cgpa = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')  # active, inactive, graduated
    photo = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attendance_records = db.relationship('Attendance', backref='student', lazy=True, cascade='all, delete-orphan')

    def get_attendance_percentage(self, subject=None):
        query = Attendance.query.filter_by(student_id=self.id)
        if subject:
            query = query.filter_by(subject=subject)
        records = query.all()
        if not records:
            return 0.0
        present = sum(1 for r in records if r.status == 'present')
        return round((present / len(records)) * 100, 2)

    def __repr__(self):
        return f'<Student {self.roll_number}>'


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    period = db.Column(db.Integer, nullable=False, default=1)  # 1 to 8
    status = db.Column(db.String(10), nullable=False)  # present, absent, late
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(200))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'date', 'period', name='unique_attendance'),
    )

    def __repr__(self):
        return f'<Attendance {self.student_id} {self.date} Period {self.period}>'


class TimetableEntry(db.Model):
    __tablename__ = 'timetable'
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)  # 1, 2, 3, 4
    day_of_week = db.Column(db.String(20), nullable=False)  # Monday, Tuesday, etc.
    period = db.Column(db.Integer, nullable=False)  # 1 to 8
    subject = db.Column(db.String(100), nullable=False)  # Course Name

    __table_args__ = (
        db.UniqueConstraint('department_id', 'year', 'day_of_week', 'period', name='unique_timetable_slot'),
    )

    def __repr__(self):
        return f'<TimetableEntry {self.day_of_week} Year {self.year} Period {self.period} - {self.subject}>'


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ActivityLog {self.action}>'
