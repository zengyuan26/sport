import math
import os
import uuid
import random
from collections import Counter
from datetime import date, datetime, timedelta
from functools import wraps

import qrcode
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, current_app, send_file)
from models import (db, Course, Student, CheckIn, Assessment, BadgeTemplate,
                    StudentBadge, Photo, Booking, ContentLog, Setting,
                    ATTR_ICONS, ATTR_NAMES, RANK_TIERS)
from share_hooks import get_share_hook
from sqlalchemy import func
from face_utils import encode_face_from_image, match_student, HAS_FACE_RECOGNITION

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
    """每次打卡后检查自动奖章（仅统计已确认打卡）"""
    count = CheckIn.query.filter_by(student_id=student.id, status='confirmed').count()
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


def check_assessment_badges(assessment):
    """评估保存后检查评估数据奖章"""
    metric_values = {
        'rope_skip': assessment.rope_skip,
        'sit_up': assessment.sit_up,
        'seated_forward_bend': assessment.seated_forward_bend,
        'standing_long_jump': assessment.standing_long_jump,
        'shuttle_run': assessment.shuttle_run,
    }

    # 获取所有评估类奖章模板
    templates = BadgeTemplate.query.filter_by(
        trigger_type='assessment', is_active=True
    ).all()

    awarded = 0
    for bt in templates:
        metric = bt.trigger_metric
        if not metric or metric not in metric_values:
            continue
        val = metric_values[metric]
        if val is None:
            continue

        # shuttle_run 是越低越好，其余是越高越好
        if metric == 'shuttle_run':
            hit = val <= bt.trigger_value
        else:
            hit = val >= bt.trigger_value

        if not hit:
            continue

        exists = StudentBadge.query.filter_by(
            student_id=assessment.student_id, badge_template_id=bt.id
        ).first()
        if not exists:
            db.session.add(StudentBadge(
                student_id=assessment.student_id, badge_template_id=bt.id
            ))
            awarded += 1

    if awarded:
        db.session.commit()
    return awarded


# ── 入学评估分析 ───────────────────────────────────

def analyze_onboarding(age_group, gender, height_cm, weight_kg, goal, weekly_sessions):
    """根据学员基础信息分析并给出推荐方案"""
    result = {
        'bmi': None, 'bmi_label': '', 'goal_label': '',
        'recommended_courses': [], 'weekly_hours': 0,
        'sessions_needed': 0, 'projection': [],
        'target_score': 0, 'advice': ''
    }

    if height_cm and weight_kg and height_cm > 0:
        bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
        result['bmi'] = bmi
        if bmi < 15:
            result['bmi_label'] = '偏瘦'
        elif bmi < 18.5:
            result['bmi_label'] = '标准'
        elif bmi < 22:
            result['bmi_label'] = '偏胖'
        else:
            result['bmi_label'] = '超重'

    goal_map = {
        'zhongkao': '中考体育冲刺', 'fitness': '综合体能提升',
        'posture': '体态矫正', 'weight_loss': '健康减重', 'general': '全面发展'
    }
    result['goal_label'] = goal_map.get(goal, '全面发展')

    base_hours = {'3-6岁': 2, '6-9岁': 3, '9-12岁': 4, '11-15岁': 5}
    result['weekly_hours'] = base_hours.get(age_group, 3)
    if goal == 'zhongkao':
        result['weekly_hours'] = max(result['weekly_hours'], 5)
    result['sessions_needed'] = max(2, result['weekly_hours'])

    if goal == 'zhongkao':
        result['recommended_courses'] = [
            {'name': '中考体育·跳绳专项', 'icon': '🪢', 'reason': '中考必考项，提分最快'},
            {'name': '中考体育·跑步专项', 'icon': '🏃', 'reason': '800/1000米耐力训练'},
            {'name': '中考体育·跳远专项', 'icon': '📏', 'reason': '立定跳远技术训练'},
            {'name': '中考体育·仰卧起坐专项', 'icon': '🔄', 'reason': '核心力量强化'},
        ]
    elif goal == 'posture':
        result['recommended_courses'] = [
            {'name': '感统训练·基础循环第1节', 'icon': '🐻', 'reason': '本体感觉训练，改善体态'},
            {'name': '基础体能·柔韧平衡', 'icon': '🧘', 'reason': '柔韧与平衡训练'},
        ]
    elif goal == 'weight_loss':
        result['recommended_courses'] = [
            {'name': '进阶体能·耐力心肺', 'icon': '🏃', 'reason': '有氧燃脂，提升代谢'},
            {'name': '基础体能·速度敏捷', 'icon': '⚡', 'reason': '高强度间歇，持续燃脂'},
        ]
    elif age_group == '3-6岁':
        result['recommended_courses'] = [
            {'name': '感统训练·基础循环第1节', 'icon': '🐻', 'reason': '感统启蒙，适合低龄'},
            {'name': '感统训练·基础循环第2节', 'icon': '⚽', 'reason': '触觉与协调发展'},
        ]
    elif age_group == '6-9岁':
        result['recommended_courses'] = [
            {'name': '基础体能·力量入门', 'icon': '💪', 'reason': '建立基础力量素质'},
            {'name': '基础体能·协调跳跃', 'icon': '🦘', 'reason': '协调性发展黄金期'},
            {'name': '基础体能·柔韧平衡', 'icon': '🧘', 'reason': '柔韧素质培养'},
        ]
    else:
        result['recommended_courses'] = [
            {'name': '进阶体能·爆发力', 'icon': '🚀', 'reason': '爆发力系统训练'},
            {'name': '进阶体能·耐力心肺', 'icon': '🏃', 'reason': '心肺功能强化'},
        ]

    # 目标投影曲线（6个月）
    ratio = weekly_sessions / result['sessions_needed'] if result['sessions_needed'] > 0 else 0.5
    decay = 0.4 * min(ratio, 1.2)

    target_map = {'zhongkao': 85, 'weight_loss': 70, 'posture': 60, 'fitness': 75, 'general': 70}
    target_score = target_map.get(goal, 70)
    result['target_score'] = target_score

    start_score = 20
    for m in range(1, 7):
        progress = start_score + (target_score - start_score) * (1 - math.exp(-decay * m))
        result['projection'].append({
            'month': m,
            'score': round(min(progress, target_score))
        })

    if weekly_sessions < result['sessions_needed']:
        result['advice'] = f'建议增加到每周 {result["sessions_needed"]} 节课以达到最佳效果'
    else:
        result['advice'] = f'每周 {weekly_sessions} 节课的安排很好，坚持就是胜利！'

    if result['bmi']:
        if result['bmi'] >= 22:
            result['advice'] += '；体重偏重，建议配合饮食管理'
        elif result['bmi'] < 15:
            result['advice'] += '；体重偏轻，注意营养补充'

    return result


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

    # 检查是否已存在今日同课程的待确认打卡
    from datetime import date as date_type
    today = date_type.today()
    existing = CheckIn.query.filter(
        CheckIn.student_id == student.id,
        CheckIn.course_id == course.id,
        func.date(CheckIn.checkin_time) == today
    ).first()
    if existing:
        return jsonify({
            'ok': False,
            'msg': f'{student.name} 今天已打卡此课程，等待教练确认' if existing.status == 'pending' else f'{student.name} 今天已完成此课程打卡'
        })

    ci = CheckIn(student_id=student.id, course_id=course.id, status='pending')
    db.session.add(ci)

    # 检查自动奖章（仅统计已确认的打卡）
    db.session.commit()
    new_badges = check_auto_badges(student)

    return jsonify({
        'ok': True,
        'student_name': student.name,
        'total': student.total_checkins,
        'new_badges': new_badges,
        'pending': True,
        'access_code': student.access_code
    })


@fitness_bp.route('/p/<access_code>')
def parent_home(access_code):
    """扫学员个人码 → 孩子主页（动态信息流）"""
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

    # 奖章
    badges = student.badges.all()

    quote = get_share_quote(student)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    # Today's courses (matching student's age group)
    today_courses = Course.query.filter_by(
        is_active=True, age_group=student.age_group
    ).order_by(Course.name).all()

    # Today's already checked-in courses
    today_checked_ids = set()
    for ci in student.checkins.filter(
        func.date(CheckIn.checkin_time) == today
    ).all():
        today_checked_ids.add(ci.course_id)
    today_checked = len(today_checked_ids)

    # 个人排名（找到最佳排名来展示）
    all_students = Student.query.filter_by(is_active=True).all()
    best_rank_dim = None
    best_rank_info = None
    for dim in RANK_DIMENSIONS:
        dim_rankings = get_student_ranking_data(dim['key'], all_students)
        for r in dim_rankings:
            if r['id'] == student.id:
                rank_pct = (1 - r['rank'] / len(dim_rankings)) * 100 if dim_rankings else 0
                if best_rank_info is None or rank_pct > best_rank_info.get('pct', 0):
                    gap = None
                    ahead_name = None
                    if r['rank'] > 1:
                        ahead = dim_rankings[r['rank'] - 2]
                        gap = ahead['score'] - r['score']
                        ahead_name = ahead['name']
                    best_rank_info = {
                        'dim_name': dim['name'], 'dim_icon': dim['icon'],
                        'rank': r['rank'], 'score': r['score'],
                        'total': len(dim_rankings), 'gap': gap,
                        'ahead_name': ahead_name, 'pct': rank_pct
                    }
                    best_rank_dim = dim['key']
                break

    return render_template('parent/home.html',
                           student=student,
                           checkins=checkins,
                           checkin_count=checkin_count,
                           streak=streak,
                           this_month_count=this_month_count,
                           badges=badges,
                           badge_count=len(badges),
                           photos=student.photos.limit(20).all(),
                           fitness_score=student.fitness_score,
                           rank_tier=student.rank_tier,
                           quote=quote,
                           coach_qr=coach_qr,
                           now=datetime.now(),
                           today_courses=today_courses,
                           today_checked=today_checked,
                           best_rank_info=best_rank_info,
                           best_rank_dim=best_rank_dim)


# ═══════════════════════════════════════════════════
# 专属报告页
# ═══════════════════════════════════════════════════

@fitness_bp.route('/p/<access_code>/report')
def parent_report(access_code):
    """专属报告页：成长变化、初始情况、分析报告、图表、洞察"""
    student = Student.query.filter_by(access_code=access_code).first_or_404()

    # Per-metric growth comparison
    improvements, assessments = compute_improvements(student)

    # Chart data for trend line
    chart_data = {
        'labels': [a.date.strftime('%m/%d') for a in assessments],
        'rope_skip': [a.rope_skip for a in assessments],
        'seated_forward_bend': [a.seated_forward_bend for a in assessments],
        'standing_long_jump': [a.standing_long_jump for a in assessments],
        'shuttle_run': [a.shuttle_run for a in assessments],
        'sit_up': [a.sit_up for a in assessments],
    }

    # Onboarding analysis
    onboarding = analyze_onboarding(
        student.age_group, student.gender,
        student.height_cm, student.weight_kg,
        student.goal, student.weekly_sessions or 1
    )

    today = date.today()
    streak = student.streak_days

    # 课程类型分布
    CATEGORY_ICONS = {
        '感统': '🐻', '力量': '💪', '速度': '⚡', '协调': '🎯',
        '柔韧': '🤸', '爆发': '🚀', '耐力': '🫁',
        '跳绳': '🪢', '跑步': '🏃', '跳远': '📏', '仰卧起坐': '🔄', '综合': '📋'
    }
    CATEGORY_COLORS = [
        '#007AFF','#34C759','#FF9500','#FF3B30','#AF52DE',
        '#FFD700','#FF6B6B','#4ECDC4','#45B7D1','#96CEB4',
        '#FFEAA7','#DDA0DD','#98D8C8'
    ]
    course_dist = Counter()
    total_confirmed = 0
    for ci in student.checkins.filter(CheckIn.status == 'confirmed').all():
        total_confirmed += 1
        matched = False
        for cat in CATEGORY_ICONS:
            if cat in ci.course.name:
                course_dist[cat] += 1
                matched = True
                break
        if not matched:
            course_dist['其他'] += 1

    course_dist_data = {
        'labels': [f'{CATEGORY_ICONS.get(k, "📌")} {k}' for k in course_dist],
        'data': [course_dist[k] for k in course_dist],
        'colors': CATEGORY_COLORS[:len(course_dist)]
    }

    # 六维属性雷达图数据
    attr_labels = list(ATTR_ICONS.keys())
    attr_values = [student.attributes[a] for a in attr_labels]

    # 每周训练频率（最近8周）
    weekly_labels = []
    weekly_counts = []
    for i in range(7, -1, -1):
        w_end = today - timedelta(days=i * 7)
        w_start = w_end - timedelta(days=6)
        cnt = student.checkins.filter(
            CheckIn.status == 'confirmed',
            func.date(CheckIn.checkin_time) >= w_start,
            func.date(CheckIn.checkin_time) <= w_end
        ).count()
        weekly_labels.append(w_start.strftime('%m/%d'))
        weekly_counts.append(cnt)

    # 本周训练次数
    this_week_start = today - timedelta(days=today.weekday())
    this_week_count = student.checkins.filter(
        CheckIn.status == 'confirmed',
        func.date(CheckIn.checkin_time) >= this_week_start,
        func.date(CheckIn.checkin_time) <= today
    ).count()

    # 目标达成进度
    goal_progress = None
    if student.goal and student.weekly_sessions and student.weekly_sessions > 0:
        four_weeks_ago = today - timedelta(days=28)
        recent_count = student.checkins.filter(
            CheckIn.status == 'confirmed',
            func.date(CheckIn.checkin_time) >= four_weeks_ago
        ).count()
        actual_weekly = round(recent_count / 4, 1)
        goal_progress = {
            'target': student.weekly_sessions,
            'actual': actual_weekly,
            'pct': min(100, round(actual_weekly / student.weekly_sessions * 100))
        }

    # 第一次训练距今
    first_checkin = student.checkins.filter(
        CheckIn.status == 'confirmed'
    ).order_by(CheckIn.checkin_time.asc()).first()
    days_active = (today - first_checkin.checkin_time.date()).days if first_checkin else None

    # 参加过的不同课程数
    unique_courses = db.session.query(func.count(func.distinct(CheckIn.course_id))).filter(
        CheckIn.student_id == student.id,
        CheckIn.status == 'confirmed'
    ).scalar() or 0

    # 智能洞察
    badges = student.badges.all()
    insights = []
    if days_active and days_active >= 30:
        insights.append({'icon': '📅', 'text': f'已坚持训练 {days_active} 天，养成了运动习惯'})
    if student.streak_days >= 7:
        insights.append({'icon': '🔥', 'text': f'连续 {student.streak_days} 天打卡，自律能力超强'})
    if len(badges) >= 3:
        insights.append({'icon': '🏅', 'text': f'已获得 {len(badges)} 枚奖章，综合发展均衡'})
    if improvements:
        best = max(improvements, key=lambda x: abs(x['last_val'] - x['first_val']) / max(abs(x['first_val']), 1))
        direction = '提升' if best['improved'] else '改善'
        insights.append({'icon': '📈', 'text': f'{best["label"]}进步最大，从 {best["first_val"]} {direction}到 {best["last_val"]}'})
    if student.fitness_score >= 80:
        insights.append({'icon': '👑', 'text': f'体质分 {student.fitness_score}，已达巅峰水平'})
    elif student.fitness_score >= 60:
        insights.append({'icon': '🌿', 'text': f'体质分 {student.fitness_score}，处于稳定成长期'})
    else:
        insights.append({'icon': '🌱', 'text': f'体质分 {student.fitness_score}，仍有巨大成长空间'})
    if goal_progress and goal_progress['pct'] >= 80:
        insights.append({'icon': '✅', 'text': f'每周训练达标率 {goal_progress["pct"]}%，计划执行良好'})
    elif goal_progress and goal_progress['pct'] < 50:
        insights.append({'icon': '⚠️', 'text': f'近期训练频率偏低，建议保持每周 {student.weekly_sessions} 节'})
    if unique_courses >= 4:
        insights.append({'icon': '🎯', 'text': f'体验过 {unique_courses} 种不同课程，训练多样性好'})

    goal_labels = {'zhongkao': '中考体育冲刺', 'fitness': '综合体能提升',
                   'posture': '体态矫正', 'weight_loss': '健康减重', 'general': '全面发展'}

    quote = get_share_quote(student)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/report.html',
                           student=student,
                           improvements=improvements,
                           assessments=assessments,
                           chart_data=chart_data,
                           onboarding=onboarding,
                           fitness_score=student.fitness_score,
                           rank_tier=student.rank_tier,
                           streak=streak,
                           total_confirmed=total_confirmed,
                           this_week_count=this_week_count,
                           unique_courses=unique_courses,
                           days_active=days_active,
                           course_dist_data=course_dist_data,
                           attr_labels=attr_labels,
                           attr_values=attr_values,
                           weekly_labels=weekly_labels,
                           weekly_counts=weekly_counts,
                           goal_progress=goal_progress,
                           goal_labels=goal_labels,
                           insights=insights,
                           badges=badges,
                           badge_count=len(badges),
                           quote=quote,
                           coach_qr=coach_qr)


# ═══════════════════════════════════════════════════
# 排行榜（公开）
# ═══════════════════════════════════════════════════

RANK_DIMENSIONS = [
    {'key': 'fitness', 'name': '综合体质', 'icon': '🏆', 'unit': '分', 'color': '#FF9500'},
    {'key': 'weekly', 'name': '本周训练王', 'icon': '🔥', 'unit': '次', 'color': '#FF375F'},
    {'key': 'strength', 'name': '力量之王', 'icon': '💪', 'unit': '分', 'color': '#FF375F'},
    {'key': 'speed', 'name': '速度之星', 'icon': '⚡', 'unit': '分', 'color': '#5AC8FA'},
    {'key': 'endurance', 'name': '耐力达人', 'icon': '🫁', 'unit': '分', 'color': '#4CD964'},
    {'key': 'flexibility', 'name': '柔韧高手', 'icon': '🤸', 'unit': '分', 'color': '#AF52DE'},
    {'key': 'coordination', 'name': '协调大师', 'icon': '🎯', 'unit': '分', 'color': '#FF9500'},
    {'key': 'power', 'name': '爆发力王', 'icon': '🚀', 'unit': '分', 'color': '#FF375F'},
    {'key': 'badges', 'name': '奖章收藏家', 'icon': '🏅', 'unit': '枚', 'color': '#FFD700'},
    {'key': 'progress', 'name': '进步之星', 'icon': '📈', 'unit': '次/月', 'color': '#4CD964'},
]

ATTR_KEY_MAP = {'strength': '力量', 'speed': '速度', 'endurance': '耐力',
                'flexibility': '柔韧', 'coordination': '协调', 'power': '爆发'}

MOTIVATIONAL_QUOTES_RANK = [
    '排名不重要，重要的是每天都在超越自己。',
    '今天比昨天强，就是最好的胜利。',
    '每一次训练都在悄悄改变排名。',
    '不是要赢过所有人，是要赢过昨天的自己。',
    '汗水不会说谎，排名会证明一切。',
    '坚持的孩子，排名从不说谎。',
    '现在的每一分，都是未来的勋章。',
    '排名的意义不是比较，是见证成长。',
]


def get_student_ranking_data(dimension_key, student_list):
    """根据维度计算排名列表"""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_ago = today - timedelta(days=30)

    results = []
    for s in student_list:
        attrs = s.attributes
        if dimension_key == 'fitness':
            score = s.fitness_score
        elif dimension_key == 'weekly':
            score = s.checkins.filter(
                CheckIn.status == 'confirmed',
                func.date(CheckIn.checkin_time) >= week_start
            ).count()
        elif dimension_key == 'badges':
            score = s.badges.count()
        elif dimension_key == 'progress':
            score = s.checkins.filter(
                CheckIn.status == 'confirmed',
                func.date(CheckIn.checkin_time) >= month_ago
            ).count()
        elif dimension_key in ATTR_KEY_MAP:
            score = attrs.get(ATTR_KEY_MAP[dimension_key], 0)
        else:
            score = 0

        results.append({
            'id': s.id,
            'name': s.name,
            'access_code': s.access_code,
            'avatar_emoji': s.avatar_emoji,
            'face_photo_path': s.face_photo_path,
            'age_group': s.age_group,
            'fitness_score': s.fitness_score,
            'total_checkins': s.total_checkins,
            'badge_count': s.badges.count(),
            'rank_tier': s.rank_tier,
            'score': score,
        })

    results.sort(key=lambda r: r['score'], reverse=True)
    for i, r in enumerate(results):
        r['rank'] = i + 1
        if i == 0:
            r['medal'] = '🥇'
        elif i == 1:
            r['medal'] = '🥈'
        elif i == 2:
            r['medal'] = '🥉'
        else:
            r['medal'] = str(r['rank'])

    return results


@fitness_bp.route('/leaderboard')
def leaderboard():
    sort_by = request.args.get('sort', 'fitness')
    my_code = request.args.get('my', '')

    students = Student.query.filter_by(is_active=True).all()

    rankings = get_student_ranking_data(sort_by, students)

    # Personal ranking lookup
    my_ranks = None
    if my_code:
        my_student = Student.query.filter_by(access_code=my_code).first()
        if my_student:
            my_ranks = {}
            for dim in RANK_DIMENSIONS:
                dim_rankings = get_student_ranking_data(dim['key'], students)
                for r in dim_rankings:
                    if r['id'] == my_student.id:
                        my_ranks[dim['key']] = {
                            'rank': r['rank'], 'score': r['score'],
                            'total': len(dim_rankings)
                        }
                        # Challenge: who's ahead by how much
                        if r['rank'] > 1:
                            ahead = dim_rankings[r['rank'] - 2]
                            my_ranks[dim['key']]['gap'] = ahead['score'] - r['score']
                            my_ranks[dim['key']]['ahead_name'] = ahead['name']
                        break

    # Current dimension info
    dim_info = next((d for d in RANK_DIMENSIONS if d['key'] == sort_by), RANK_DIMENSIONS[0])

    return render_template('parent/leaderboard.html',
                           rankings=rankings,
                           sort_by=sort_by,
                           dimensions=RANK_DIMENSIONS,
                           dim_info=dim_info,
                           my_ranks=my_ranks,
                           my_code=my_code,
                           quote=random.choice(MOTIVATIONAL_QUOTES_RANK))


@fitness_bp.route('/leaderboard/student-access/<int:student_id>')
def leaderboard_student_access(student_id):
    s = Student.query.get_or_404(student_id)
    return jsonify({'code': s.access_code})


@fitness_bp.route('/leaderboard/share')
def leaderboard_share():
    """排名分享卡片（小红书封面风格）"""
    student_code = request.args.get('code', '')
    dim_key = request.args.get('dim', 'fitness')
    student = Student.query.filter_by(access_code=student_code).first()

    if not student:
        return '学员未找到', 404

    students = Student.query.filter_by(is_active=True).all()
    rankings = get_student_ranking_data(dim_key, students)

    my_rank = None
    for r in rankings:
        if r['id'] == student.id:
            my_rank = r
            break

    if not my_rank:
        return '排名数据异常', 500

    dim_info = next((d for d in RANK_DIMENSIONS if d['key'] == dim_key), RANK_DIMENSIONS[0])
    quote = random.choice(MOTIVATIONAL_QUOTES_RANK)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/rank_share.html',
                           student=student,
                           my_rank=my_rank,
                           dim_info=dim_info,
                           quote=quote,
                           coach_qr=coach_qr,
                           total=len(rankings),
                           rank_tier=student.rank_tier)


@fitness_bp.route('/leaderboard/share/challenge')
def leaderboard_challenge_share():
    """对决挑战分享卡 — VS 模式"""
    my_code = request.args.get('me', '')
    opponent_id = request.args.get('opponent', type=int)
    dim_key = request.args.get('dim', 'fitness')

    me = Student.query.filter_by(access_code=my_code).first()
    opponent = Student.query.get(opponent_id) if opponent_id else None

    if not me or not opponent:
        return '参数错误', 400

    students = Student.query.filter_by(is_active=True).all()
    rankings = get_student_ranking_data(dim_key, students)

    my_rank = next((r for r in rankings if r['id'] == me.id), None)
    opp_rank = next((r for r in rankings if r['id'] == opponent.id), None)

    if not my_rank or not opp_rank:
        return '排名数据异常', 500

    dim_info = next((d for d in RANK_DIMENSIONS if d['key'] == dim_key), RANK_DIMENSIONS[0])
    quote = random.choice(MOTIVATIONAL_QUOTES_RANK)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/challenge_share.html',
                           me=me, opponent=opponent,
                           my_rank=my_rank, opp_rank=opp_rank,
                           dim_info=dim_info, quote=quote, coach_qr=coach_qr)


@fitness_bp.route('/p/<code>/share/tier-up')
def parent_share_tier_up(code):
    """段位晋升分享卡 — 游戏化 LEVEL UP"""
    student = Student.query.filter_by(access_code=code).first_or_404()

    current_tier = student.rank_tier
    idx = RANK_TIERS.index(current_tier)
    old_tier = RANK_TIERS[idx - 1] if idx > 0 else RANK_TIERS[0]

    hook_data = {
        'name': student.name,
        'old_tier': old_tier['name'],
        'new_tier': current_tier['name'],
    }
    hook = get_share_hook(hook_data, 'tier_up')
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/tier_up_share.html',
                           student=student,
                           current_tier=current_tier,
                           old_tier=old_tier,
                           hook=hook,
                           coach_qr=coach_qr)


@fitness_bp.route('/p/<code>/share/weekly')
def parent_share_weekly(code):
    """周报个人卡 — 本周训练数据汇总"""
    student = Student.query.filter_by(access_code=code).first_or_404()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    week_checkins = CheckIn.query.filter(
        CheckIn.student_id == student.id,
        CheckIn.status == 'confirmed',
        func.date(CheckIn.checkin_time) >= week_start,
        func.date(CheckIn.checkin_time) <= today
    ).count()

    # 检测本周事件
    events = []
    assessments = Assessment.query.filter_by(student_id=student.id)\
        .order_by(Assessment.date.desc()).all()

    # 本周是否有新评估记录
    for a in assessments:
        if a.date and a.date >= week_start:
            for metric, label, icon in [
                ('rope_skip', '跳绳', '🪢'),
                ('standing_long_jump', '跳远', '🚀'),
                ('sit_up', '仰卧起坐', '💪'),
                ('shuttle_run', '折返跑', '⚡'),
                ('seated_forward_bend', '体前屈', '🤸'),
            ]:
                val = getattr(a, metric)
                if val is not None:
                    events.append({
                        'icon': icon,
                        'text': f'{label}: {val}',
                    })
            break  # 只取最近一次评估

    # 本周打卡情况
    if week_checkins >= 3:
        events.insert(0, {'icon': '🔥', 'text': f'本周出勤 {week_checkins} 次，全勤达人'})
    elif week_checkins > 0:
        events.insert(0, {'icon': '✅', 'text': f'本周出勤 {week_checkins} 次'})

    # 如果有进步
    if assessments:
        improvements, _ = compute_improvements(student)
        for imp in improvements[:3]:
            if imp['improved']:
                direction = '↑' if imp['unit'] != 's' else '↓'
                events.append({
                    'icon': imp['icon'],
                    'text': f"{imp['label']}: {imp['first_val']}{imp['unit']} → {imp['last_val']}{imp['unit']} {direction}",
                })

    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'
    rank_tier = student.rank_tier

    return render_template('parent/weekly_share.html',
                           student=student,
                           week_checkins=week_checkins,
                           week_start=week_start.strftime('%m/%d'),
                           week_end=today.strftime('%m/%d'),
                           events=events[-5:],
                           rank_tier=rank_tier,
                           coach_qr=coach_qr)


# ═══════════════════════════════════════════════════
# 分享卡片
# ═══════════════════════════════════════════════════

MOTIVATIONAL_QUOTES = [
    '每一次挥汗，都是未来的铠甲。',
    '今天比昨天强，就是最好的进步。',
    '小小的身体，大大的能量。',
    '坚持不是为了赢别人，是为了超越自己。',
    '你流下的每一滴汗，都在悄悄改变你。',
    '不积跬步，无以至千里。',
    '现在付出的努力，身体都记得。',
    '真正的对手，是昨天的自己。',
    '成长没有捷径，但有迹可循。',
    '每一个坚持的孩子，背后都有用心的父母。',
    '体能是给童年最好的礼物。',
    '你今天跑的每一步，都算数。',
    '小小的坚持，大大的改变。',
    '别人看到的是成绩，我看到的是汗水。',
    '练的不是体育，是品格。',
]


def compute_improvements(student):
    """Per-metric earliest non-null vs latest non-null across ALL assessments.
    Supports single-metric updates (单项更新) — if only rope_skip was updated
    in the 2nd assessment, only rope_skip shows a comparison."""
    assessments = Assessment.query.filter_by(student_id=student.id)\
        .order_by(Assessment.date.asc()).all()

    if not assessments:
        return [], assessments

    improvements = []
    metrics = [
        ('rope_skip', '跳绳', '🪢', '次'),
        ('seated_forward_bend', '体前屈', '🤸', 'cm'),
        ('standing_long_jump', '跳远', '🚀', 'cm'),
        ('sit_up', '仰卧起坐', '💪', '次'),
        ('shuttle_run', '折返跑', '⚡', 's'),
    ]

    for attr, label, icon, unit in metrics:
        earliest_val = None
        latest_val = None
        for a in assessments:
            v = getattr(a, attr)
            if v is not None:
                if earliest_val is None:
                    earliest_val = v
                latest_val = v
        if earliest_val is not None and latest_val is not None and earliest_val != latest_val:
            improved = latest_val < earliest_val if attr == 'shuttle_run' else latest_val > earliest_val
            improvements.append({
                'icon': icon, 'label': label,
                'first_val': earliest_val, 'last_val': latest_val,
                'improved': improved, 'unit': unit,
            })

    return improvements, assessments


def get_share_quote(student):
    """根据学生状态选择激励金句"""
    score = student.fitness_score
    count = student.total_checkins

    if count == 0:
        return '旅程刚刚开始，每一步都值得记录。'
    if score >= 90:
        return '巅峰不是终点，是下一个起点。🏆'
    if score >= 80:
        return '突破自我，就在这一节课。🔥'
    if score >= 60:
        return '成长看得见，进步每一天。🌿'
    if student.streak_days >= 7:
        return '连续坚持，是最酷的事情。'
    if count >= 10:
        return '不知不觉，已经坚持这么久啦！'

    import random
    return random.choice(MOTIVATIONAL_QUOTES)


@fitness_bp.route('/p/<access_code>/share')
def parent_share(access_code):
    """分享卡片页"""
    student = Student.query.filter_by(access_code=access_code).first_or_404()
    attrs = student.attributes
    top_attrs = sorted(attrs.items(), key=lambda x: x[1], reverse=True)[:3]
    quote = get_share_quote(student)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/share.html',
                           student=student,
                           fitness_score=student.fitness_score,
                           rank_tier=student.rank_tier,
                           total_checkins=student.total_checkins,
                           badge_count=student.badges.count(),
                           top_attrs=top_attrs,
                           quote=quote,
                           coach_qr=coach_qr)


@fitness_bp.route('/p/<access_code>/badge/<int:student_badge_id>')
def parent_badge_detail(access_code, student_badge_id):
    """奖章详情：配当天训练照片"""
    student = Student.query.filter_by(access_code=access_code).first_or_404()
    badge = StudentBadge.query.get_or_404(student_badge_id)

    # 找奖章日期当天被标记给该学员的照片
    badge_date = badge.awarded_date.date() if hasattr(badge.awarded_date, 'date') else badge.awarded_date
    day_photos = Photo.query.filter(
        Photo.student_id == student.id,
        Photo.is_tagged == True,
        func.date(Photo.upload_date) == badge_date
    ).order_by(Photo.upload_date.desc()).limit(20).all()

    quote = get_share_quote(student)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'

    return render_template('parent/badge_detail.html',
                           student=student,
                           badge=badge,
                           day_photos=day_photos,
                           quote=quote,
                           coach_qr=coach_qr,
                           rank_tier=student.rank_tier,
                           fitness_score=student.fitness_score)


@fitness_bp.route('/p/<access_code>/photo/<int:photo_id>/share')
def parent_photo_share(access_code, photo_id):
    """单张照片一键分享卡片（小红书封面风格）"""
    student = Student.query.filter_by(access_code=access_code).first_or_404()
    photo = Photo.query.get_or_404(photo_id)

    quote = get_share_quote(student)
    coach_qr = '/static/uploads/qrcodes/coach_wechat.png'
    attrs = student.attributes
    top_attrs = sorted(attrs.items(), key=lambda x: x[1], reverse=True)[:3]

    # 成长变化数据
    assessments = student.assessments.order_by(Assessment.date.asc()).all()
    improvements = []
    if len(assessments) >= 2:
        first, last = assessments[0], assessments[-1]
        for attr, label, icon in [
            ('rope_skip', '跳绳', '🪢'),
            ('seated_forward_bend', '体前屈', '🤸'),
            ('standing_long_jump', '跳远', '🚀'),
            ('sit_up', '仰卧起坐', '💪'),
        ]:
            fv, lv = getattr(first, attr), getattr(last, attr)
            if fv and lv and lv != fv:
                improvements.append({
                    'icon': icon, 'label': label,
                    'from_val': fv, 'to_val': lv,
                    'up': lv > fv,
                })

    return render_template('parent/photo_share.html',
                           student=student,
                           photo=photo,
                           quote=quote,
                           coach_qr=coach_qr,
                           top_attrs=top_attrs,
                           improvements=improvements,
                           rank_tier=student.rank_tier,
                           fitness_score=student.fitness_score,
                           total_checkins=student.total_checkins,
                           badge_count=student.badges.count())


# ═══════════════════════════════════════════════════
# 教练端 认证
# ═══════════════════════════════════════════════════

@fitness_bp.route('/login', methods=['GET', 'POST'])
def coach_login():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == current_app.config['FITNESS_COACH_PASSWORD']:
            session['coach_ok'] = True
            session.permanent = True
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

        today_all = CheckIn.query.filter(
            CheckIn.course_id == course_id,
            func.date(CheckIn.checkin_time) == date.today()
        ).order_by(CheckIn.checkin_time.asc()).all()

        today_checkins = [c for c in today_all if c.status == 'confirmed']
        pending_checkins = [c for c in today_all if c.status == 'pending']
    else:
        pending_checkins = []

    # 所有待确认打卡（全局）
    all_pending = CheckIn.query.filter_by(status='pending').order_by(
        CheckIn.checkin_time.desc()
    ).limit(50).all() if not course_id else []

    courses = Course.query.filter_by(is_active=True).order_by(
        Course.age_group, Course.name).all()

    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()

    return render_template('coach/today.html',
                           courses=courses, course=course,
                           qr_path=qr_path, today_checkins=today_checkins,
                           pending_checkins=pending_checkins,
                           all_pending=all_pending,
                           students=students)


@fitness_bp.route('/today/checkin', methods=['POST'])
@coach_required
def coach_manual_checkin():
    """教练手动补打卡"""
    student_id = request.form.get('student_id', type=int)
    course_id = request.form.get('course_id', type=int)
    student = Student.query.get_or_404(student_id)
    course = Course.query.get_or_404(course_id)

    # 同一天同一学员同一课程不允许重复打卡
    existing = CheckIn.query.filter(
        CheckIn.student_id == student.id,
        CheckIn.course_id == course.id,
        func.date(CheckIn.checkin_time) == date.today()
    ).first()
    if existing:
        return jsonify({'ok': False, 'msg': f'{student.name} 今天已打卡此课程'})

    ci = CheckIn(student_id=student.id, course_id=course.id, status='confirmed')
    db.session.add(ci)
    db.session.commit()
    check_auto_badges(student)
    return jsonify({'ok': True, 'student_name': student.name})


@fitness_bp.route('/checkins/<int:checkin_id>/approve', methods=['POST'])
@coach_required
def coach_checkin_approve(checkin_id):
    ci = CheckIn.query.get_or_404(checkin_id)
    ci.status = 'confirmed'
    db.session.commit()
    check_auto_badges(ci.student)
    return jsonify({'ok': True})


@fitness_bp.route('/checkins/<int:checkin_id>/reject', methods=['POST'])
@coach_required
def coach_checkin_reject(checkin_id):
    ci = CheckIn.query.get_or_404(checkin_id)
    if ci.status == 'pending':
        db.session.delete(ci)
        db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════
# 教练端 学员管理
# ═══════════════════════════════════════════════════

@fitness_bp.route('/students')
@coach_required
def coach_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('coach/students.html', students=students)


@fitness_bp.route('/students/new/onboarding', methods=['GET', 'POST'])
@coach_required
def coach_onboarding():
    """入学初始评估 → 分析推荐 → 添加学员"""
    if request.method == 'POST':
        # "参与计划" → store data in session, redirect to student form
        if request.form.get('start_plan') == '1':
            session['onboarding_data'] = {
                'age_group': request.form.get('age_group', ''),
                'gender': request.form.get('gender', ''),
                'height_cm': request.form.get('height_cm', ''),
                'weight_kg': request.form.get('weight_kg', ''),
                'goal': request.form.get('goal', ''),
                'weekly_sessions': request.form.get('weekly_sessions', ''),
            }
            return redirect(url_for('fitness.coach_student_new'))

        # 分析模式
        goal_raw = request.form.get('goal', '')
        goals = [g.strip() for g in goal_raw.split(',') if g.strip()]
        primary_goal = goals[0] if goals else 'general'

        analysis = analyze_onboarding(
            age_group=request.form.get('age_group', ''),
            gender=request.form.get('gender', ''),
            height_cm=request.form.get('height_cm', type=float),
            weight_kg=request.form.get('weight_kg', type=float),
            goal=primary_goal,
            weekly_sessions=request.form.get('weekly_sessions', type=int) or 2
        )
        return render_template('coach/onboarding.html',
                               form_data=request.form,
                               analysis=analysis,
                               analyzed=True)

    return render_template('coach/onboarding.html', analyzed=False, form_data={})


@fitness_bp.route('/students/new', methods=['GET', 'POST'])
@coach_required
def coach_student_new():
    # Pre-fill from onboarding session data
    onboard_data = session.pop('onboarding_data', None)

    if request.method == 'POST':
        s = Student(
            name=request.form['name'].strip(),
            age_group=request.form['age_group'],
            gender=request.form.get('gender', ''),
            height_cm=request.form.get('height_cm', type=float),
            weight_kg=request.form.get('weight_kg', type=float),
            goal=request.form.get('goal', ''),
            weekly_sessions=request.form.get('weekly_sessions', type=int),
            notes=request.form.get('notes', ''),
            avatar_emoji=request.form.get('avatar_emoji', '🧒')
        )
        db.session.add(s)
        db.session.commit()

        # 生成个人二维码
        base = current_app.config['PUBLIC_BASE_URL']
        url = f'{base}/p/{s.access_code}'
        generate_qr(url, f'student_{s.access_code}.png')

        return redirect(url_for('fitness.coach_student_detail', student_id=s.id))

    return render_template('coach/student_form.html', student=None, onboard_data=onboard_data)


@fitness_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@coach_required
def coach_student_edit(student_id):
    s = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        s.name = request.form['name'].strip()
        s.age_group = request.form['age_group']
        s.gender = request.form.get('gender', '')
        s.height_cm = request.form.get('height_cm', type=float)
        s.weight_kg = request.form.get('weight_kg', type=float)
        s.goal = request.form.get('goal', '')
        s.weekly_sessions = request.form.get('weekly_sessions', type=int)
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

    # 如果二维码不存在，自动生成
    import qrcode
    full_qr = os.path.join(current_app.root_path, qr_path.lstrip('/'))
    if not os.path.exists(full_qr):
        qr = qrcode.make(f'{base}/p/{s.access_code}')
        qr.save(full_qr)

    badge_templates = BadgeTemplate.query.filter_by(is_active=True).all()

    return render_template('coach/student_detail.html',
                           student=s, checkins=checkins,
                           assessments=assessments, badges=badges,
                           qr_path=qr_path, base_url=base,
                           badge_templates=badge_templates,
                           today=date.today())


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
        db.session.flush()  # 先 flush 以便获取 a.id

        # 自动检查评估奖章
        check_assessment_badges(a)

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


# ═══════════════════════════════════════════════════
# 照片上传 + 人脸识别
# ═══════════════════════════════════════════════════

@fitness_bp.route('/photos/upload', methods=['GET', 'POST'])
@coach_required
def coach_photo_upload():
    if request.method == 'POST':
        files = request.files.getlist('photos')
        if not files or files[0].filename == '':
            return jsonify({'ok': False, 'msg': '请选择照片'})

        # 获取所有已录入人脸的学生
        students_with_faces = db.session.query(
            Student.id, Student.face_encoding
        ).filter(
            Student.is_active == True,
            Student.face_encoding.isnot(None)
        ).all()

        photo_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'photos')
        os.makedirs(photo_dir, exist_ok=True)

        results = {'tagged': 0, 'untagged': 0, 'photos': []}

        for f in files:
            if not f.filename or not f.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.webp')):
                continue

            ext = os.path.splitext(f.filename)[1].lower() or '.jpg'
            fname = f'{uuid.uuid4().hex}{ext}'
            fpath = os.path.join(photo_dir, fname)
            f.save(fpath)

            rel_path = f'/static/uploads/photos/{fname}'

            matched_sid, conf = None, None
            if students_with_faces:
                matched_sid, conf = match_student(fpath, students_with_faces)

            photo = Photo(
                student_id=matched_sid,
                file_path=rel_path,
                is_tagged=matched_sid is not None,
                confidence=conf
            )
            db.session.add(photo)

            if matched_sid:
                student = Student.query.get(matched_sid)
                results['tagged'] += 1
                results['photos'].append({
                    'path': rel_path,
                    'tagged': True,
                    'student_name': student.name if student else '?',
                    'confidence': conf
                })
            else:
                results['untagged'] += 1
                results['photos'].append({
                    'photo_id': None,  # will be set after commit
                    'path': rel_path,
                    'tagged': False
                })

        db.session.commit()

        # 回填 photo_id 给未标记项
        untagged = Photo.query.filter_by(is_tagged=False).order_by(
            Photo.upload_date.desc()
        ).limit(results['untagged']).all()
        idx = 0
        for r in results['photos']:
            if not r['tagged'] and idx < len(untagged):
                r['photo_id'] = untagged[-(results['untagged'] - idx)].id \
                    if results['untagged'] - idx <= len(untagged) else untagged[idx].id

        results['ok'] = True
        results['has_face_recognition'] = HAS_FACE_RECOGNITION
        return jsonify(results)

    students_with_faces = db.session.query(Student.id, Student.name).filter(
        Student.is_active == True,
        Student.face_encoding.isnot(None)
    ).count()

    return render_template('coach/photo_upload.html',
                           has_face_recognition=HAS_FACE_RECOGNITION,
                           students_with_faces=students_with_faces)


@fitness_bp.route('/photos/untagged')
@coach_required
def coach_photos_untagged():
    """未标记照片列表"""
    photos = Photo.query.filter_by(is_tagged=False).order_by(
        Photo.upload_date.desc()
    ).limit(100).all()
    students = Student.query.filter_by(is_active=True).order_by(Student.name).all()
    return render_template('coach/photos_untagged.html',
                           photos=photos, students=students)


@fitness_bp.route('/photos/<int:photo_id>/tag', methods=['POST'])
@coach_required
def coach_photo_tag(photo_id):
    """手动标记照片所属学员"""
    photo = Photo.query.get_or_404(photo_id)
    student_id = request.form.get('student_id', type=int)

    if student_id:
        student = Student.query.get_or_404(student_id)
        photo.student_id = student.id
        photo.is_tagged = True

        # 如果该学员还没有人脸编码，从此照片学习
        if not student.face_encoding:
            encoding = encode_face_from_image(
                os.path.join(current_app.root_path, photo.file_path.lstrip('/'))
            )
            if encoding is not None:
                import pickle
                student.face_encoding = pickle.dumps(encoding)
                student.face_photo_path = photo.file_path

        db.session.commit()
        return jsonify({'ok': True, 'student_name': student.name})
    else:
        # 跳过（标记为已处理但无归属）
        photo.is_tagged = True
        db.session.commit()
        return jsonify({'ok': True})


@fitness_bp.route('/students/<int:student_id>/face/register', methods=['POST'])
@coach_required
def coach_face_register(student_id):
    """为学员录入人脸"""
    student = Student.query.get_or_404(student_id)

    f = request.files.get('face_photo')
    if not f or f.filename == '':
        return jsonify({'ok': False, 'msg': '请上传一张正面照片'})

    photo_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'photos')
    os.makedirs(photo_dir, exist_ok=True)

    fname = f'face_{student.access_code}_{uuid.uuid4().hex[:6]}.jpg'
    fpath = os.path.join(photo_dir, fname)
    f.save(fpath)

    if not HAS_FACE_RECOGNITION:
        return jsonify({'ok': False, 'msg': '人脸识别库未安装（dlib 编译失败），请在学员详情页使用手动标记功能'})

    encoding = encode_face_from_image(fpath)
    if encoding is None:
        os.remove(fpath)
        return jsonify({'ok': False, 'msg': '未检测到人脸，请用清晰的正面照片重试'})

    import pickle
    student.face_encoding = pickle.dumps(encoding)
    student.face_photo_path = f'/static/uploads/photos/{fname}'
    db.session.commit()

    return jsonify({'ok': True, 'msg': f'{student.name} 人脸录入成功', 'photo_path': student.face_photo_path})


@fitness_bp.route('/students/<int:student_id>/photos')
@coach_required
def coach_student_photos(student_id):
    """查看某学员的所有照片"""
    student = Student.query.get_or_404(student_id)
    photos = student.photos.all()
    return render_template('coach/student_photos.html',
                           student=student, photos=photos)


# ═══════════════════════════════════════════════════════════════
# 课程预约系统
# ═══════════════════════════════════════════════════════════════

@fitness_bp.route('/booking')
def parent_booking():
    """家长端预约页"""
    from datetime import date as dt_date, timedelta
    today = dt_date.today()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0 and today.weekday() > 4:
        days_until_friday = 7
    friday = today + timedelta(days=days_until_friday)

    sessions = [
        {'key': 'friday_evening', 'date': friday, 'label': '周五晚 19:00-20:00', 'max': 20},
        {'key': 'saturday_afternoon', 'date': friday + timedelta(days=1), 'label': '周六下午 15:00-16:00', 'max': 20},
        {'key': 'saturday_evening', 'date': friday + timedelta(days=1), 'label': '周六晚 19:00-20:00', 'max': 20},
        {'key': 'sunday_afternoon', 'date': friday + timedelta(days=2), 'label': '周日下午 15:00-16:00', 'max': 20},
        {'key': 'sunday_evening', 'date': friday + timedelta(days=2), 'label': '周日晚 19:00-20:00', 'max': 20},
    ]

    my_code = request.args.get('code', '')
    my_student = None
    if my_code:
        my_student = Student.query.filter_by(access_code=my_code).first()

    # 统计每个时段的预约数
    for s in sessions:
        s['booked'] = Booking.query.filter(
            func.date(Booking.course_date) == s['date'],
            Booking.course_session == s['key'],
            Booking.status == 'booked',
        ).count()
        s['remaining'] = s['max'] - s['booked']

        # 检查当前学员是否已预约
        if my_student:
            existing = Booking.query.filter_by(
                student_id=my_student.id,
                course_date=s['date'],
                course_session=s['key'],
                status='booked',
            ).first()
            if existing:
                s['my_booking'] = True
                s['booking_id'] = existing.id
            else:
                s['my_booking'] = False

    # 所有在读学员（供无码时选择）
    active_students = Student.query.filter_by(is_active=True).order_by(Student.name).all()

    return render_template('parent/booking.html',
                           sessions=sessions,
                           my_student=my_student,
                           my_code=my_code,
                           students=active_students)


@fitness_bp.route('/booking/create', methods=['POST'])
def booking_create():
    """AJAX 创建预约"""
    student_id = request.form.get('student_id', type=int)
    course_date = request.form.get('course_date', '')
    course_session = request.form.get('course_session', '')

    if not student_id or not course_date or not course_session:
        return jsonify({'ok': False, 'error': '缺少参数'}), 400

    # 检查重复
    existing = Booking.query.filter_by(
        student_id=student_id,
        course_date=datetime.strptime(course_date, '%Y-%m-%d').date(),
        course_session=course_session,
        status='booked',
    ).first()
    if existing:
        return jsonify({'ok': False, 'error': '该时段已预约'})

    b = Booking(
        student_id=student_id,
        course_date=datetime.strptime(course_date, '%Y-%m-%d').date(),
        course_session=course_session,
    )
    db.session.add(b)
    db.session.commit()
    return jsonify({'ok': True, 'booking_id': b.id})


@fitness_bp.route('/booking/cancel', methods=['POST'])
def booking_cancel():
    """AJAX 取消预约"""
    booking_id = request.form.get('booking_id', type=int)
    b = Booking.query.get(booking_id)
    if not b or b.status != 'booked':
        return jsonify({'ok': False, 'error': '预约不存在或已取消'}), 400

    b.status = 'cancelled'
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════════════════════════════════════════════════
# 教练内容后台
# ═══════════════════════════════════════════════════════════════

@fitness_bp.route('/coach/content')
@coach_required
def coach_content():
    """教练内容后台：内容日历 + 生成"""
    from content_engine import generate_weekly_report, generate_progress_stars, generate_matchups, generate_booking_reminder, generate_coach_knowledge, generate_coach_knowledge_dynamic
    from datetime import date as dt_date, timedelta

    today = dt_date.today()
    weekday = today.weekday()  # 0=Mon, 6=Sun

    # 允许 ?type= 强制切换内容类型用于预览
    force_type = request.args.get('type', '').strip()

    # 今天应该发什么内容
    daily_content_map = {
        0: ('weekly_report', '📊 周报战报', 'weekly_report'),
        1: ('progress_star', '⭐ 进步之星', 'progress_star'),
        2: ('matchup', '⚔️ 对决预告', 'matchup'),
        3: ('coach_knowledge', '🧠 教练知识卡', 'coach_knowledge'),
        4: ('booking_reminder', '📋 上课提醒', 'booking_reminder'),
        5: ('session_report', '📸 实时战报', 'session_report'),
        6: ('session_report', '📸 实时战报', 'session_report'),
    }

    content_key, content_label, template_key = daily_content_map.get(
        weekday, ('weekly_report', '📊 周报', 'weekly_report'))

    # 允许 ?type= 强制切换内容类型用于预览
    if force_type:
        type_map = {
            'weekly_report': ('weekly_report', '📊 周报战报', 'weekly_report'),
            'progress_star': ('progress_star', '⭐ 进步之星', 'progress_star'),
            'matchup': ('matchup', '⚔️ 对决预告', 'matchup'),
            'coach_knowledge': ('coach_knowledge', '🧠 教练知识卡', 'coach_knowledge'),
            'booking_reminder': ('booking_reminder', '📋 上课提醒', 'booking_reminder'),
            'session_report': ('session_report', '📸 实时战报', 'session_report'),
        }
        if force_type in type_map:
            content_key, content_label, template_key = type_map[force_type]

    # 生成本周内容预览
    preview = None
    if content_key == 'weekly_report':
        preview = generate_weekly_report()
    elif content_key == 'progress_star':
        preview = generate_progress_stars()
    elif content_key == 'matchup':
        preview = generate_matchups()
    elif content_key == 'booking_reminder':
        preview = generate_booking_reminder()
    elif content_key == 'coach_knowledge':
        if request.args.get('dynamic'):
            preview = generate_coach_knowledge_dynamic()
            if not preview:
                preview = generate_coach_knowledge()  # fallback to static
        else:
            topic_idx = request.args.get('topic', type=int)
            preview = generate_coach_knowledge(topic_index=topic_idx)

    # 历史记录
    logs = ContentLog.query.order_by(ContentLog.created_at.desc()).limit(20).all()

    return render_template('coach/content.html',
                           today=today,
                           content_key=content_key,
                           content_label=content_label,
                           template_key=template_key,
                           preview=preview,
                           logs=logs)


@fitness_bp.route('/coach/settings', methods=['GET', 'POST'])
@coach_required
def coach_settings():
    """教练端：系统设置（LLM API Key 等）"""
    from llm_utils import get_llm_config

    if request.method == 'POST':
        keys = ['LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL']
        for k in keys:
            v = request.form.get(k, '').strip()
            s = Setting.query.filter_by(key=k).first()
            if v:
                if s:
                    s.value = v
                else:
                    db.session.add(Setting(key=k, value=v))
            elif s:
                db.session.delete(s)  # empty value → remove override
        db.session.commit()
        return redirect(url_for('fitness.coach_settings'))

    config = get_llm_config()
    # 判断当前用的是数据库配置还是 .env
    db_keys = {}
    for s in Setting.query.all():
        db_keys[s.key] = s.value

    return render_template('coach/settings.html',
                           config=config,
                           db_keys=db_keys)


@fitness_bp.route('/coach/bookings')
@coach_required
def coach_bookings():
    """教练端：预约总览"""
    from datetime import date as dt_date, timedelta
    today = dt_date.today()
    days_until_friday = (4 - today.weekday()) % 7
    friday = today + timedelta(days=days_until_friday)

    sessions = [
        ('friday_evening', '周五晚', friday),
        ('saturday_afternoon', '周六下午', friday + timedelta(days=1)),
        ('saturday_evening', '周六晚', friday + timedelta(days=1)),
        ('sunday_afternoon', '周日下午', friday + timedelta(days=2)),
        ('sunday_evening', '周日晚', friday + timedelta(days=2)),
    ]

    bookings_data = []
    total_booked = 0
    for key, label, d in sessions:
        bookings = Booking.query.filter(
            func.date(Booking.course_date) == d,
            Booking.course_session == key,
        ).order_by(Booking.created_at.asc()).all()
        booked_count = len([b for b in bookings if b.status == 'booked'])
        total_booked += booked_count
        bookings_data.append({
            'key': key,
            'label': label,
            'date': d,
            'bookings': bookings,
            'count': booked_count,
        })

    return render_template('coach/bookings.html',
                           bookings_data=bookings_data,
                           total_booked=total_booked)
