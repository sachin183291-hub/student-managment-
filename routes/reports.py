from flask import Blueprint, render_template, make_response, request
from flask_login import login_required, current_user
from extensions import db
from models import Student, Attendance, Department
from datetime import datetime, date, timedelta
from io import BytesIO
import io

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    departments = Department.query.all()
    return render_template('reports/index.html', departments=departments)

@reports_bp.route('/students')
@login_required
def students_report():
    dept_id = request.args.get('department', '')
    year = request.args.get('year', '')
    query = Student.query.filter_by(status='active')
    
    if current_user.role == 'teacher':
        dept_id = current_user.department_id
        year = current_user.year
        query = query.filter_by(department_id=dept_id, year=year)
        if current_user.section:
            query = query.filter_by(section=current_user.section)
    else:
        if dept_id:
            query = query.filter_by(department_id=int(dept_id))
        if year:
            query = query.filter_by(year=int(year))
            
    students = query.order_by(Student.roll_number).all()
    departments = Department.query.all()
    return render_template('reports/students.html', students=students, departments=departments,
                           dept_filter=dept_id, year_filter=year)

@reports_bp.route('/attendance')
@login_required
def attendance_report():
    query = Student.query.filter_by(status='active')
    if current_user.role == 'teacher':
        query = query.filter_by(department_id=current_user.department_id, year=current_user.year)
        if current_user.section:
            query = query.filter_by(section=current_user.section)
    students = query.order_by(Student.roll_number).all()
    report_data = []
    for s in students:
        pct = s.get_attendance_percentage()
        total_classes = len(s.attendance_records)
        present = sum(1 for r in s.attendance_records if r.status == 'present')
        report_data.append({
            'student': s,
            'pct': pct,
            'total': total_classes,
            'present': present,
            'absent': total_classes - present,
            'risk': 'High' if pct < 60 else ('Medium' if pct < 75 else 'Low')
        })
    report_data.sort(key=lambda x: x['pct'])
    return render_template('attendance/report.html', report_data=report_data)

@reports_bp.route('/download-pdf')
@login_required
def download_pdf():
    if not REPORTLAB_AVAILABLE:
        from flask import flash, redirect, url_for
        flash('PDF generation requires reportlab. Install with: pip install reportlab', 'warning')
        return redirect(url_for('reports.index'))

    report_type = request.args.get('type', 'students')
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    elements = []

    # Title style
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                  fontSize=20, spaceAfter=6,
                                  textColor=colors.HexColor('#4f46e5'))
    sub_style = ParagraphStyle('SubTitle', parent=styles['Normal'],
                                fontSize=11, spaceAfter=12,
                                textColor=colors.HexColor('#6b7280'), alignment=TA_CENTER)

    elements.append(Paragraph("Smart Student Management Portal", title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y, %I:%M %p')}", sub_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#4f46e5')))
    elements.append(Spacer(1, 0.2*inch))

    if report_type == 'students':
        elements.append(Paragraph("Student Directory Report", styles['Heading1']))
        elements.append(Spacer(1, 0.1*inch))

        query = Student.query.filter_by(status='active')
        if current_user.role == 'teacher':
            query = query.filter_by(department_id=current_user.department_id, year=current_user.year)
            if current_user.section:
                query = query.filter_by(section=current_user.section)
        students = query.order_by(Student.roll_number).all()
        data = [['#', 'Roll No', 'Name', 'Department', 'Year', 'CGPA', 'Status']]
        for i, s in enumerate(students, 1):
            data.append([
                str(i), s.roll_number, s.full_name,
                s.department.name if s.department else 'N/A',
                f'Year {s.year}', str(s.cgpa), s.status.title()
            ])

        col_widths = [0.4*inch, 1*inch, 2*inch, 1.8*inch, 0.7*inch, 0.6*inch, 0.7*inch]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(table)

    elif report_type == 'attendance':
        elements.append(Paragraph("Attendance Summary Report", styles['Heading1']))
        elements.append(Spacer(1, 0.1*inch))

        query = Student.query.filter_by(status='active')
        if current_user.role == 'teacher':
            query = query.filter_by(department_id=current_user.department_id, year=current_user.year)
            if current_user.section:
                query = query.filter_by(section=current_user.section)
        students = query.order_by(Student.roll_number).all()
        data = [['#', 'Roll No', 'Name', 'Department', 'Total', 'Present', 'Absent', 'Percentage', 'Risk']]
        for i, s in enumerate(students, 1):
            pct = s.get_attendance_percentage()
            total = len(s.attendance_records)
            present = sum(1 for r in s.attendance_records if r.status == 'present')
            risk = 'High' if pct < 60 else ('Medium' if pct < 75 else 'Low')
            data.append([
                str(i), s.roll_number, s.full_name,
                s.department.name if s.department else 'N/A',
                str(total), str(present), str(total - present),
                f'{pct:.1f}%', risk
            ])

        col_widths = [0.3*inch, 0.9*inch, 1.7*inch, 1.5*inch, 0.5*inch, 0.6*inch, 0.6*inch, 0.7*inch, 0.6*inch]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,1), (-1,-1), 7),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report_{date.today()}.pdf'
    return response
