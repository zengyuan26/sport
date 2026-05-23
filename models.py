import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def short_code():
    return uuid.uuid4().hex[:8]


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age_group = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200))
    duration = db.Column(db.Integer, default=60)
    icon = db.Column(db.String(10), default='🏃')
    is_active = db.Column(db.Boolean, default=True)

    checkins = db.relationship('CheckIn', backref='course', lazy='dynamic',
                               cascade='all, delete-orphan')


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    age_group = db.Column(db.String(20), nullable=False)
    access_code = db.Column(db.String(8), unique=True, nullable=False, index=True,
                             default=short_code)
    avatar_emoji = db.Column(db.String(10), default='🧒')
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    join_date = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    checkins = db.relationship('CheckIn', backref='student', lazy='dynamic',
                               cascade='all, delete-orphan',
                               order_by='CheckIn.checkin_time.desc()')
    assessments = db.relationship('Assessment', backref='student', lazy='dynamic',
                                  cascade='all, delete-orphan',
                                  order_by='Assessment.date.desc()')
    badges = db.relationship('StudentBadge', backref='student', lazy='dynamic',
                             cascade='all, delete-orphan',
                             order_by='StudentBadge.awarded_date.desc()')

    @property
    def total_checkins(self):
        return self.checkins.count()

    @property
    def streak_days(self):
        """计算连续出勤天数（按自然日连续）"""
        from sqlalchemy import func, Date
        dates = db.session.query(
            func.date(CheckIn.checkin_time).label('d')
        ).filter(
            CheckIn.student_id == self.id
        ).group_by('d').order_by(db.text('d desc')).all()

        if not dates:
            return 0

        from datetime import date, timedelta
        today = date.today()
        streak = 0
        for (d,) in dates:
            expected = today - timedelta(days=streak)
            if d == expected:
                streak += 1
            elif d < expected:
                break
        return streak


class CheckIn(db.Model):
    __tablename__ = 'checkins'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    checkin_time = db.Column(db.DateTime, default=datetime.utcnow)


class Assessment(db.Model):
    __tablename__ = 'assessments'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    seated_forward_bend = db.Column(db.Float)
    standing_long_jump = db.Column(db.Float)
    shuttle_run = db.Column(db.Float)
    rope_skip = db.Column(db.Integer)
    sit_up = db.Column(db.Integer)
    balance_score = db.Column(db.Float)
    posture_notes = db.Column(db.Text)
    overall_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BadgeTemplate(db.Model):
    __tablename__ = 'badge_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(10), default='🏅')
    trigger_type = db.Column(db.String(30), nullable=False)
    # attendance_count / streak_days / manual / assessment_achievement
    trigger_value = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)

    awards = db.relationship('StudentBadge', backref='template', lazy='dynamic',
                             cascade='all, delete-orphan')


class StudentBadge(db.Model):
    __tablename__ = 'student_badges'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    badge_template_id = db.Column(db.Integer, db.ForeignKey('badge_templates.id'),
                                  nullable=False)
    awarded_date = db.Column(db.DateTime, default=datetime.utcnow)
