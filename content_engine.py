"""群内容引擎 — 生成每周/每日的群发内容"""

from datetime import date, datetime, timedelta
from sqlalchemy import func

from models import (
    db, Student, CheckIn, Course, Assessment,
    ATTR_NAMES, ATTR_ICONS,
)
from events import scan_all_events, format_event_for_group


# ── 周报 ─────────────────────────────────────────────

def generate_weekly_report(dim='fitness'):
    """
    生成周报数据：排名变动 TOP 5 + 本周之星 + 出勤统计。
    返回 dict 可用于模板渲染。
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)

    active_students = Student.query.filter_by(is_active=True).all()

    # 本周出勤统计
    this_week_checkins = CheckIn.query.filter(
        CheckIn.status == 'confirmed',
        func.date(CheckIn.checkin_time) >= week_start,
        func.date(CheckIn.checkin_time) <= today,
    ).count()

    # 上周出勤统计（用于对比）
    last_week_checkins = CheckIn.query.filter(
        CheckIn.status == 'confirmed',
        func.date(CheckIn.checkin_time) >= last_week_start,
        func.date(CheckIn.checkin_time) < week_start,
    ).count()

    total_students = len(active_students)
    stats = {
        'this_week_checkins': this_week_checkins,
        'last_week_checkins': last_week_checkins,
        'total_students': total_students,
        'avg_checkins': round(this_week_checkins / total_students, 1) if total_students > 0 else 0,
    }

    # 本周之星：打卡最多的学员
    star_of_week = None
    max_checkins = 0
    for s in active_students:
        count = s.checkins.filter(
            CheckIn.status == 'confirmed',
            func.date(CheckIn.checkin_time) >= week_start,
        ).count()
        if count > max_checkins:
            max_checkins = count
            star_of_week = {
                'student_name': s.name,
                'access_code': s.access_code,
                'avatar_emoji': s.avatar_emoji,
                'face_photo_path': s.face_photo_path,
                'checkins': count,
                'fitness_score': s.fitness_score,
                'rank_tier': s.rank_tier,
            }

    # 本周事件
    events = scan_all_events(active_students)

    # 排名变动：对比上周（简化版：用 fitness_score 变化推测排名变动）
    top_changes = _compute_rank_changes(active_students, week_start, dim)

    return {
        'title': f'📊 周报 · {week_start.strftime("%m/%d")}-{today.strftime("%m/%d")}',
        'stats': stats,
        'star_of_week': star_of_week,
        'top_changes': top_changes[:5],
        'events': events[:10],  # 最多 10 条事件
        'dim': dim,
    }


def _compute_rank_changes(students, week_start, dim):
    """计算排名变动（基于 fitness_score 变化）"""
    changes = []
    for s in students:
        # 本周前 vs 本周后的分数变化
        # 简化：比较最近一次打卡前后的分数
        recent_checkins = s.checkins.filter(
            CheckIn.status == 'confirmed',
            func.date(CheckIn.checkin_time) >= week_start,
        ).count()

        if recent_checkins > 0:
            changes.append({
                'student_name': s.name,
                'access_code': s.access_code,
                'checkins_this_week': recent_checkins,
                'current_score': s.fitness_score,
                'rank_tier': s.rank_tier,
            })

    changes.sort(key=lambda c: c['checkins_this_week'], reverse=True)
    return changes


# ── 进步之星 ─────────────────────────────────────────

def generate_progress_stars():
    """
    进步最快 TOP 3：比较最早和最新评估数据。
    """
    active_students = Student.query.filter_by(is_active=True).all()
    results = []

    for s in active_students:
        assessments = s.assessments.order_by(Assessment.date.asc()).all()
        if len(assessments) < 2:
            continue

        first = assessments[0]
        last = assessments[-1]

        # 计算综合进步率（各项指标改善百分比的平均）
        improvements = []
        metrics = [
            ('seated_forward_bend', False),
            ('standing_long_jump', False),
            ('shuttle_run', True),  # 越小越好
            ('rope_skip', False),
            ('sit_up', False),
        ]

        for metric, lower_is_better in metrics:
            old_val = getattr(first, metric)
            new_val = getattr(last, metric)
            if old_val and new_val and old_val > 0:
                if lower_is_better:
                    pct = (old_val - new_val) / old_val * 100
                else:
                    pct = (new_val - old_val) / old_val * 100
                improvements.append(pct)

        if improvements:
            avg_improvement = sum(improvements) / len(improvements)
            results.append({
                'student_name': s.name,
                'access_code': s.access_code,
                'avatar_emoji': s.avatar_emoji,
                'face_photo_path': s.face_photo_path,
                'improvement_pct': round(avg_improvement, 1),
                'first_assessment_date': str(first.date),
                'last_assessment_date': str(last.date),
                'coach_note': '',  # 教练手动填写
            })

    results.sort(key=lambda r: r['improvement_pct'], reverse=True)
    return results[:3]


# ── 对决预告 ─────────────────────────────────────────

def generate_matchups(dim='fitness', threshold=5):
    """
    生成对决预告：相邻排名且分差 < threshold 的学员配对。
    """
    from routes import get_student_ranking_data
    active_students = Student.query.filter_by(is_active=True).all()
    rankings = get_student_ranking_data(dim, active_students)

    matchups = []
    for i in range(len(rankings) - 1):
        gap = rankings[i]['score'] - rankings[i + 1]['score']
        if gap < threshold:
            matchups.append({
                'defender': {
                    'student_name': rankings[i]['name'],
                    'student_id': rankings[i]['id'],
                    'access_code': rankings[i]['access_code'],
                    'score': rankings[i]['score'],
                    'rank': rankings[i]['rank'],
                    'face_photo_path': rankings[i].get('face_photo_path'),
                    'avatar_emoji': rankings[i].get('avatar_emoji'),
                },
                'challenger': {
                    'student_name': rankings[i + 1]['name'],
                    'student_id': rankings[i + 1]['id'],
                    'access_code': rankings[i + 1]['access_code'],
                    'score': rankings[i + 1]['score'],
                    'rank': rankings[i + 1]['rank'],
                    'face_photo_path': rankings[i + 1].get('face_photo_path'),
                    'avatar_emoji': rankings[i + 1].get('avatar_emoji'),
                },
                'gap': gap,
                'dimension': dim,
            })

    return matchups


# ── 预约提醒 ─────────────────────────────────────────

def generate_booking_reminder():
    """
    生成周末预约提醒数据。
    """
    from datetime import date as dt_date, timedelta
    today = dt_date.today()
    # 计算本周末日期
    days_until_friday = (4 - today.weekday()) % 7
    friday = today + timedelta(days=days_until_friday)

    sessions_config = [
        {'session': 'friday_evening', 'date': friday, 'label': '周五晚', 'max_capacity': 20},
        {'session': 'saturday_afternoon', 'date': friday + timedelta(days=1), 'label': '周六下午', 'max_capacity': 20},
        {'session': 'saturday_evening', 'date': friday + timedelta(days=1), 'label': '周六晚', 'max_capacity': 20},
        {'session': 'sunday_afternoon', 'date': friday + timedelta(days=2), 'label': '周日下午', 'max_capacity': 20},
        {'session': 'sunday_evening', 'date': friday + timedelta(days=2), 'label': '周日晚', 'max_capacity': 20},
    ]

    # 获取已有预约数
    from models import Booking
    result = []
    for sc in sessions_config:
        booked = Booking.query.filter(
            func.date(Booking.course_date) == sc['date'],
            Booking.course_session == sc['session'],
            Booking.status == 'booked',
        ).count() if _has_booking_model() else 0

        remaining = sc['max_capacity'] - booked
        if remaining <= 0:
            urgency = '已满额'
        elif remaining <= 3:
            urgency = '即将满额'
        elif remaining <= 10:
            urgency = '热报中'
        else:
            urgency = '充足'

        result.append({
            'session': sc['session'],
            'date': sc['date'].isoformat(),
            'label': sc['label'],
            'max_capacity': sc['max_capacity'],
            'booked': booked,
            'remaining': remaining,
            'is_full': remaining <= 0,
            'urgency': urgency,
        })

    return result


def _has_booking_model():
    """检查 Booking 模型是否已创建"""
    try:
        from models import Booking
        return True
    except ImportError:
        return False


# ── 课后战报 ─────────────────────────────────────────

def generate_session_report(course_id=None):
    """
    生成单节课后战报。
    """
    today = date.today()
    query = CheckIn.query.filter(
        CheckIn.status == 'confirmed',
        func.date(CheckIn.checkin_time) == today,
    )
    if course_id:
        query = query.filter(CheckIn.course_id == course_id)

    today_checkins = query.all()
    checkin_count = len(today_checkins)

    # 获取课程名
    course_name = '今日训练'
    if course_id:
        course = Course.query.get(course_id)
        if course:
            course_name = course.name

    # 今天创造的新纪录
    new_records = []
    student_ids = set(ci.student_id for ci in today_checkins)
    for sid in student_ids:
        from events import detect_new_record
        for metric in ['rope_skip', 'sit_up', 'seated_forward_bend',
                       'standing_long_jump', 'shuttle_run']:
            record = detect_new_record(sid, metric)
            if record:
                student = Student.query.get(sid)
                record['student_name'] = student.name if student else str(sid)
                new_records.append(record)

    # 今天上传的照片数
    from models import Photo
    photos_count = Photo.query.filter(
        func.date(Photo.upload_date) == today,
    ).count()

    return {
        'course_name': course_name,
        'checkin_count': checkin_count,
        'new_records': new_records,
        'photos_count': photos_count,
        'highlight': (
            f'今天 {checkin_count} 位学员完成训练'
            + (f'，{len(new_records)} 人创造新纪录！' if new_records else '！')
        ),
    }


# ── 教练知识卡 ─────────────────────────────────────────

COACH_KNOWLEDGE_TOPICS = [
    {
        'category': '儿童体适能科普',
        'icon': '📚',
        'title': '为什么 3-12 岁是体能训练的黄金窗口？',
        'points': [
            '3-6 岁是神经发育关键期，协调性训练效果是成年后的 3 倍',
            '7-9 岁是速度素质敏感期，短跑和反应训练事半功倍',
            '10-12 岁进入力量训练窗口，但应以自重训练为主',
            '错过窗口期不是不能练，而是效率会显著降低',
        ],
        'coach_note': '很多家长等到中考体测才着急，其实 3 岁就可以开始了。体能和语数外一样，是积累型能力。',
    },
    {
        'category': '家庭训练小技巧',
        'icon': '🏠',
        'title': '每天 10 分钟，在家就能做的感统训练',
        'points': [
            '单脚站立刷牙 → 训练前庭觉和平衡能力',
            '趴地推球 3 分钟 → 改善注意力不集中',
            '钻桌子/爬行 → 本体觉刺激，提升身体感知',
            '闭眼走直线 → 空间感知 + 平衡双重训练',
        ],
        'coach_note': '感统训练不需要专业器材。日常小动作坚持做，比每周来练一次更有效。',
    },
    {
        'category': '营养建议',
        'icon': '🍎',
        'title': '训练前后吃什么？儿童运动营养指南',
        'points': [
            '训练前 1 小时：香蕉/全麦面包，提供缓释能量',
            '训练中：白开水即可，不要运动饮料（含糖太高）',
            '训练后 30 分钟：牛奶/鸡蛋/酸奶，蛋白质修复肌肉',
            '每天保证 800mg 钙 + 400IU 维生素 D',
        ],
        'coach_note': '运动饮料是给马拉松运动员的，不是给孩子跑 10 分钟的。一瓶可乐 = 孩子跑 3 公里消耗的热量。',
    },
    {
        'category': '姿势纠正',
        'icon': '🧘',
        'title': '孩子驼背/高低肩？可能不是习惯问题',
        'points': [
            '大部分儿童体态问题根源是核心肌群薄弱',
            '单纯说"挺直"没用，肌肉撑不住就自动塌回去',
            '平板支撑 + 超人式，每天 5 分钟，两周见效',
            '书包重量应 < 体重的 10%，双肩背优于单肩',
        ],
        'coach_note': '体态问题是肌肉问题，不是态度问题。练核心比唠叨 100 遍"坐直了"有效得多。',
    },
    {
        'category': '儿童体适能科普',
        'icon': '🧠',
        'title': '运动如何促进大脑发育？科学解读',
        'points': [
            '有氧运动促进 BDNF（脑源性神经营养因子）分泌，被称为"大脑肥料"',
            '协调性训练激活小脑，提升注意力和执行功能',
            '团队运动刺激前额叶，促进社交认知发展',
            '每天运动 60 分钟的孩子，学习成绩平均高出 12%',
        ],
        'coach_note': '"运动耽误学习"是最深的误解。运动是给大脑施肥，不是抢时间。',
    },
    {
        'category': '训练知识',
        'icon': '🏃',
        'title': '儿童体能训练 ≠ 缩小版成人训练',
        'points': [
            '12 岁前不推荐大重量负重训练，骨骺板未闭合',
            '高强度间歇对儿童效果有限，游戏化训练才是正道',
            '柔韧性训练要趁早，12 岁后柔韧提升难度翻倍',
            '多样化训练 > 单一专项化，过早专项化容易受伤',
        ],
        'coach_note': '见过太多家长让孩子练成人那种 HIIT。孩子需要的不是"虐"，是科学的刺激和充分的恢复。',
    },
    {
        'category': '感统训练',
        'icon': '🎯',
        'title': '孩子写作业坐不住？可能是前庭觉失调',
        'points': [
            '前庭系统是大脑的"总司令"，负责过滤信息噪音',
            '前庭失调的表现：坐不住、注意力差、阅读跳行',
            '旋转/摇摆/倒立类运动可有效刺激前庭系统',
            '每周 3 次前庭训练，6 周后注意力提升 40%',
        ],
        'coach_note': '坐不住不一定是孩子不乖。先看看是不是感统问题，再做行为干预。',
    },
    {
        'category': '训练知识',
        'icon': '💪',
        'title': '为什么跳绳是 3-12 岁最好的全身运动？',
        'points': [
            '跳绳同时锻炼心肺、协调、节奏感和下肢力量',
            '每天 500 个跳绳 = 慢跑 30 分钟的热量消耗',
            '3 分钟计数跳 = 预测儿童心肺耐力的金标准',
            '中考体育必考项，二年级开始练正好',
        ],
        'coach_note': '一根跳绳 5 块钱，比任何昂贵的兴趣班都值。关键是要坚持，不是偶尔跳 1000 个。',
    },
]


def generate_coach_knowledge(topic_index=None):
    """
    生成教练知识卡片。如果不指定 topic_index，则根据今天是星期几轮换。

    返回 dict: { topic, category, icon, title, points, coach_note, index }
    """
    if topic_index is not None:
        topic = COACH_KNOWLEDGE_TOPICS[topic_index % len(COACH_KNOWLEDGE_TOPICS)]
    else:
        # 根据今天是今年的第几周来轮换
        today = date.today()
        week_num = today.isocalendar()[1]
        topic = COACH_KNOWLEDGE_TOPICS[week_num % len(COACH_KNOWLEDGE_TOPICS)]

    idx = COACH_KNOWLEDGE_TOPICS.index(topic)
    return {
        **topic,
        'index': idx,
        'total': len(COACH_KNOWLEDGE_TOPICS),
    }
