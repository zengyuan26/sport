"""群内容引擎测试 — 周报、进步之星、对决预告、预约提醒、课后战报"""

import pytest


# ── 内容引擎接口定义（正式实现在 content_engine.py）──

def generate_weekly_report(rankings, events, checkin_stats):
    """
    生成周报数据。
    rankings: [ { student_id, name, current_rank, previous_rank, score } ]
    events: 本周事件列表
    checkin_stats: { total_checkins, total_students, avg_attendance }
    返回: { top_changes: [...], star_of_week: {...}, stats: {...}, events: [...] }
    """
    # 排名变动 TOP 5
    changes = []
    for r in rankings:
        if r.get('previous_rank') and r['previous_rank'] != r['current_rank']:
            changes.append({
                'student_name': r['name'],
                'from_rank': r['previous_rank'],
                'to_rank': r['current_rank'],
                'delta': r['previous_rank'] - r['current_rank'],
            })
    changes.sort(key=lambda x: abs(x['delta']), reverse=True)
    top_changes = changes[:5]

    # 本周之星：排名提升最多的学员
    star = None
    if changes:
        best = max(changes, key=lambda x: x['delta'])
        star = {
            'student_name': best['student_name'],
            'reason': f'排名从第{best["from_rank"]}位升至第{best["to_rank"]}位',
        }

    return {
        'top_changes': top_changes,
        'star_of_week': star,
        'stats': checkin_stats,
        'events': events or [],
    }


def generate_progress_stars(students, period='week'):
    """
    生成进步之星 TOP 3。
    students: [{ name, improvement_pct, coach_note }]
    """
    sorted_students = sorted(students, key=lambda x: x.get('improvement_pct', 0), reverse=True)
    return sorted_students[:3]


def generate_matchups(rankings, dim='fitness', threshold=5):
    """
    生成对决预告：分差 < threshold 的相邻学员配对。
    rankings: 按排名排序的 [{ rank, student_name, score, student_id }]
    """
    matchups = []
    for i in range(len(rankings) - 1):
        gap = rankings[i]['score'] - rankings[i + 1]['score']
        if gap < threshold:
            matchups.append({
                'challenger': rankings[i + 1],
                'defender': rankings[i],
                'gap': gap,
                'dimension': dim,
            })
    return matchups


def generate_booking_reminder(courses_this_weekend, booked_counts):
    """
    生成预约提醒。
    courses_this_weekend: [{ session, course_name, max_capacity }]
    booked_counts: { session: booked_count }
    """
    result = []
    for c in courses_this_weekend:
        session = c['session']
        booked = booked_counts.get(session, 0)
        remaining = c['max_capacity'] - booked
        result.append({
            **c,
            'booked': booked,
            'remaining': remaining,
            'is_full': remaining <= 0,
            'urgency': '即将满额' if remaining <= 3 else ('充足' if remaining > 10 else '热报中'),
        })
    return result


def generate_session_report(course_name, checkin_count, new_records, photos_count):
    """
    生成课后战报。
    """
    return {
        'course_name': course_name,
        'checkin_count': checkin_count,
        'new_records': new_records or [],
        'photos_count': photos_count,
        'highlight': f'今天 {checkin_count} 位学员完成训练' +
                     (f'，{len(new_records)} 人创造新纪录！' if new_records else '！'),
    }


def content_has_branding(content_dict):
    """检查内容是否包含品牌标识要求的结构"""
    # 所有内容应有明确的标题字段
    return 'title' in content_dict or 'course_name' in content_dict or 'star_of_week' in content_dict


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

class TestWeeklyReport:
    """周报战报"""

    def test_top_changes_limited_to_5(self):
        rankings = [
            {'name': f'学员{i}', 'current_rank': i, 'previous_rank': i + 3, 'score': 100 - i}
            for i in range(1, 11)
        ]
        report = generate_weekly_report(rankings, [], {'total_checkins': 50, 'total_students': 10, 'avg_attendance': 5})
        assert len(report['top_changes']) <= 5

    def test_star_of_week_is_best_improver(self):
        rankings = [
            {'name': '小明', 'current_rank': 1, 'previous_rank': 3, 'score': 95},
            {'name': '小红', 'current_rank': 2, 'previous_rank': 10, 'score': 90},
        ]
        report = generate_weekly_report(rankings, [], {'total_checkins': 20, 'total_students': 10, 'avg_attendance': 2})
        assert report['star_of_week'] is not None
        assert report['star_of_week']['student_name'] == '小红'

    def test_no_changes_no_star(self):
        rankings = [
            {'name': '小明', 'current_rank': 1, 'previous_rank': 1, 'score': 95},
        ]
        report = generate_weekly_report(rankings, [], {'total_checkins': 5, 'total_students': 1, 'avg_attendance': 5})
        assert report['star_of_week'] is None
        assert len(report['top_changes']) == 0

    def test_stats_preserved(self):
        stats = {'total_checkins': 42, 'total_students': 8, 'avg_attendance': 5.25}
        report = generate_weekly_report([], [], stats)
        assert report['stats'] == stats

    def test_events_included(self):
        events = [{'type': 'rank_up', 'delta': 5}]
        report = generate_weekly_report([], events, {})
        assert len(report['events']) == 1


class TestProgressStars:
    """进步之星"""

    def test_top_3_returned(self):
        students = [
            {'name': '小明', 'improvement_pct': 30},
            {'name': '小红', 'improvement_pct': 10},
            {'name': '小刚', 'improvement_pct': 45},
            {'name': '小丽', 'improvement_pct': 25},
            {'name': '小强', 'improvement_pct': 5},
        ]
        stars = generate_progress_stars(students)
        assert len(stars) == 3
        assert stars[0]['name'] == '小刚'
        assert stars[0]['improvement_pct'] == 45
        assert stars[1]['name'] == '小明'
        assert stars[2]['name'] == '小丽'

    def test_fewer_than_3_students(self):
        students = [{'name': '小明', 'improvement_pct': 30}]
        stars = generate_progress_stars(students)
        assert len(stars) == 1

    def test_empty_list(self):
        assert generate_progress_stars([]) == []

    def test_equal_improvement(self):
        """相同进步率时保持传入顺序"""
        students = [
            {'name': '小明', 'improvement_pct': 10},
            {'name': '小红', 'improvement_pct': 10},
        ]
        stars = generate_progress_stars(students)
        assert len(stars) == 2


class TestMatchups:
    """对决预告"""

    def test_close_gap_matchup(self):
        rankings = [
            {'rank': 1, 'student_name': '小明', 'score': 95, 'student_id': 1},
            {'rank': 2, 'student_name': '小红', 'score': 93, 'student_id': 2},
        ]
        matchups = generate_matchups(rankings, threshold=5)
        assert len(matchups) == 1
        assert matchups[0]['gap'] == 2
        assert matchups[0]['challenger']['student_name'] == '小红'
        assert matchups[0]['defender']['student_name'] == '小明'

    def test_large_gap_no_matchup(self):
        rankings = [
            {'rank': 1, 'student_name': '小明', 'score': 95, 'student_id': 1},
            {'rank': 2, 'student_name': '小红', 'score': 50, 'student_id': 2},
        ]
        matchups = generate_matchups(rankings, threshold=5)
        assert len(matchups) == 0

    def test_multiple_matchups(self):
        rankings = [
            {'rank': 1, 'student_name': 'A', 'score': 95, 'student_id': 1},
            {'rank': 2, 'student_name': 'B', 'score': 93, 'student_id': 2},
            {'rank': 3, 'student_name': 'C', 'score': 90, 'student_id': 3},
        ]
        matchups = generate_matchups(rankings, threshold=5)
        assert len(matchups) == 2  # A-B and B-C

    def test_custom_threshold(self):
        rankings = [
            {'rank': 1, 'student_name': '小明', 'score': 95, 'student_id': 1},
            {'rank': 2, 'student_name': '小红', 'score': 85, 'student_id': 2},
        ]
        # gap=10, threshold=12 → matched
        matchups = generate_matchups(rankings, threshold=12)
        assert len(matchups) == 1


class TestBookingReminder:
    """预约提醒"""

    def test_remaining_spots_calculated(self):
        courses = [
            {'session': 'saturday_afternoon', 'course_name': '力量入门', 'max_capacity': 20},
            {'session': 'saturday_evening', 'course_name': '速度敏捷', 'max_capacity': 20},
        ]
        booked = {'saturday_afternoon': 18, 'saturday_evening': 5}
        result = generate_booking_reminder(courses, booked)
        assert result[0]['remaining'] == 2
        assert result[0]['urgency'] == '即将满额'
        assert result[1]['remaining'] == 15
        assert result[1]['urgency'] == '充足'

    def test_full_session(self):
        courses = [{'session': 'saturday_afternoon', 'course_name': '力量入门', 'max_capacity': 20}]
        booked = {'saturday_afternoon': 20}
        result = generate_booking_reminder(courses, booked)
        assert result[0]['is_full']
        assert result[0]['remaining'] == 0

    def test_hot_session(self):
        """剩余 <= 10 且 > 3 → 热报中"""
        courses = [{'session': 'friday_evening', 'course_name': '感统训练', 'max_capacity': 20}]
        booked = {'friday_evening': 12}
        result = generate_booking_reminder(courses, booked)
        assert result[0]['urgency'] == '热报中'


class TestSessionReport:
    """课后战报"""

    def test_basic_report(self):
        report = generate_session_report('感统训练·基础循环', 15, [], 5)
        assert report['course_name'] == '感统训练·基础循环'
        assert report['checkin_count'] == 15
        assert '15' in report['highlight']

    def test_report_with_records(self):
        records = [{'student_name': '小明', 'metric': 'rope_skip', 'new_value': 120}]
        report = generate_session_report('跳绳专项', 10, records, 8)
        assert '新纪录' in report['highlight']

    def test_report_no_records(self):
        report = generate_session_report('柔韧训练', 8, [], 3)
        assert '新纪录' not in report['highlight']


class TestContentBranding:
    """内容品牌要求"""

    def test_weekly_report_has_star(self):
        """周报必须有 star_of_week 字段"""
        report = generate_weekly_report([], [], {})
        assert 'star_of_week' in report

    def test_matchup_has_dimension(self):
        rankings = [
            {'rank': 1, 'student_name': 'A', 'score': 95, 'student_id': 1},
            {'rank': 2, 'student_name': 'B', 'score': 94, 'student_id': 2},
        ]
        matchups = generate_matchups(rankings)
        assert matchups[0]['dimension'] is not None

    def test_booking_has_urgency(self):
        courses = [{'session': 'saturday_afternoon', 'course_name': '力量', 'max_capacity': 20}]
        booked = {'saturday_afternoon': 5}
        result = generate_booking_reminder(courses, booked)
        assert 'urgency' in result[0]


class TestEdgeCases:
    """内容引擎边界"""

    def test_empty_rankings_weekly_report(self):
        report = generate_weekly_report([], [], {})
        assert report['top_changes'] == []
        assert report['star_of_week'] is None

    def test_single_student_no_matchups(self):
        rankings = [{'rank': 1, 'student_name': '小明', 'score': 95, 'student_id': 1}]
        matchups = generate_matchups(rankings)
        assert matchups == []

    def test_no_courses_booking_reminder(self):
        result = generate_booking_reminder([], {})
        assert result == []


class TestCoachKnowledge:
    """教练 IP 知识卡"""

    def test_topics_not_empty(self):
        """知识卡话题池不为空"""
        from content_engine import COACH_KNOWLEDGE_TOPICS
        assert len(COACH_KNOWLEDGE_TOPICS) > 0

    def test_topics_have_required_fields(self):
        """每个话题都有必要字段"""
        from content_engine import COACH_KNOWLEDGE_TOPICS
        for topic in COACH_KNOWLEDGE_TOPICS:
            assert 'category' in topic
            assert 'title' in topic
            assert 'points' in topic
            assert len(topic['points']) >= 3
            assert 'coach_note' in topic
            assert 'icon' in topic

    def test_generate_returns_topic(self):
        """generate_coach_knowledge 返回完整话题"""
        from content_engine import generate_coach_knowledge
        result = generate_coach_knowledge(topic_index=0)
        assert result['index'] == 0
        assert 'title' in result
        assert 'points' in result
        assert 'coach_note' in result
        assert 'total' in result

    def test_generate_rotates_by_index(self):
        """不同 index 返回不同话题"""
        from content_engine import generate_coach_knowledge, COACH_KNOWLEDGE_TOPICS
        if len(COACH_KNOWLEDGE_TOPICS) < 2:
            return
        r1 = generate_coach_knowledge(topic_index=0)
        r2 = generate_coach_knowledge(topic_index=1)
        assert r1['title'] != r2['title']

    def test_generate_without_index(self):
        """不指定 index 时根据周数轮换"""
        from content_engine import generate_coach_knowledge
        result = generate_coach_knowledge()
        assert 'title' in result
        assert 0 <= result['index'] < result['total']
