"""事件检测引擎 — 扫描数据库发现有推送价值的动态"""

from datetime import date, datetime, timedelta
from sqlalchemy import func

from models import (
    db, Student, CheckIn, Assessment, StudentBadge, BadgeTemplate,
    RANK_TIERS, ATTR_NAMES
)


def detect_rank_changes(current_rank, previous_rank):
    """
    检测排名变化。
    Args:
        current_rank: 当前排名 (int) 或 None（未上榜）
        previous_rank: 上周排名 (int) 或 None（首次上榜）
    Returns:
        { type: 'rank_up'|'rank_down'|'stable', delta: int }
    """
    if previous_rank is None:
        return {
            'type': 'rank_up',
            'delta': 0,
            'reason': '首次上榜',
        }
    delta = previous_rank - current_rank  # 正数 = 上升
    if delta >= 3:
        return {'type': 'rank_up', 'delta': delta}
    elif delta <= -3:
        return {'type': 'rank_down', 'delta': abs(delta)}
    return {'type': 'stable', 'delta': delta}


def detect_new_record(student_id, metric):
    """
    检测某学员在某项评估指标上是否创个人最佳。
    metric: 'seated_forward_bend' | 'standing_long_jump' | 'shuttle_run' |
             'rope_skip' | 'sit_up' | 'balance_score'
    """
    assessments = Assessment.query.filter(
        Assessment.student_id == student_id
    ).order_by(Assessment.date.asc()).all()

    values = [getattr(a, metric) for a in assessments if getattr(a, metric) is not None]
    if len(values) < 2:
        return None

    latest = values[-1]
    previous_best = min(values[:-1]) if metric == 'shuttle_run' else max(values[:-1])

    if metric == 'shuttle_run':
        is_record = latest < previous_best
    else:
        is_record = latest > previous_best

    if is_record:
        return {
            'type': 'new_record',
            'metric': metric,
            'new_value': latest,
            'previous_best': previous_best,
        }
    return None


def detect_tier_up(old_score, new_score):
    """检测段位晋升"""
    def get_tier(score):
        for t in RANK_TIERS:
            if t['min'] <= score <= t['max']:
                return t
        return RANK_TIERS[0]

    old_tier = get_tier(old_score)
    new_tier = get_tier(new_score)

    if RANK_TIERS.index(new_tier) > RANK_TIERS.index(old_tier):
        return {
            'type': 'tier_up',
            'from_tier': old_tier['name'],
            'to_tier': new_tier['name'],
            'from_icon': old_tier['icon'],
            'to_icon': new_tier['icon'],
            'old_score': old_score,
            'new_score': new_score,
        }
    return None


def detect_streak_broken(student, had_checkin_this_week):
    """检测连续出勤中断"""
    streak = student.streak_days
    if streak >= 3 and not had_checkin_this_week:
        return {
            'type': 'streak_broken',
            'previous_streak': streak,
        }
    return None


def detect_comeback(student):
    """检测回归学员: 上次打卡 ≥ 14 天前"""
    last_checkin = CheckIn.query.filter(
        CheckIn.student_id == student.id,
        CheckIn.status == 'confirmed',
    ).order_by(CheckIn.checkin_time.desc()).first()

    if not last_checkin:
        return None

    days_ago = (datetime.utcnow() - last_checkin.checkin_time).days
    if days_ago >= 14:
        return {
            'type': 'comeback',
            'days_gone': days_ago,
        }
    return None


def detect_first_checkin(student):
    """检测首次打卡"""
    count = student.total_checkins
    if count == 1:
        return {'type': 'first_checkin'}
    return None


# ── 全库扫描 ─────────────────────────────────────────

def scan_all_events(active_students=None):
    """
    扫描全库，返回所有待推送事件。
    返回: [ { student_id, student_name, type, ... } ]
    """
    if active_students is None:
        active_students = Student.query.filter_by(is_active=True).all()

    events = []
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    for s in active_students:
        # 首次打卡
        first = detect_first_checkin(s)
        if first:
            events.append({
                **first,
                'student_id': s.id,
                'student_name': s.name,
                'access_code': s.access_code,
                'priority': 'high',
            })

        # 连续出勤中断：本周未打卡但有连续记录
        this_week_checkins = s.checkins.filter(
            CheckIn.status == 'confirmed',
            func.date(CheckIn.checkin_time) >= week_start,
        ).count()
        streak_event = detect_streak_broken(s, this_week_checkins > 0)
        if streak_event:
            events.append({
                **streak_event,
                'student_id': s.id,
                'student_name': s.name,
                'access_code': s.access_code,
                'priority': 'medium',
            })

        # 回归学员
        comeback = detect_comeback(s)
        if comeback:
            events.append({
                **comeback,
                'student_id': s.id,
                'student_name': s.name,
                'access_code': s.access_code,
                'priority': 'low',
            })

        # 个人新纪录：检查所有评估指标
        for metric in ['seated_forward_bend', 'standing_long_jump', 'shuttle_run',
                       'rope_skip', 'sit_up', 'balance_score']:
            record = detect_new_record(s.id, metric)
            if record:
                events.append({
                    **record,
                    'student_id': s.id,
                    'student_name': s.name,
                    'access_code': s.access_code,
                    'priority': 'high',
                })

        # 最近获得的奖章 (3天内)
        recent_cutoff = datetime.utcnow() - timedelta(days=3)
        recent_badges = s.badges.filter(
            StudentBadge.awarded_date >= recent_cutoff
        ).all()
        for sb in recent_badges:
            events.append({
                'type': 'badge_earned',
                'badge_name': sb.template.name,
                'badge_icon': sb.template.icon,
                'student_id': s.id,
                'student_name': s.name,
                'access_code': s.access_code,
                'priority': 'high',
            })

    # 按优先级排序
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    events.sort(key=lambda e: priority_order.get(e.get('priority', 'low'), 3))

    return events


def format_event_for_group(event):
    """将事件格式化为适合群发的文案"""
    name = event.get('student_name', '学员')
    templates = {
        'rank_up': f'📈 {name} 排名上升 {event.get("delta", "?")} 位！继续加油！',
        'rank_down': f'📉 {name} 排名下降 {event.get("delta", "?")} 位，周末记得来训练！',
        'new_record': f'🎯 {name} 在 {event.get("metric", "某项目")} 创造个人最佳 {event.get("new_value", "?")}！突破自我！',
        'tier_up': f'🎊 {name} 从「{event.get("from_tier", "")}」晋升到「{event.get("to_tier", "?")}」！',
        'streak_broken': f'⚠️ {name} 的 {event.get("previous_streak", "?")} 天连续出勤中断了，这周末快来补课吧！',
        'first_checkin': f'🎉 欢迎 {name} 第一次打卡！加入春夏体适能大家庭！',
        'comeback': f'👋 {name} 回来了！时隔 {event.get("days_gone", "?")} 天再次训练，欢迎回归！',
        'badge_earned': f'🏅 {name} 获得新奖章「{event.get("badge_name", "?")}」{event.get("badge_icon", "")}！',
    }
    return templates.get(event['type'], '')


def get_metric_name(metric_key):
    """评估指标的显示名称"""
    names = {
        'seated_forward_bend': '坐位体前屈',
        'standing_long_jump': '立定跳远',
        'shuttle_run': '折返跑',
        'rope_skip': '跳绳',
        'sit_up': '仰卧起坐',
        'balance_score': '闭眼单脚站立',
    }
    return names.get(metric_key, metric_key)
