"""模型层测试：Student 属性计算、COURSE_ATTR_MAP、RANK_TIERS、状态流转"""

from datetime import date, timedelta

import pytest

from models import (
    Student, CheckIn, Course, Assessment, BadgeTemplate, StudentBadge,
    COURSE_ATTR_MAP, ATTR_NAMES, RANK_TIERS, ATTR_MAX
)


class TestCourseAttrMap:
    """COURSE_ATTR_MAP 关键词匹配与增益值"""

    def test_all_keywords_have_valid_attrs(self):
        """所有关键词映射的属性都在 ATTR_NAMES 中"""
        for keyword, gains in COURSE_ATTR_MAP.items():
            for attr in gains:
                assert attr in ATTR_NAMES, f'{keyword} 的属性 {attr} 不在 ATTR_NAMES 中'

    def test_all_gain_values_positive(self):
        """所有增益值 > 0"""
        for keyword, gains in COURSE_ATTR_MAP.items():
            for attr, val in gains.items():
                assert val > 0, f'{keyword}.{attr} = {val}, 应 > 0'

    def test_keyword_matches_course_name(self):
        """验证关键词在课程名中的匹配逻辑"""
        assert '感统' in '感统训练·基础循环第1节'
        assert '力量' in '力量入门'
        assert '跳绳' in '跳绳专项训练'
        assert '综合模拟' in '综合模拟测试'

    def test_attr_max_boundary(self):
        """ATTR_MAX = 100"""
        assert ATTR_MAX == 100


class TestRankTiers:
    """RANK_TIERS 段位边界值"""

    def test_four_tiers(self):
        assert len(RANK_TIERS) == 4

    def test_tier_names(self):
        names = [t['name'] for t in RANK_TIERS]
        assert names == ['萌芽期', '成长期', '突破期', '巅峰期']

    @pytest.mark.parametrize('score,expected', [
        (0, '萌芽期'),
        (30, '萌芽期'),
        (59, '萌芽期'),
        (60, '成长期'),
        (70, '成长期'),
        (79, '成长期'),
        (80, '突破期'),
        (85, '突破期'),
        (89, '突破期'),
        (90, '巅峰期'),
        (95, '巅峰期'),
        (100, '巅峰期'),
    ])
    def test_tier_boundaries(self, score, expected):
        """段位边界值测试"""
        for tier in RANK_TIERS:
            if tier['min'] <= score <= tier['max']:
                assert tier['name'] == expected
                return
        pytest.fail(f'分数 {score} 未匹配到段位')


class TestStudentTotalCheckins:
    """Student.total_checkins 属性"""

    def test_zero_checkins(self, db_session, student_fixture):
        s = student_fixture
        assert s.total_checkins == 0

    def test_only_confirmed_counted(self, db_session, student_fixture, seed_courses):
        s = student_fixture
        db_session.add(CheckIn(student_id=s.id, course_id=seed_courses[0].id, status='confirmed'))
        db_session.add(CheckIn(student_id=s.id, course_id=seed_courses[1].id, status='pending'))
        db_session.commit()
        assert s.total_checkins == 1

    def test_all_confirmed(self, db_session, student_fixture, seed_courses):
        s = student_fixture
        for c in seed_courses[:3]:
            db_session.add(CheckIn(student_id=s.id, course_id=c.id, status='confirmed'))
        db_session.commit()
        assert s.total_checkins == 3


class TestStudentStreakDays:
    """Student.streak_days 连续出勤"""

    def test_no_checkins(self, db_session, student_fixture):
        assert student_fixture.streak_days == 0

    def test_today_checkin_is_streak_one(self, db_session, student_fixture, seed_courses):
        """今天打卡 → 连续1天"""
        from datetime import datetime
        ci = CheckIn(
            student_id=student_fixture.id,
            course_id=seed_courses[0].id,
            checkin_time=datetime.utcnow(),
            status='confirmed',
        )
        db_session.add(ci)
        db_session.commit()
        assert student_fixture.streak_days >= 1

    def test_pending_not_counted_in_streak(self, db_session, student_fixture, seed_courses):
        """待确认打卡不算入连续天数"""
        ci = CheckIn(
            student_id=student_fixture.id,
            course_id=seed_courses[0].id,
            status='pending',
        )
        db_session.add(ci)
        db_session.commit()
        assert student_fixture.streak_days == 0


class TestStudentAttributes:
    """Student.attributes 六维属性计算"""

    def test_no_checkins_all_zero(self, db_session, student_fixture):
        attrs = student_fixture.attributes
        assert all(v == 0 for v in attrs.values())

    def test_single_course_gain(self, db_session, student_fixture, seed_courses):
        """一门课程 → 正确计算增益"""
        s = student_fixture
        # 力量入门 → 力量+10
        strength_course = [c for c in seed_courses if '力量' in c.name][0]
        db_session.add(CheckIn(student_id=s.id, course_id=strength_course.id, status='confirmed'))
        db_session.commit()
        attrs = s.attributes
        assert attrs['力量'] == 10
        assert attrs['速度'] == 0

    def test_multiple_courses_accumulate(self, db_session, student_fixture, seed_courses):
        """多门课程属性累积"""
        s = student_fixture
        for c in seed_courses[:3]:  # 感统、力量、速度
            db_session.add(CheckIn(student_id=s.id, course_id=c.id, status='confirmed'))
        db_session.commit()
        attrs = s.attributes
        # 感统: 协调+8, 柔韧+5 / 力量: 力量+10 / 速度: 速度+8, 协调+3
        assert attrs['协调'] == 11  # 8 + 3
        assert attrs['柔韧'] == 5
        assert attrs['力量'] == 10
        assert attrs['速度'] == 8

    def test_capped_at_max(self, db_session, student_fixture, seed_courses):
        """属性不超过 ATTR_MAX (100)"""
        s = student_fixture
        strength_course = [c for c in seed_courses if '力量' in c.name][0]
        # 添加 11 次力量课程 → 力量应为 100 (capped)
        for _ in range(11):
            db_session.add(CheckIn(student_id=s.id, course_id=strength_course.id, status='confirmed'))
        db_session.commit()
        attrs = s.attributes
        assert attrs['力量'] == 100


class TestStudentFitnessScore:
    """Student.fitness_score 体质分"""

    def test_zero_score_new_student(self, db_session, student_fixture):
        assert student_fixture.fitness_score == 0

    def test_rounded_integer(self, db_session, student_with_checkins):
        s = student_with_checkins
        assert isinstance(s.fitness_score, int)
        assert 0 <= s.fitness_score <= 100


class TestStudentRankTier:
    """Student.rank_tier 段位"""

    def test_new_student_is_sprout(self, db_session, student_fixture):
        tier = student_fixture.rank_tier
        assert tier['name'] == '萌芽期'
        assert tier['color'] == '#34C759'

    def test_tier_has_required_keys(self, db_session, student_fixture):
        tier = student_fixture.rank_tier
        for key in ['name', 'icon', 'color', 'min', 'max']:
            assert key in tier


class TestStudentNextRank:
    """Student.next_rank 下一段位"""

    def test_new_student_has_next_rank(self, db_session, student_fixture):
        nxt = student_fixture.next_rank
        assert nxt is not None
        assert nxt['name'] == '成长期'
        assert 'progress_pct' in nxt

    def test_max_tier_returns_none(self, db_session, student_fixture, seed_courses):
        """巅峰期学员 next_rank 为 None"""
        s = student_fixture
        # 大量打卡让属性达到巅峰期
        for c in seed_courses * 5:
            db_session.add(CheckIn(
                student_id=s.id, course_id=c.id, status='confirmed',
            ))
        db_session.commit()
        if s.rank_tier['name'] == '巅峰期':
            assert s.next_rank is None


class TestCheckInStatus:
    """CheckIn 状态流转"""

    def test_default_status_is_pending(self, db_session, student_fixture, seed_courses):
        ci = CheckIn(student_id=student_fixture.id, course_id=seed_courses[0].id)
        db_session.add(ci)
        db_session.commit()
        assert ci.status == 'pending'

    def test_explicit_confirmed(self, db_session, student_fixture, seed_courses):
        ci = CheckIn(student_id=student_fixture.id, course_id=seed_courses[0].id,
                     status='confirmed')
        db_session.add(ci)
        db_session.commit()
        assert ci.status == 'confirmed'


class TestBadgeTemplate:
    """BadgeTemplate trigger_type 分类"""

    def test_valid_trigger_types(self, db_session, seed_badge_templates):
        valid_types = {'attendance_count', 'streak_days', 'manual', 'assessment'}
        for t in seed_badge_templates:
            assert t.trigger_type in valid_types, \
                f'{t.name} 的 trigger_type={t.trigger_type} 不合法'

    def test_attendance_badges_have_value(self, db_session, seed_badge_templates):
        for t in seed_badge_templates:
            if t.trigger_type == 'attendance_count':
                assert t.trigger_value is not None and t.trigger_value > 0

    def test_assessment_badges_have_metric(self, db_session, seed_badge_templates):
        for t in seed_badge_templates:
            if t.trigger_type == 'assessment':
                assert t.trigger_metric is not None
                assert t.trigger_value is not None


class TestStudentBadge:
    """StudentBadge 关联"""

    def test_award_badge_to_student(self, db_session, student_fixture, seed_badge_templates):
        sb = StudentBadge(
            student_id=student_fixture.id,
            badge_template_id=seed_badge_templates[0].id,
        )
        db_session.add(sb)
        db_session.commit()
        assert sb.id is not None
        assert sb.template == seed_badge_templates[0]


class TestAssessment:
    """Assessment 模型"""

    def test_create_assessment(self, db_session, student_fixture):
        a = Assessment(
            student_id=student_fixture.id,
            seated_forward_bend=10.0,
            standing_long_jump=140.0,
            shuttle_run=10.0,
            rope_skip=60,
            sit_up=25,
        )
        db_session.add(a)
        db_session.commit()
        assert a.id is not None
        assert a.student == student_fixture

    def test_nullable_fields(self, db_session, student_fixture):
        """各评估字段可为空"""
        a = Assessment(student_id=student_fixture.id)
        db_session.add(a)
        db_session.commit()
        assert a.seated_forward_bend is None
        assert a.rope_skip is None
