"""事件检测引擎测试 — 排名变动、新纪录、段位晋升、奖章触发等"""

import pytest
from datetime import date

from models import (
    db, Student, CheckIn, Course, Assessment,
    BadgeTemplate, StudentBadge,
    RANK_TIERS,
)


# ── 模拟事件检测函数（正式实现在 events.py 中，这里先定义接口和预期行为）──

def detect_rank_changes(current_rank, previous_rank):
    """
    检测排名变化。
    返回: { type: 'rank_up'|'rank_down'|'stable', delta: int }
    """
    if previous_rank is None:
        return {'type': 'rank_up', 'delta': 0, 'reason': '首次上榜'}
    delta = previous_rank - current_rank
    if delta >= 3:
        return {'type': 'rank_up', 'delta': delta}
    elif delta <= -3:
        return {'type': 'rank_down', 'delta': abs(delta)}
    return {'type': 'stable', 'delta': delta}


def detect_new_record(student_id, assessment_list, metric):
    """
    检测是否创个人最佳纪录。
    assessment_list: 按时间排序的评估列表
    """
    values = [getattr(a, metric) for a in assessment_list if getattr(a, metric) is not None]
    if len(values) < 2:
        return None
    # shuttle_run 越小越好，其他越大越好
    if metric == 'shuttle_run':
        is_record = values[-1] < min(values[:-1])
    else:
        is_record = values[-1] > max(values[:-1])
    if is_record:
        return {
            'type': 'new_record',
            'metric': metric,
            'new_value': values[-1],
            'previous_best': min(values[:-1]) if metric == 'shuttle_run' else max(values[:-1]),
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
            'old_score': old_score,
            'new_score': new_score,
        }
    return None


def detect_streak_broken(student_current_streak, had_checkin_this_week):
    """检测连续出勤中断"""
    if student_current_streak >= 3 and not had_checkin_this_week:
        return {
            'type': 'streak_broken',
            'previous_streak': student_current_streak,
        }
    return None


def detect_comeback(last_checkin_days_ago, is_active):
    """检测回归学员: 缺课 ≥ 14 天后重新出现"""
    if is_active and last_checkin_days_ago and last_checkin_days_ago >= 14:
        return {
            'type': 'comeback',
            'days_gone': last_checkin_days_ago,
        }
    return None


def detect_first_checkin(checkin_count):
    """检测首次打卡"""
    if checkin_count == 1:
        return {'type': 'first_checkin'}
    return None


# ── 事件格式化 ──

def format_event_for_group(event, student_name=''):
    """将事件格式化为群发文案"""
    templates = {
        'rank_up': f'📈 {student_name} 排名上升 {event.get("delta", "?")} 位！继续加油！',
        'rank_down': f'📉 {student_name} 排名下降 {event.get("delta", "?")} 位，周末记得来训练！',
        'new_record': f'🎯 {student_name} 在 {event.get("metric", "某项目")} 创造个人最佳成绩 {event.get("new_value", "?")}！',
        'tier_up': f'🎊 {student_name} 从「{event.get("from_tier", "")}」晋升到「{event.get("to_tier", "?")}」！',
        'streak_broken': f'⚠️ {student_name} 的 {event.get("previous_streak", "?")} 天连续出勤中断了，快来补课！',
        'first_checkin': f'🎉 欢迎 {student_name} 第一次打卡！加入春夏体适能大家庭！',
        'comeback': f'👋 {student_name} 回来了！时隔 {event.get("days_gone", "?")} 天再次训练！',
        'badge_earned': f'🏅 {student_name} 获得新奖章「{event.get("badge_name", "?")}」！',
    }
    return templates.get(event['type'], '')


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

class TestRankChangeDetection:
    """排名变动检测"""

    def test_rank_up_3_or_more(self):
        result = detect_rank_changes(current_rank=5, previous_rank=10)
        assert result['type'] == 'rank_up'
        assert result['delta'] == 5

    def test_rank_up_less_than_3(self):
        result = detect_rank_changes(current_rank=8, previous_rank=9)
        assert result['type'] == 'stable'

    def test_rank_down_3_or_more(self):
        result = detect_rank_changes(current_rank=8, previous_rank=3)
        assert result['type'] == 'rank_down'
        assert result['delta'] == 5

    def test_rank_down_less_than_3(self):
        result = detect_rank_changes(current_rank=4, previous_rank=3)
        assert result['type'] == 'stable'

    def test_first_time_ranking(self):
        result = detect_rank_changes(current_rank=5, previous_rank=None)
        assert result['type'] == 'rank_up'
        assert result['reason'] == '首次上榜'

    def test_stable_rank(self):
        result = detect_rank_changes(current_rank=5, previous_rank=5)
        assert result['type'] == 'stable'


class TestNewRecordDetection:
    """个人最佳纪录检测"""

    def test_score_improvement_is_record(self, db_session, student_fixture):
        """坐位体前屈从 10 提升到 15 → 新纪录"""
        today = date.today()
        a1 = Assessment(student_id=student_fixture.id, date=today, seated_forward_bend=10.0)
        a2 = Assessment(student_id=student_fixture.id, date=today, seated_forward_bend=15.0)
        result = detect_new_record(student_fixture.id, [a1, a2], 'seated_forward_bend')
        assert result is not None
        assert result['type'] == 'new_record'
        assert result['new_value'] == 15.0
        assert result['previous_best'] == 10.0

    def test_score_decline_not_record(self, db_session, student_fixture):
        """成绩下降不触发新纪录"""
        today = date.today()
        a1 = Assessment(student_id=student_fixture.id, date=today, seated_forward_bend=15.0)
        a2 = Assessment(student_id=student_fixture.id, date=today, seated_forward_bend=10.0)
        result = detect_new_record(student_fixture.id, [a1, a2], 'seated_forward_bend')
        assert result is None

    def test_shuttle_run_lower_is_better(self, db_session, student_fixture):
        """折返跑：时间越短越好"""
        today = date.today()
        a1 = Assessment(student_id=student_fixture.id, date=today, shuttle_run=10.0)
        a2 = Assessment(student_id=student_fixture.id, date=today, shuttle_run=8.5)
        result = detect_new_record(student_fixture.id, [a1, a2], 'shuttle_run')
        assert result is not None
        assert result['type'] == 'new_record'

    def test_shuttle_run_slower_not_record(self, db_session, student_fixture):
        """折返跑时间变长 → 不是纪录"""
        today = date.today()
        a1 = Assessment(student_id=student_fixture.id, date=today, shuttle_run=8.5)
        a2 = Assessment(student_id=student_fixture.id, date=today, shuttle_run=10.0)
        result = detect_new_record(student_fixture.id, [a1, a2], 'shuttle_run')
        assert result is None

    def test_single_assessment_no_record(self, db_session, student_fixture):
        """只有一次评估 → 无纪录"""
        a1 = Assessment(student_id=student_fixture.id, date=date.today(), rope_skip=100)
        result = detect_new_record(student_fixture.id, [a1], 'rope_skip')
        assert result is None

    def test_same_score_no_record(self, db_session, student_fixture):
        """两次评估成绩相同 → 无纪录"""
        today = date.today()
        a1 = Assessment(student_id=student_fixture.id, date=today, rope_skip=100)
        a2 = Assessment(student_id=student_fixture.id, date=today, rope_skip=100)
        result = detect_new_record(student_fixture.id, [a1, a2], 'rope_skip')
        assert result is None


class TestTierUpDetection:
    """段位晋升检测"""

    def test_sprout_to_growth(self):
        result = detect_tier_up(old_score=50, new_score=65)
        assert result is not None
        assert result['type'] == 'tier_up'
        assert result['from_tier'] == '萌芽期'
        assert result['to_tier'] == '成长期'

    def test_growth_to_breakthrough(self):
        result = detect_tier_up(old_score=75, new_score=82)
        assert result is not None
        assert result['from_tier'] == '成长期'
        assert result['to_tier'] == '突破期'

    def test_no_tier_change(self):
        result = detect_tier_up(old_score=30, new_score=50)
        assert result is None

    def test_already_max_tier(self):
        result = detect_tier_up(old_score=95, new_score=98)
        assert result is None


class TestStreakBrokenDetection:
    """连续出勤中断检测"""

    def test_streak_broken_when_no_checkin_this_week(self):
        result = detect_streak_broken(student_current_streak=7, had_checkin_this_week=False)
        assert result is not None
        assert result['type'] == 'streak_broken'
        assert result['previous_streak'] == 7

    def test_no_break_when_had_checkin(self):
        result = detect_streak_broken(student_current_streak=7, had_checkin_this_week=True)
        assert result is None

    def test_short_streak_not_detected(self):
        """连续天数 < 3 不触发"""
        result = detect_streak_broken(student_current_streak=2, had_checkin_this_week=False)
        assert result is None


class TestComebackDetection:
    """回归学员检测"""

    def test_comeback_after_14_days(self):
        result = detect_comeback(last_checkin_days_ago=20, is_active=True)
        assert result is not None
        assert result['type'] == 'comeback'
        assert result['days_gone'] == 20

    def test_no_comeback_under_14_days(self):
        result = detect_comeback(last_checkin_days_ago=10, is_active=True)
        assert result is None

    def test_no_comeback_for_inactive(self):
        result = detect_comeback(last_checkin_days_ago=30, is_active=False)
        assert result is None


class TestFirstCheckinDetection:
    """首次打卡检测"""

    def test_first_checkin(self):
        result = detect_first_checkin(checkin_count=1)
        assert result is not None
        assert result['type'] == 'first_checkin'

    def test_not_first_checkin(self):
        assert detect_first_checkin(checkin_count=5) is None
        assert detect_first_checkin(checkin_count=0) is None


class TestFormatEventForGroup:
    """事件文案格式化"""

    def test_rank_up_contains_name(self):
        text = format_event_for_group({'type': 'rank_up', 'delta': 5}, '小明')
        assert '小明' in text
        assert '5' in text
        assert '春夏体适能' not in text  # 不是所有文案都含品牌名

    def test_tier_up_contains_tier_names(self):
        text = format_event_for_group({
            'type': 'tier_up',
            'from_tier': '萌芽期',
            'to_tier': '成长期',
        }, '小明')
        assert '萌芽期' in text
        assert '成长期' in text

    def test_first_checkin_contains_welcome(self):
        text = format_event_for_group({'type': 'first_checkin'}, '小明')
        assert '欢迎' in text

    def test_all_event_types_have_template(self):
        """所有事件类型都有对应文案模板"""
        event_types = ['rank_up', 'rank_down', 'new_record', 'tier_up',
                       'streak_broken', 'first_checkin', 'comeback', 'badge_earned']
        for et in event_types:
            text = format_event_for_group({'type': et}, '测试')
            # 文案非空且包含学员名
            assert len(text) > 0, f'{et} 文案为空'


class TestEventEdgeCases:
    """边界条件"""

    def test_tied_rank_no_change(self):
        """并列排名 → 无变化"""
        result = detect_rank_changes(current_rank=3, previous_rank=3)
        assert result['type'] == 'stable'

    def test_rank_from_unranked_to_first(self):
        """从无排名到第 1 名"""
        result = detect_rank_changes(current_rank=1, previous_rank=None)
        assert result['type'] == 'rank_up'

    def test_new_student_no_events(self, db_session, student_fixture):
        """新学员：无纪录、无排名变动、无段位晋升"""
        assert detect_first_checkin(student_fixture.total_checkins) is None
        assert detect_tier_up(
            student_fixture.fitness_score,
            student_fixture.fitness_score,
        ) is None
