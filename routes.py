import os
import uuid
from datetime import date, datetime
from functools import wraps

import qrcode
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, current_app, send_file)
from models import db, Course, Student, CheckIn, Assessment, BadgeTemplate, StudentBadge
from sqlalchemy import func

fitness_bp = Blueprint('fitness', __name__)

# ── 教练认证 ──────────────────────────────────────

def coach_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('coach_ok'):
            return redirect(url_for('fitness.coach_login'))
        return f(*args, **kwargs)
    return decorated


def check_auto_badges(student):
    """每次打卡后检查自动奖章"""
    count = student.total_checkins
    streak = student.streak_days

    # 出勤次数奖章
    badges = BadgeTemplate.query.filter(
        BadgeTemplate.trigger_type == 'attendance_count',
        BadgeTemplate.trigger_value <= count
    ).all()

    # 连续出勤奖章
    streak_badges = BadgeTemplate.query.filter(
        BadgeTemplate.trigger_type == 'streak_days',
        BadgeTemplate.trigger_value <= streak
    ).all()

    awarded = 0
    for bt in badges + streak_badges:
        exists = StudentBadge.query.filter_by(
            student_id=student.id, badge_template_id=bt.id
        ).first()
        if not exists:
            db.session.add(StudentBadge(
                student_id=student.id, badge_template_id=bt.id
            ))
            awarded += 1
    if awarded:
        db.session.commit()
    return awarded


# ── 二维码工具 ─────────────────────────────────────

def generate_qr(data, filename):
    d = os.path.join(current_app.root_path, 'static', 'uploads', 'qrcodes')
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, filename)
    if not os.path.exists(fp):
        qr = qrcode.make(data)
        qr.save(fp)
    return f'/static/uploads/qrcodes/{filename}'


# ═══════════════════════════════════════════════════
# 家长端（无需登录）
# ═══════════════════════════════════════════════════

@fitness_bp.route('/c/<int:course_id>')
def parent_checkin(course_id):
    """扫 SOP 课程码 → 打卡页"""
    course = Course.query.get_or_404(course_id)
    students = Student.query.filter_by(
        is_active=True, age_group=course.age_group
    ).order_by(Student.name).all()
    return render_template('parent/checkin.html', course=course, students=students)


@fitness_bp.route('/c/<int:course_id>/do', methods=['POST'])
def parent_checkin_do(course_id):
    """执行打卡"""
    course = Course.query.get_or_404(course_id)
    student_id = request.form.get('student_id')
    student_name = request.form.get('student_name', '').strip()

    if student_id:
        student = Student.query.get(int(student_id))
    elif student_name:
        student = Student.query.filter_by(name=student_name, is_active=True).first()
    else:
        return jsonify({'ok': False, 'msg': '请选择或输入孩子姓名'})

    if not student:
        return jsonify({'ok': False, 'msg': f'未找到学员: {student_name}'})

    ci = CheckIn(student_id=student.id, course_id=course.id)
    db.session.add(ci)
    db.session.commit()

    # 检查自动奖章
    new_badges = check_auto_badges(student)

    return jsonify({
        'ok': True,
        'student_name': student.name,
        'total': student.total_checkins,
        'new_badges': new_badges
    })


@fitness_bp.route('/p/<access_code>')
def parent_home(access_code):
    """扫学员个人码 → 孩子主页"""
    student = Student.query.filter_by(access_code=access_code).first_or_404()

    # 出勤统计
    checkins = student.checkins.order_by(CheckIn.checkin_time.desc()).limit(60).all()
    checkin_count = student.total_checkins
    streak = student.streak_days

    # 本月出勤天数
    today = date.today()
    first_of_month = today.replace(day=1)
    this_month_count = student.checkins.filter(
        func.date(CheckIn.checkin_time) >= first_of_month
    ).count()

    # 最近一次评估
    latest_assessment = student.assessments.first()

    # 奖章
    badges = student.badges.all()

    # 评估数据给 Chart.js
    assessments = student.assessments.order_by(Assessment.date.asc()).all()
    chart_data = {
        'labels': [a.date.strftime('%m/%d') for a in assessments],
        'rope_skip': [a.rope_skip for a in assessments],
        'seated_forward_bend': [a.seated_forward_bend for a in assessments],
        'standing_long_jump': [a.standing_long_jump for a in assessments],
        'shuttle_run': [a.shuttle_run for a in assessments],
        'sit_up': [a.sit_up for a in assessments],
    }

    return render_template('parent/home.html',
                           student=student,
                           checkins=checkins,
                           checkin_count=checkin_count,
                           streak=streak,
                           this_month_count=this_month_count,
                           latest_assessment=latest_assessment,
                           badges=badges,
                           chart_data=chart_data,
                           now=datetime.now())


# ═══════════════════════════════════════════════════
# 教练端 认证
# ═══════════════════════════════════════════════════

@fitness_bp.route('/login', methods=['GET', 'POST'])
def coach_login():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == current_app.config['FITNESS_COACH_PASSWORD']:
            session['coach_ok'] = True
            return redirect(url_for('fitness.coach_dashboard'))
        return render_template('coach/login.html', error='密码错误')
    return render_template('coach/login.html')


@fitness_bp.route('/logout')
def coach_logout():
    session.pop('coach_ok', None)
    return redirect(url_for('fitness.coach_login'))


# ═══════════════════════════════════════════════════
# 教练端 首页 + 今日课程
# ═══════════════════════════════════════════════════

@fitness_bp.route('/')
@coach_required
def coach_dashboard():
    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()
    courses = Course.query.filter_by(is_active=True).order_by(Course.age_group, Course.name).all()

    # 今日打卡数
    today = date.today()
    today_count = CheckIn.query.filter(
        func.date(CheckIn.checkin_time) == today
    ).count()

    return render_template('coach/dashboard.html',
                           students=students, courses=courses,
                           today_count=today_count)


@fitness_bp.route('/today')
@coach_required
def coach_today():
    course_id = request.args.get('course_id', type=int)
    course = None
    qr_path = None
    today_checkins = []

    if course_id:
        course = Course.query.get_or_404(course_id)
        base = current_app.config['PUBLIC_BASE_URL']
        url = f'{base}/c/{course.id}'
        qr_path = generate_qr(url, f'course_{course.id}.png')

        today_checkins = CheckIn.query.filter(
            CheckIn.course_id == course_id,
            func.date(CheckIn.checkin_time) == date.today()
        ).all()

    courses = Course.query.filter_by(is_active=True).order_by(
        Course.age_group, Course.name).all()

    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()

    return render_template('coach/today.html',
                           courses=courses, course=course,
                           qr_path=qr_path, today_checkins=today_checkins,
                           students=students)


@fitness_bp.route('/today/checkin', methods=['POST'])
@coach_required
def coach_manual_checkin():
    """教练手动补打卡"""
    student_id = request.form.get('student_id', type=int)
    course_id = request.form.get('course_id', type=int)
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)
    ci = CheckIn(student_id=student.id, course_id=course.id)
    db.session.add(ci)
    db.session.commit()
    check_auto_badges(student)
    return jsonify({'ok': True, 'student_name': student.name})


# ═══════════════════════════════════════════════════
# 教练端 学员管理
# ═══════════════════════════════════════════════════

@fitness_bp.route('/students')
@coach_required
def coach_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('coach/students.html', students=students)


@fitness_bp.route('/students/new', methods=['GET', 'POST'])
@coach_required
def coach_student_new():
    if request.method == 'POST':
        s = Student(
            name=request.form['name'].strip(),
            age_group=request.form['age_group'],
            notes=request.form.get('notes', ''),
            avatar_emoji=request.form.get('avatar_emoji', '🧒')
        )
        db.session.add(s)
        db.session.commit()

        # 生成个人二维码
        base = current_app.config['PUBLIC_BASE_URL']
        url = f'{base}/p/{s.access_code}'
        generate_qr(url, f'student_{s.access_code}.png')

        return redirect(url_for('fitness.coach_students'))
    return render_template('coach/student_form.html', student=None)


@fitness_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@coach_required
def coach_student_edit(student_id):
    s = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        s.name = request.form['name'].strip()
        s.age_group = request.form['age_group']
        s.notes = request.form.get('notes', '')
        s.avatar_emoji = request.form.get('avatar_emoji', '🧒')
        s.is_active = 'is_active' in request.form
        db.session.commit()
        return redirect(url_for('fitness.coach_students'))
    return render_template('coach/student_form.html', student=s)


@fitness_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@coach_required
def coach_student_delete(student_id):
    s = Student.query.get_or_404(student_id)
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for('fitness.coach_students'))


@fitness_bp.route('/students/<int:student_id>')
@coach_required
def coach_student_detail(student_id):
    s = Student.query.get_or_404(student_id)
    checkins = s.checkins.limit(50).all()
    assessments = s.assessments.all()
    badges = s.badges.all()

    base = current_app.config['PUBLIC_BASE_URL']
    qr_path = f'/static/uploads/qrcodes/student_{s.access_code}.png'

    badge_templates = BadgeTemplate.query.filter_by(is_active=True).all()

    return render_template('coach/student_detail.html',
                           student=s, checkins=checkins,
                           assessments=assessments, badges=badges,
                           qr_path=qr_path, base_url=base,
                           badge_templates=badge_templates)


# ═══════════════════════════════════════════════════
# 教练端 评估
# ═══════════════════════════════════════════════════

@fitness_bp.route('/students/<int:student_id>/assessment', methods=['GET', 'POST'])
@coach_required
def coach_assessment(student_id):
    s = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        a = Assessment(
            student_id=s.id,
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            seated_forward_bend=request.form.get('seated_forward_bend', type=float),
            standing_long_jump=request.form.get('standing_long_jump', type=float),
            shuttle_run=request.form.get('shuttle_run', type=float),
            rope_skip=request.form.get('rope_skip', type=int),
            sit_up=request.form.get('sit_up', type=int),
            balance_score=request.form.get('balance_score', type=float),
            posture_notes=request.form.get('posture_notes', ''),
            overall_notes=request.form.get('overall_notes', '')
        )
        db.session.add(a)
        db.session.commit()
        return redirect(url_for('fitness.coach_student_detail', student_id=s.id))
    return render_template('coach/assessment_form.html', student=s, today=date.today())


@fitness_bp.route('/assessments/<int:assessment_id>/delete', methods=['POST'])
@coach_required
def coach_assessment_delete(assessment_id):
    a = Assessment.query.get_or_404(assessment_id)
    sid = a.student_id
    db.session.delete(a)
    db.session.commit()
    return redirect(url_for('fitness.coach_student_detail', student_id=sid))


# ═══════════════════════════════════════════════════
# 教练端 奖章
# ═══════════════════════════════════════════════════

@fitness_bp.route('/students/<int:student_id>/badge', methods=['POST'])
@coach_required
def coach_award_badge(student_id):
    s = Student.query.get_or_404(student_id)
    badge_id = request.form.get('badge_template_id', type=int)
    bt = BadgeTemplate.query.get_or_404(badge_id)

    exists = StudentBadge.query.filter_by(
        student_id=s.id, badge_template_id=bt.id
    ).first()
    if not exists:
        db.session.add(StudentBadge(student_id=s.id, badge_template_id=bt.id))
        db.session.commit()
    return redirect(url_for('fitness.coach_student_detail', student_id=s.id))


# ═══════════════════════════════════════════════════
# 教练端 课程管理
# ═══════════════════════════════════════════════════

@fitness_bp.route('/courses')
@coach_required
def coach_courses():
    courses = Course.query.order_by(Course.age_group, Course.name).all()
    return render_template('coach/courses.html', courses=courses)


@fitness_bp.route('/courses/<int:course_id>/qr')
@coach_required
def coach_course_qr(course_id):
    course = Course.query.get_or_404(course_id)
    base = current_app.config['PUBLIC_BASE_URL']
    url = f'{base}/c/{course.id}'
    qr_path = generate_qr(url, f'course_{course.id}.png')
    return render_template('coach/course_qr.html', course=course, qr_path=qr_path)
