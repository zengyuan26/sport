"""课程预约系统测试"""

import pytest
from datetime import date, timedelta


# ── 预约系统接口定义（正式实现在 models.py + routes.py）──

VALID_SESSIONS = [
    'friday_evening',
    'saturday_afternoon',
    'saturday_evening',
    'sunday_afternoon',
    'sunday_evening',
]

BOOKING_STATUSES = ['booked', 'cancelled', 'attended']


def validate_booking(student_id, course_date, session, existing_bookings):
    """
    验证预约请求。
    返回: { ok: bool, error?: str }
    """
    if session not in VALID_SESSIONS:
        return {'ok': False, 'error': '无效的时段'}

    # 检查重复预约
    for b in existing_bookings:
        if (b['student_id'] == student_id
                and b['course_date'] == str(course_date)
                and b['session'] == session
                and b['status'] == 'booked'):
            return {'ok': False, 'error': '该时段已预约'}

    return {'ok': True}


def validate_cancel(booking, cancel_deadline_hours=4):
    """
    验证取消预约。
    """
    if booking['status'] != 'booked':
        return {'ok': False, 'error': '只能取消已预约的课程'}

    # 检查取消截止时间
    booking_date = date.fromisoformat(booking['course_date'])
    if booking_date <= date.today():
        return {'ok': False, 'error': '已过取消截止时间'}

    return {'ok': True}


def get_booking_summary(bookings, sessions_config):
    """
    生成预约汇总：每个时段已预约数和剩余名额。
    """
    summary = {}
    for session in sessions_config:
        session_key = session['key']
        booked_count = len([
            b for b in bookings
            if b['session'] == session_key and b['status'] == 'booked'
        ])
        summary[session_key] = {
            'course_name': session['name'],
            'max_capacity': session['max_capacity'],
            'booked': booked_count,
            'remaining': session['max_capacity'] - booked_count,
        }
    return summary


def get_student_bookings(bookings, student_id):
    """获取某学员的所有预约"""
    return [b for b in bookings if b['student_id'] == student_id]


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

class TestBookingValidation:
    """预约验证"""

    def test_valid_booking(self):
        result = validate_booking(
            student_id=1,
            course_date=date.today() + timedelta(days=3),
            session='saturday_afternoon',
            existing_bookings=[],
        )
        assert result['ok'] is True

    def test_invalid_session(self):
        result = validate_booking(
            student_id=1,
            course_date=date.today(),
            session='monday_morning',  # 不存在的时段
            existing_bookings=[],
        )
        assert result['ok'] is False
        assert '无效' in result['error']

    def test_duplicate_booking(self):
        existing = [
            {
                'student_id': 1,
                'course_date': '2026-05-30',
                'session': 'saturday_afternoon',
                'status': 'booked',
            }
        ]
        result = validate_booking(
            student_id=1,
            course_date=date(2026, 5, 30),
            session='saturday_afternoon',
            existing_bookings=existing,
        )
        assert result['ok'] is False
        assert '已预约' in result['error']

    def test_different_session_same_day_ok(self):
        """同一天不同时段可以预约"""
        existing = [
            {
                'student_id': 1,
                'course_date': '2026-05-30',
                'session': 'saturday_afternoon',
                'status': 'booked',
            }
        ]
        result = validate_booking(
            student_id=1,
            course_date=date(2026, 5, 30),
            session='saturday_evening',
            existing_bookings=existing,
        )
        assert result['ok'] is True

    def test_cancelled_booking_doesnt_block(self):
        """已取消的预约不阻止重新预约"""
        existing = [
            {
                'student_id': 1,
                'course_date': '2026-05-30',
                'session': 'saturday_afternoon',
                'status': 'cancelled',
            }
        ]
        result = validate_booking(
            student_id=1,
            course_date=date(2026, 5, 30),
            session='saturday_afternoon',
            existing_bookings=existing,
        )
        assert result['ok'] is True

    def test_different_student_same_session_ok(self):
        """不同学员同一时段不冲突"""
        existing = [
            {
                'student_id': 1,
                'course_date': '2026-05-30',
                'session': 'saturday_afternoon',
                'status': 'booked',
            }
        ]
        result = validate_booking(
            student_id=2,
            course_date=date(2026, 5, 30),
            session='saturday_afternoon',
            existing_bookings=existing,
        )
        assert result['ok'] is True


class TestBookingCancel:
    """取消预约"""

    def test_cancel_booked_booking(self):
        booking = {
            'id': 1,
            'student_id': 1,
            'course_date': str(date.today() + timedelta(days=5)),
            'session': 'saturday_afternoon',
            'status': 'booked',
        }
        result = validate_cancel(booking)
        assert result['ok'] is True

    def test_cancel_already_cancelled(self):
        booking = {
            'id': 1,
            'student_id': 1,
            'course_date': str(date.today() + timedelta(days=5)),
            'session': 'saturday_afternoon',
            'status': 'cancelled',
        }
        result = validate_cancel(booking)
        assert result['ok'] is False

    def test_cancel_attended_booking(self):
        """已上课的不能取消"""
        booking = {
            'id': 1,
            'student_id': 1,
            'course_date': str(date.today() - timedelta(days=1)),
            'session': 'saturday_afternoon',
            'status': 'attended',
        }
        result = validate_cancel(booking)
        assert result['ok'] is False

    def test_cancel_past_date(self):
        booking = {
            'id': 1,
            'student_id': 1,
            'course_date': str(date.today()),
            'session': 'saturday_afternoon',
            'status': 'booked',
        }
        result = validate_cancel(booking)
        assert result['ok'] is False


class TestBookingSummary:
    """预约汇总"""

    def test_summary_calculates_correctly(self):
        sessions_config = [
            {'key': 'saturday_afternoon', 'name': '力量入门', 'max_capacity': 20},
            {'key': 'saturday_evening', 'name': '速度敏捷', 'max_capacity': 20},
            {'key': 'sunday_afternoon', 'name': '协调跳跃', 'max_capacity': 15},
        ]
        bookings = [
            {'student_id': 1, 'session': 'saturday_afternoon', 'status': 'booked'},
            {'student_id': 2, 'session': 'saturday_afternoon', 'status': 'booked'},
            {'student_id': 3, 'session': 'saturday_evening', 'status': 'booked'},
            {'student_id': 1, 'session': 'saturday_afternoon', 'status': 'cancelled'},
        ]
        summary = get_booking_summary(bookings, sessions_config)

        assert summary['saturday_afternoon']['booked'] == 2
        assert summary['saturday_afternoon']['remaining'] == 18
        assert summary['saturday_evening']['booked'] == 1
        assert summary['sunday_afternoon']['booked'] == 0
        assert summary['sunday_afternoon']['remaining'] == 15

    def test_full_session(self):
        sessions_config = [
            {'key': 'saturday_afternoon', 'name': '力量入门', 'max_capacity': 2},
        ]
        bookings = [
            {'student_id': 1, 'session': 'saturday_afternoon', 'status': 'booked'},
            {'student_id': 2, 'session': 'saturday_afternoon', 'status': 'booked'},
        ]
        summary = get_booking_summary(bookings, sessions_config)
        assert summary['saturday_afternoon']['remaining'] == 0

    def test_empty_bookings(self):
        sessions_config = [
            {'key': 'friday_evening', 'name': '感统训练', 'max_capacity': 20},
        ]
        summary = get_booking_summary([], sessions_config)
        assert summary['friday_evening']['booked'] == 0
        assert summary['friday_evening']['remaining'] == 20


class TestStudentBookings:
    """学员预约查询"""

    def test_get_student_bookings(self):
        bookings = [
            {'student_id': 1, 'session': 'saturday_afternoon', 'course_date': '2026-05-30'},
            {'student_id': 1, 'session': 'sunday_afternoon', 'course_date': '2026-05-31'},
            {'student_id': 2, 'session': 'saturday_afternoon', 'course_date': '2026-05-30'},
        ]
        result = get_student_bookings(bookings, student_id=1)
        assert len(result) == 2

    def test_no_bookings(self):
        bookings = [
            {'student_id': 2, 'session': 'saturday_afternoon', 'course_date': '2026-05-30'},
        ]
        result = get_student_bookings(bookings, student_id=1)
        assert result == []


class TestValidSessions:
    """时段定义"""

    def test_all_sessions_are_weekend(self):
        """所有时段都在周五到周日"""
        for s in VALID_SESSIONS:
            assert any(day in s for day in ['friday', 'saturday', 'sunday']), \
                f'{s} 不在周末范围'

    def test_booking_statuses(self):
        assert 'booked' in BOOKING_STATUSES
        assert 'cancelled' in BOOKING_STATUSES
        assert 'attended' in BOOKING_STATUSES
