"""群内容引擎 — 生成每周/每日的群发内容"""

from datetime import date, datetime, timedelta
from sqlalchemy import func

from models import (
    db, Student, CheckIn, Course, Assessment, Setting, Photo,
    ATTR_NAMES, ATTR_ICONS,
)
from events import scan_all_events, format_event_for_group


# ═══════════════════════════════════════════════════════════════
# 内容类型体系（按心理功能分类）
# ═══════════════════════════════════════════════════════════════

CONTENT_TYPES = {
    'expert_trust': {
        'label': '👨‍🏫 教练观点',
        'psychology': '信任+IP',
        'description': '建立教练专业权威，让家长信任',
        'suitable': ['cold_start', 'active'],
        'llm_topic': True,
    },
    'science_edu': {
        'label': '🎓 专业科普',
        'psychology': '信任+收藏',
        'description': '儿童体能知识，收藏价值高',
        'suitable': ['cold_start', 'active'],
        'llm_topic': True,
    },
    'pain_point': {
        'label': '💬 痛点共鸣',
        'psychology': '互动+讨论',
        'description': '击中家长焦虑，引发回应',
        'suitable': ['cold_start', 'active'],
        'llm_topic': True,
    },
    'contrarian': {
        'label': '🔥 反常识',
        'psychology': '流量+破冰',
        'description': '颠覆认知，最容易引发讨论',
        'suitable': ['cold_start', 'active'],
        'llm_topic': True,
    },
    'practical_tip': {
        'label': '🎯 实用技巧',
        'psychology': '收藏+口碑',
        'description': '回家就能用，家长愿意转发',
        'suitable': ['cold_start', 'active'],
        'llm_topic': True,
    },
    'student_story': {
        'label': '📖 学员故事',
        'psychology': '情感+转发',
        'description': '真实变化，最容易打动人',
        'suitable': ['active'],
        'needs_data': True,
    },
    'urgency_drive': {
        'label': '⚡ 紧迫驱动',
        'psychology': '转化+行动',
        'description': '制造合理紧迫感，促进预约',
        'suitable': ['active'],
        'llm_topic': True,
    },
    'data_report': {
        'label': '🏆 数据战报',
        'psychology': '荣誉+社交',
        'description': '排名/进步/奖章，驱动分享',
        'suitable': ['active'],
        'needs_data': True,
    },
    'victory_report': {
        'label': '🎉 荣誉喜报',
        'psychology': '荣誉+炫耀',
        'description': '比赛成绩/新纪录/升学喜报，引爆群聊',
        'suitable': ['active'],
        'needs_data': True,
    },
    'transformation': {
        'label': '📸 成长见证',
        'psychology': '视觉冲击+信任',
        'description': '前后对比图，体态/成绩变化一目了然',
        'suitable': ['active'],
        'needs_data': True,
    },
}


def get_content_mode():
    """读取当前运营模式：cold_start 或 active"""
    try:
        s = Setting.query.filter_by(key='CONTENT_MODE').first()
        if s and s.value in ('cold_start', 'active'):
            return s.value
    except Exception:
        pass
    return 'cold_start'  # 默认冷启动


def get_content_calendar(mode=None):
    """
    根据模式返回内容日历。
    cold_start: 每周 2 次，轮换信任/科普/痛点/反常识/实用技巧
    active:     每周 4 次，全部类型参与轮换
    返回 [(weekday, content_type_key, label), ...]
    """
    if mode is None:
        mode = get_content_mode()

    if mode == 'cold_start':
        # 周三 + 周六，轮换 5 种不需要数据的类型
        cold_types = ['science_edu', 'pain_point', 'contrarian', 'expert_trust', 'practical_tip']
        # 根据周数决定轮换
        week_num = date.today().isocalendar()[1]
        wed_type = cold_types[week_num % len(cold_types)]
        sat_type = cold_types[(week_num + 1) % len(cold_types)]
        return [
            (2, wed_type, CONTENT_TYPES[wed_type]['label']),    # 周三
            (5, sat_type, CONTENT_TYPES[sat_type]['label']),    # 周六
        ]
    else:
        # 活跃期：周一/三/五/日，4 次/周
        all_types = list(CONTENT_TYPES.keys())
        week_num = date.today().isocalendar()[1]
        return [
            (0, all_types[(week_num + 0) % len(all_types)], CONTENT_TYPES[all_types[(week_num + 0) % len(all_types)]]['label']),
            (2, all_types[(week_num + 2) % len(all_types)], CONTENT_TYPES[all_types[(week_num + 2) % len(all_types)]]['label']),
            (4, all_types[(week_num + 4) % len(all_types)], CONTENT_TYPES[all_types[(week_num + 4) % len(all_types)]]['label']),
            (6, all_types[(week_num + 6) % len(all_types)], CONTENT_TYPES[all_types[(week_num + 6) % len(all_types)]]['label']),
        ]


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


# ── 荣誉喜报 ─────────────────────────────────────────

def generate_victory_report():
    """
    生成荣誉喜报：扫描近期高价值事件，每学员只展示最亮眼的一条成就。
    first_checkin 和 badge_earned 只在 7 天内有效，避免老事件反复出现。
    """
    from events import scan_all_events, get_metric_name

    active_students = Student.query.filter_by(is_active=True).all()
    all_events = scan_all_events(active_students)

    # 按优先级筛选：只取 high
    featured = [e for e in all_events if e.get('priority') == 'high']

    # 限制时间窗口：first_checkin / badge_earned 只在 7 天内有效
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent = []
    for e in featured:
        if e['type'] in ('first_checkin', 'badge_earned', 'comeback'):
            # 这些事件需要近期发生
            s = Student.query.get(e.get('student_id'))
            if s:
                last_ci = CheckIn.query.filter(
                    CheckIn.student_id == s.id,
                    CheckIn.status == 'confirmed',
                ).order_by(CheckIn.checkin_time.desc()).first()
                if not last_ci or last_ci.checkin_time < cutoff:
                    continue
        recent.append(e)

    # 按学员分组，每学员只保留优先级最高的一条
    student_best = {}  # student_id -> best event
    type_rank = {'tier_up': 0, 'badge_earned': 1, 'new_record': 2, 'first_checkin': 3, 'comeback': 4}

    for e in recent:
        sid = e.get('student_id')
        rank = type_rank.get(e['type'], 99)
        if sid not in student_best or rank < type_rank.get(student_best[sid]['type'], 99):
            student_best[sid] = e

    # 格式化
    items = []
    for e in student_best.values():
        name = e.get('student_name', '学员')
        student = Student.query.get(e.get('student_id'))
        avatar = student.avatar_emoji if student else '⭐'

        if e['type'] == 'new_record':
            metric_name = get_metric_name(e.get('metric', ''))
            items.append({
                'avatar': avatar, 'student_name': name,
                'achievement': f'在「{metric_name}」创造个人最佳',
                'detail': f'{e.get("previous_best", "?")} → {e.get("new_value", "?")}',
                'emoji': '🎯',
            })
        elif e['type'] == 'tier_up':
            items.append({
                'avatar': avatar, 'student_name': name,
                'achievement': f'段位晋升：{e.get("from_tier", "")} → {e.get("to_tier", "")}',
                'detail': f'体质分 {e.get("old_score", 0)} → {e.get("new_score", 0)}',
                'emoji': '🎊',
            })
        elif e['type'] == 'badge_earned':
            items.append({
                'avatar': avatar, 'student_name': name,
                'achievement': f'获得奖章「{e.get("badge_name", "?")}」',
                'detail': e.get('badge_icon', '🏅'),
                'emoji': '🏅',
            })
        elif e['type'] == 'first_checkin':
            items.append({
                'avatar': avatar, 'student_name': name,
                'achievement': '加入春夏体适能大家庭',
                'detail': '欢迎新伙伴 🎉',
                'emoji': '🎉',
            })
        elif e['type'] == 'comeback':
            items.append({
                'avatar': avatar, 'student_name': name,
                'achievement': f'回归训练！时隔 {e.get("days_gone", "?")} 天',
                'detail': '欢迎回来 👋',
                'emoji': '👋',
            })

    items = items[:6]

    today = date.today()
    return {
        'title': f'🎉 荣誉喜报 · {today.strftime("%m/%d")}',
        'items': items,
        'count': len(items),
        'highlight': f'本周 {len(items)} 位学员取得突破' if items else '期待下周的精彩表现',
    }


# ── 成长见证（前后对比） ─────────────────────────────

def generate_transformation():
    """
    生成成长见证：找出评估数据变化最大的学员，
    展示前后对比数据。优先选择有照片的学员。
    """
    active_students = Student.query.filter_by(is_active=True).all()
    results = []

    for s in active_students:
        assessments = s.assessments.order_by(Assessment.date.asc()).all()
        if len(assessments) < 2:
            continue

        first = assessments[0]
        last = assessments[-1]

        # 找出改善最大的指标
        best_metric = None
        best_pct = 0
        metrics = [
            ('rope_skip', '跳绳', '次', False),
            ('standing_long_jump', '立定跳远', 'cm', False),
            ('sit_up', '仰卧起坐', '次', False),
            ('seated_forward_bend', '坐位体前屈', 'cm', False),
            ('shuttle_run', '折返跑', 's', True),
        ]

        for attr, label, unit, lower_better in metrics:
            old_val = getattr(first, attr)
            new_val = getattr(last, attr)
            if old_val and new_val and old_val > 0 and old_val != new_val:
                if lower_better:
                    pct = round((old_val - new_val) / old_val * 100, 1)
                else:
                    pct = round((new_val - old_val) / old_val * 100, 1)
                if pct > best_pct:
                    best_pct = pct
                    best_metric = {
                        'label': label,
                        'unit': unit,
                        'old_val': old_val,
                        'new_val': new_val,
                        'improvement_pct': pct,
                        'lower_better': lower_better,
                    }

        if best_metric and best_pct >= 5:
            # 获取照片：优先取有标签的照片
            photos = s.photos.filter_by(is_tagged=True).order_by(
                Photo.upload_date.desc()
            ).limit(2).all() if hasattr(s, 'photos') else []

            results.append({
                'student_name': s.name,
                'access_code': s.access_code,
                'avatar_emoji': s.avatar_emoji,
                'face_photo_path': s.face_photo_path,
                'photos': [{'path': p.file_path} for p in photos],
                'metric': best_metric,
                'first_date': str(first.date),
                'last_date': str(last.date),
                'total_checkins': s.total_checkins,
            })

    # 按改善幅度排序，取 TOP 3
    results.sort(key=lambda r: r['metric']['improvement_pct'], reverse=True)
    top3 = results[:3]

    today = date.today()
    return {
        'title': f'📸 成长见证 · {today.strftime("%m/%d")}',
        'transformations': top3,
        'count': len(top3),
        'highlight': f'{len(top3)} 位学员的惊人变化' if top3 else '积累更多数据后将展示对比',
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


def generate_coach_knowledge_dynamic(content_type=None):
    """
    使用 LLM 动态生成教练知识卡主题。
    根据 content_type 调整提示词策略，匹配对应的心理功能。
    避免与已有静态题库重复。
    返回 dict: { category, icon, title, points, coach_note, dynamic: True }
    """
    from llm_utils import chat_json

    existing_titles = [t['title'] for t in COACH_KNOWLEDGE_TOPICS]
    existing_str = '\n'.join(f'- {t}' for t in existing_titles)

    # 根据内容类型定制提示词
    type_guides = {
        'expert_trust': {
            'role': '儿童体适能资深教练，10年+教学经验',
            'angle': '展示教练的专业判断和经验，让家长觉得"这个教练懂行"。用第一人称教练视角，分享独到见解。',
            'tone': '自信、有观点、不盲从流行说法',
            'categories': '训练知识、姿势纠正、成长发育',
        },
        'science_edu': {
            'role': '儿童运动科学专家',
            'angle': '用科学研究和数据说话，解释"为什么"。引用运动生理学/神经科学原理，让家长觉得有收藏价值。',
            'tone': '专业、严谨、深入浅出',
            'categories': '儿童体适能科普、感统训练、成长发育',
        },
        'pain_point': {
            'role': '懂家长的儿童体能教练',
            'angle': '击中家长最常见的焦虑：孩子坐不住、驼背、体质差、中考体育。先共鸣痛点，再给解决方案。',
            'tone': '共情、直接、不绕弯子',
            'categories': '姿势纠正、感统训练、运动心理、家庭训练小技巧',
        },
        'contrarian': {
            'role': '敢于挑战常识的儿童体能专家',
            'angle': '颠覆一个家长普遍相信但其实是误解的观点（如"运动耽误学习""孩子太小不能练力量""跳绳伤膝盖"）。用证据反驳，制造认知冲突。',
            'tone': '犀利、有冲击力、但有理有据',
            'categories': '训练知识、儿童体适能科普、营养建议',
        },
        'practical_tip': {
            'role': '接地气的儿童体能教练',
            'angle': '给出家长回家就能用的具体方法，最好是"每天X分钟""不用器材""在家就能做"。实操性强，方便转发。',
            'tone': '实用、亲切、step-by-step',
            'categories': '家庭训练小技巧、姿势纠正、营养建议',
        },
        'urgency_drive': {
            'role': '儿童体能教育专家',
            'angle': '制造合理的紧迫感：窗口期有限、中考倒计时、错过敏感期效率减半。不要恐吓，要用数据和阶段特征让家长意识到"现在就是最佳时机"。',
            'tone': '紧迫但不焦虑、数据驱动、行动导向',
            'categories': '儿童体适能科普、成长发育、训练知识',
        },
    }

    guide = type_guides.get(content_type) if content_type else None

    if guide:
        prompt = f"""你是一个{guide['role']}。请生成一个"教练知识卡"主题，用于发到家长微信群。

内容策略：{guide['angle']}
语气：{guide['tone']}
推荐分类：{guide['categories']}

要求：
1. category: 从推荐分类中选一个
2. icon: 一个与主题相关的 emoji
3. title: 标题要有吸引力，契合{CONTENT_TYPES.get(content_type, {}).get('label', '')}的内容定位
4. points: 4-5 个知识点，每个 15-30 字，要有科学依据或具体数据
5. coach_note: 教练的口语化点评，1-2 句话，要有观点、接地气

已有主题（请避免重复或太相似）：
{existing_str}

请直接输出 JSON 格式：
{{"category": "...", "icon": "...", "title": "...", "points": ["...", "..."], "coach_note": "..."}}"""
    else:
        prompt = f"""你是一个儿童体适能教练专家。请生成一个"教练知识卡"主题，用于发到家长微信群，建立教练专业形象。

要求：
1. category: 从以下分类中选一个：儿童体适能科普、家庭训练小技巧、营养建议、姿势纠正、感统训练、训练知识、运动心理、成长发育
2. icon: 一个与主题相关的 emoji
3. title: 吸引人的标题，用问句或数字开头更好（如"为什么...""每天 X 分钟...""孩子...可能不是...问题"）
4. points: 4-5 个知识点，每个 15-30 字，要有科学依据或具体数据
5. coach_note: 教练的口语化点评，1-2 句话，要有观点、接地气

已有主题（请避免重复或太相似）：
{existing_str}

请直接输出 JSON 格式：
{{"category": "...", "icon": "...", "title": "...", "points": ["...", "..."], "coach_note": "..."}}"""

    result = chat_json(prompt, temperature=0.9, max_tokens=2000)
    if result:
        result['dynamic'] = True
        result['index'] = -1  # marker for dynamic content
        result['total'] = len(COACH_KNOWLEDGE_TOPICS)
        return result
    return None
