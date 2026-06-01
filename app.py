from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db, login_manager
from models import User
import os

def create_app():
    app = Flask(__name__)
    
    # Fix for Vercel/Reverse Proxies to correctly generate HTTPS URLs and handle redirects
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Configuration
    app.config['SECRET_KEY'] = 'smart_student_portal_secret_2024_#@!'
    
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    elif os.environ.get('VERCEL') == '1':
        # Vercel has a read-only filesystem except for /tmp
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/students.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    
    # Email Configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
    app.config['MAIL_PASSWORD'] = 'your_app_password'
    app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.students import students_bp
    from routes.dashboard import dashboard_bp
    from routes.attendance import attendance_bp
    from routes.reports import reports_bp
    from routes.api import api_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Force teacher setup if not configured
    @app.before_request
    def force_teacher_setup():
        from flask import request, redirect, url_for
        from flask_login import current_user
        
        if current_user.is_authenticated:
            if current_user.role == 'student' and not current_user.password_changed:
                allowed_endpoints = ['auth.force_password_change', 'auth.logout', 'auth.set_theme', 'static']
                if request.endpoint not in allowed_endpoints and not request.path.startswith('/static/'):
                    return redirect(url_for('auth.force_password_change'))

            if current_user.role == 'teacher':
                # Allow access to setup page, logout, theme switching, and static assets
                allowed_endpoints = ['auth.teacher_setup', 'auth.logout', 'auth.set_theme', 'static']
                if request.endpoint not in allowed_endpoints and not request.path.startswith('/static/'):
                    if current_user.department_id is None or current_user.year is None or not current_user.section:
                        return redirect(url_for('auth.teacher_setup'))

    # Jinja2 globals
    from datetime import datetime as _dt
    @app.context_processor
    def inject_globals():
        return dict(now=_dt.utcnow, min=min, max=max)

    # Create tables
    with app.app_context():
        # Check if schema needs re-initialization (e.g., if 'period' column is missing in 'attendance' table)
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if inspector.has_table('users'):
            user_columns = [c['name'] for c in inspector.get_columns('users')]
            if 'password_changed' not in user_columns:
                print("Outdated user schema detected. Re-initializing database...")
                db.drop_all()
        elif inspector.has_table('attendance'):
            columns = [c['name'] for c in inspector.get_columns('attendance')]
            if 'period' not in columns:
                print("Outdated schema detected. Re-initializing database...")
                db.drop_all()

        db.create_all()
        
        # Create default admin user if not exists
        from models import User
        if not User.query.filter_by(username='admin').first():
            from werkzeug.security import generate_password_hash
            admin = User(
                username='admin',
                email='admin@studentportal.com',
                password_hash=generate_password_hash('Admin@123'),
                role='admin',
                full_name='Administrator',
                password_changed=True
            )
            db.session.add(admin)
            db.session.commit()

        # Auto-seed all default college departments if none exist
        from models import Department
        if not Department.query.first():
            default_depts = [
                ('Computer Science Engineering', 'CSE', 'Dr. Arul Prasad'),
                ('Information Technology', 'IT', 'Dr. Priya Mani'),
                ('Electronics & Communication Engineering', 'ECE', 'Dr. Sundar Rajan'),
                ('Electrical & Electronics Engineering', 'EEE', 'Dr. Meenakshi'),
                ('Mechanical Engineering', 'ME', 'Dr. Rajesh Kumar'),
                ('Civil Engineering', 'CE', 'Dr. Anand Selvam'),
                ('Artificial Intelligence & Data Science', 'AI & DS', 'Dr. Kavitha S.'),
                ('Chemical Engineering', 'CHEM', 'Dr. Vignesh V.')
            ]
            for name, code, hod in default_depts:
                dept = Department(name=name, code=code, hod=hod)
                db.session.add(dept)
            db.session.commit()

        # Auto-seed full 8-period timetables for all departments and all years
        from models import TimetableEntry
        if not TimetableEntry.query.first():
            print("Auto-seeding weekly 8-period timetables...")
            departments = Department.query.all()
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            
            DEPT_SUBJECTS = {
                'CSE': ['Data Structures', 'Algorithms', 'Database Systems', 'Software Engineering', 'Networks', 'Operating Systems', 'Machine Learning', 'Mathematics'],
                'IT': ['Database Systems', 'Web Technology', 'Networks', 'Algorithms', 'Software Engineering', 'Cloud Computing', 'Mathematics', 'English'],
                'ECE': ['Digital Electronics', 'Signals & Systems', 'Microprocessors', 'Embedded Systems', 'Networks', 'Mathematics', 'Physics', 'Chemistry'],
                'EEE': ['Electrical Machines', 'Power Systems', 'Control Systems', 'Power Electronics', 'Mathematics', 'Physics', 'Chemistry', 'English'],
            }
            DEFAULT_SUBJECTS = ['Mathematics', 'Physics', 'Chemistry', 'Computer Science', 'English', 'Data Structures', 'Algorithms', 'Database Systems']

            for dept in departments:
                subj_list = DEPT_SUBJECTS.get(dept.code, DEFAULT_SUBJECTS)
                for year in [1, 2, 3, 4]:
                    for day_idx, day in enumerate(days):
                        for period in range(1, 9):
                            # Choose standard subject with rotation
                            subj_idx = (year + day_idx * 2 + period) % len(subj_list)
                            subject = subj_list[subj_idx]
                            
                            # Add some labs or free periods for realism
                            if period == 4:
                                subject = 'Lunch Break'
                            elif period == 8:
                                subject = 'Library / Seminar'
                            elif period in [5, 6] and day_idx % 2 == 0:
                                subject = subj_list[subj_idx] + ' Lab'
                                
                            entry = TimetableEntry(
                                department_id=dept.id,
                                year=year,
                                day_of_week=day,
                                period=period,
                                subject=subject
                            )
                            db.session.add(entry)
            db.session.commit()

        # Auto-seed sample students and timetable-based attendance records
        from models import Student
        if not Student.query.first():
            print("Auto-seeding sample students and rich attendance records...")
            import random
            from datetime import date, timedelta
            
            # Helper to query department IDs
            dept_map = {d.code: d.id for d in Department.query.all()}
            
            student_data = [
                ('Aarav Sharma', 'CSE', 1, 'A', '2024CSE001'),
                ('Priya Patel', 'CSE', 2, 'A', '2023CSE002'),
                ('Rohan Verma', 'CSE', 3, 'B', '2022CSE003'),
                ('Sneha Gupta', 'CSE', 4, 'B', '2021CSE004'),
                ('Arjun Kumar', 'IT', 1, 'A', '2024IT001'),
                ('Deepika Singh', 'IT', 2, 'A', '2023IT002'),
                ('Rahul Nair', 'IT', 3, 'B', '2022IT003'),
                ('Ananya Reddy', 'IT', 4, 'B', '2021IT004'),
                ('Vikram Joshi', 'ECE', 1, 'A', '2024ECE001'),
                ('Kavya Mehta', 'ECE', 2, 'A', '2023ECE002'),
                ('Siddharth Das', 'ECE', 3, 'B', '2022ECE003'),
                ('Pooja Iyer', 'ECE', 4, 'B', '2021ECE004'),
                ('Aditya Rao', 'EEE', 1, 'A', '2024EEE001'),
                ('Ishita Kapoor', 'EEE', 2, 'A', '2023EEE002'),
                ('Nikhil Malhotra', 'EEE', 3, 'B', '2022EEE003'),
                ('Shreya Pandey', 'EEE', 4, 'B', '2021EEE004'),
                ('Kartik Bajaj', 'ME', 1, 'A', '2024ME001'),
                ('Tanvi Shah', 'ME', 2, 'A', '2023ME002'),
                ('Yash Agarwal', 'ME', 3, 'B', '2022ME003'),
                ('Divya Saxena', 'ME', 4, 'B', '2021ME004')
            ]
            
            created_students = []
            for name, dept_code, year, sec, roll in student_data:
                email = name.lower().replace(' ', '.') + '@college.edu'
                s = Student(
                    roll_number=roll,
                    full_name=name,
                    email=email,
                    phone=f'9{random.randint(100000000, 999999999)}',
                    department_id=dept_map[dept_code],
                    year=year,
                    section=sec,
                    cgpa=round(random.uniform(6.5, 9.7), 2),
                    status='active',
                    guardian_name=f'Mr. {name.split()[1]} Sr.'
                )
                db.session.add(s)
                created_students.append(s)
            db.session.flush() # populated student IDs

            # Pre-seed rich attendance records for the last 5 days
            from models import Attendance
            from datetime import datetime as dt
            days_to_seed = []
            curr_date = date.today()
            
            # Go back and find the last 5 days that are not Sundays
            while len(days_to_seed) < 5:
                curr_date -= timedelta(days=1)
                if curr_date.weekday() != 6: # not Sunday
                    days_to_seed.append(curr_date)
            
            admin_id = User.query.filter_by(username='admin').first().id
            
            print(f"Pre-seeding attendance records for days: {days_to_seed}")
            for d in days_to_seed:
                day_name = d.strftime('%A')
                for s in created_students:
                    # Get the timetable slots for this student's department, year, and day of week
                    slots = TimetableEntry.query.filter_by(
                        department_id=s.department_id,
                        year=s.year,
                        day_of_week=day_name
                    ).all()
                    
                    for slot in slots:
                        # Skip Lunch Break and Free periods from attendance tracking (or track them as present/free)
                        if slot.subject in ['Lunch Break', 'Free Period']:
                            continue
                            
                        # Weighted status: 85% present, 10% absent, 5% late
                        status_weight = random.random()
                        if status_weight < 0.85:
                            status = 'present'
                        elif status_weight < 0.95:
                            status = 'absent'
                        else:
                            status = 'late'
                            
                        att = Attendance(
                            student_id=s.id,
                            date=d,
                            period=slot.period,
                            subject=slot.subject,
                            status=status,
                            marked_by=admin_id
                        )
                        db.session.add(att)
            db.session.commit()
            
            # Auto-seed RBAC users (Teacher and Student)
            if not User.query.filter_by(role='teacher').first():
                from werkzeug.security import generate_password_hash
                # Teacher for CSE Year 1 Section A
                teacher_cse = User(
                    username='teacher_cse',
                    email='teacher.cse@college.edu',
                    password_hash=generate_password_hash('Teacher@123'),
                    role='teacher',
                    full_name='Dr. Smith (CSE)',
                    password_changed=True,
                    department_id=dept_map['CSE'],
                    year=1,
                    section='A'
                )
                db.session.add(teacher_cse)
                db.session.commit()
                print("Seeded sample Teacher user.")

            # Ensure all students have a corresponding User login account
            from models import Student
            from werkzeug.security import generate_password_hash
            all_students = Student.query.all()
            seeded_student_users = 0
            for s in all_students:
                if not User.query.filter_by(student_id=s.id).first():
                    stu_user = User(
                        username=s.roll_number,
                        email=s.email,
                        password_hash=generate_password_hash(s.roll_number),
                        role='student',
                        full_name=s.full_name,
                        student_id=s.id,
                        password_changed=False
                    )
                    db.session.add(stu_user)
                    seeded_student_users += 1
            if seeded_student_users > 0:
                db.session.commit()
                print(f"Auto-created {seeded_student_users} student login accounts.")

            print("Successfully seeded all database items!")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
