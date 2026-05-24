import os
import sys
import tempfile
import uuid

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ⚠️ 必须在导入 app/models 之前设置 DATABASE_URL，
# 因为 Config 类在 import 时读取环境变量
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f'fitness_test_{uuid.uuid4().hex[:8]}.db')
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'
os.environ['FITNESS_COACH_PASSWORD'] = 'test123'

import pytest

from app import create_app
from models import (
    db, Course, Student, CheckIn, Assessment,
    BadgeTemplate, StudentBadge, Photo,
)


@pytest.fixture(scope='session')
def _db_path():
    """Return the test database path (session-scoped, shared across tests)."""
    yield TEST_DB_PATH
    # Cleanup at end of session
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)


def _reset_db():
    """Drop all data between tests without dropping tables."""
    meta = db.metadata
    for table in reversed(meta.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture(scope='function')
def app():
    """Create Flask app with test database, tables recreated once."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'localhost'

    with app.app_context():
        db.create_all()
        # Seed courses + badges if empty
        from models import Course
        if Course.query.count() == 0:
            from seed import COURSES, BADGES
            from models import BadgeTemplate
            for c in COURSES:
                db.session.add(Course(**c))
            for b in BADGES:
                db.session.add(BadgeTemplate(**b))
            db.session.commit()

    yield app

    # Clean data between tests (keep tables)
    with app.app_context():
        _reset_db()


@pytest.fixture(scope='function')
def client(app):
    """Test client with app context pushed."""
    with app.app_context():
        yield app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Database session for direct model testing."""
    with app.app_context():
        yield db.session


@pytest.fixture(scope='function')
def seed_courses(db_session):
    """Insert seed courses for testing."""
    # Clear existing auto-seeded courses to control test data
    from models import CheckIn
    CheckIn.query.delete()
    from models import Course
    Course.query.delete()
    db_session.commit()

    courses = [
        Course(name='感统训练·基础循环第1节', age_group='3-6岁', duration=60, icon='🐻'),
        Course(name='力量入门', age_group='6-9岁', duration=60, icon='💪'),
        Course(name='速度敏捷训练', age_group='6-9岁', duration=60, icon='⚡'),
        Course(name='跳绳专项训练', age_group='9-12岁', duration=60, icon='🪢'),
        Course(name='综合模拟测试', age_group='11-15岁', duration=90, icon='🏋️'),
        Course(name='协调跳跃', age_group='6-9岁', duration=60, icon='🦘'),
        Course(name='爆发力训练', age_group='9-12岁', duration=60, icon='🚀'),
        Course(name='耐力心肺', age_group='9-12岁', duration=60, icon='🫁'),
        Course(name='柔韧平衡', age_group='6-9岁', duration=60, icon='🤸'),
        Course(name='跑步专项训练', age_group='11-15岁', duration=60, icon='🏃'),
        Course(name='仰卧起坐训练', age_group='11-15岁', duration=60, icon='🦵'),
        Course(name='跳远专项训练', age_group='11-15岁', duration=60, icon='📏'),
    ]
    db_session.add_all(courses)
    db_session.commit()
    return courses


@pytest.fixture(scope='function')
def seed_badge_templates(db_session):
    """Insert seed badge templates for testing."""
    from models import StudentBadge, BadgeTemplate
    StudentBadge.query.delete()
    BadgeTemplate.query.delete()
    db_session.commit()

    templates = [
        BadgeTemplate(name='初次打卡', icon='🎉', trigger_type='attendance_count', trigger_value=1),
        BadgeTemplate(name='坚持10次', icon='🌟', trigger_type='attendance_count', trigger_value=10),
        BadgeTemplate(name='坚持30次', icon='💫', trigger_type='attendance_count', trigger_value=30),
        BadgeTemplate(name='一周全勤', icon='🔥', trigger_type='streak_days', trigger_value=7),
        BadgeTemplate(name='月度全勤王', icon='👑', trigger_type='streak_days', trigger_value=30),
        BadgeTemplate(name='跳绳破百', icon='🪢', trigger_type='assessment', trigger_value=100,
                      trigger_metric='rope_skip'),
        BadgeTemplate(name='跳远突破', icon='📏', trigger_type='assessment', trigger_value=180,
                      trigger_metric='standing_long_jump'),
        BadgeTemplate(name='仰卧起坐达人', icon='💪', trigger_type='manual', trigger_value=None),
        BadgeTemplate(name='全项目A级', icon='🏆', trigger_type='manual', trigger_value=None),
    ]
    db_session.add_all(templates)
    db_session.commit()
    return templates


@pytest.fixture(scope='function')
def student_fixture(db_session):
    """Create a basic student for testing."""
    s = Student(
        name='测试学员',
        age_group='6-9岁',
        access_code=f'test{uuid.uuid4().hex[:6]}',
        avatar_emoji='💪',
        gender='男',
        height_cm=130.0,
        weight_kg=28.0,
        goal='fitness,general',
        weekly_sessions=2,
        is_active=True,
    )
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture(scope='function')
def student_with_checkins(db_session, seed_courses, student_fixture):
    """Student with confirmed checkins to compute attributes."""
    s = student_fixture
    for i, course in enumerate(seed_courses[:5]):
        ci = CheckIn(student_id=s.id, course_id=course.id, status='confirmed')
        db_session.add(ci)
    db_session.commit()
    return s


@pytest.fixture(scope='function')
def multiple_students(db_session):
    """Create 5 students with varying data for ranking tests."""
    students = []
    for i in range(1, 6):
        s = Student(
            name=f'学员{i}',
            age_group='6-9岁',
            access_code=f'code{i:04d}_{uuid.uuid4().hex[:4]}',
            avatar_emoji=['💪', '⚡', '🫁', '🤸', '🎯'][i-1],
            gender='男' if i % 2 == 1 else '女',
            weekly_sessions=2,
            is_active=True,
        )
        db_session.add(s)
        students.append(s)
    db_session.commit()
    return students


@pytest.fixture(scope='function')
def assessment_fixture(db_session, student_fixture):
    """Create an assessment for the test student."""
    a = Assessment(
        student_id=student_fixture.id,
        seated_forward_bend=12.5,
        standing_long_jump=150.0,
        shuttle_run=9.2,
        rope_skip=80,
        sit_up=35,
        balance_score=22.0,
        posture_notes='轻微驼背',
        overall_notes='进步明显',
    )
    db_session.add(a)
    db_session.commit()
    return a


@pytest.fixture(scope='function')
def coach_login(client):
    """Login as coach and return client with session."""
    client.post('/login', data={'password': 'test123'})
    return client
