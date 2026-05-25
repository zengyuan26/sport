import uuid
import pickle
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def short_code():
    return uuid.uuid4().hex[:8]


def encode_face(np_array):
    """将 numpy 人脸编码转为二进制存储"""
    return pickle.dumps(np_array) if np_array is not None else None


def decode_face(blob):
    """从二进制还原 numpy 人脸编码"""
    return pickle.loads(blob) if blob else None


# ── 课程 → 属性成长映射 ────────────────────────────
# 每完成一次课程，对应属性获得成长值
COURSE_ATTR_MAP = {
    '感统': {'协调': 8, '柔韧': 5},
    '力量': {'力量': 10},
    '速度': {'速度': 8, '协调': 3},
    '协调': {'协调': 8, '爆发': 5},
    '柔韧': {'柔韧': 10},
    '爆发': {'爆发': 10, '力量': 5},
    '耐力': {'耐力': 10},
    '跳绳': {'协调': 8, '耐力': 5},
    '跑步': {'速度': 8, '耐力': 5},
    '跳远': {'爆发': 8, '力量': 5},
    '仰卧起坐': {'力量': 5, '耐力': 5},
    '综合模拟': {'力量': 4, '速度': 4, '耐力': 4, '柔韧': 3, '协调': 3, '爆发': 3},
}

ATTR_NAMES = ['力量', '速度', '耐力', '柔韧', '协调', '爆发']
ATTR_ICONS = {'力量': '💪', '速度': '⚡', '耐力': '🫁', '柔韧': '🤸', '协调': '🎯', '爆发': '🚀'}
ATTR_MAX = 100

RANK_TIERS = [
    {'name': '萌芽期', 'icon': '🌱', 'color': '#34C759', 'min': 0, 'max': 59},
    {'name': '成长期', 'icon': '🌿', 'color': '#007AFF', 'min': 60, 'max': 79},
    {'name': '突破期', 'icon': '🔥', 'color': '#FF9500', 'min': 80, 'max': 89},
    {'name': '巅峰期', 'icon': '👑', 'color': '#FF3B30', 'min': 90, 'max': 100},
]


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
    face_encoding = db.Column(db.LargeBinary)
    face_photo_path = db.Column(db.String(200))  # 人脸照片路径，用作头像
    gender = db.Column(db.String(4))         # 男/女
    height_cm = db.Column(db.Float)          # 身高 cm
    weight_kg = db.Column(db.Float)          # 体重 kg
    goal = db.Column(db.String(100))         # 训练目标 多选逗号分隔: zhongkao,fitness,posture,weight_loss,general
    weekly_sessions = db.Column(db.Integer)  # 每周可上课次数
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
        return self.checkins.filter(CheckIn.status == 'confirmed').count()

    @property
    def pending_checkins(self):
        return self.checkins.filter(CheckIn.status == 'pending').count()

    @property
    def streak_days(self):
        """计算连续出勤天数（仅已确认的打卡）"""
        from sqlalchemy import func, Date
        dates = db.session.query(
            func.date(CheckIn.checkin_time).label('d')
        ).filter(
            CheckIn.student_id == self.id,
            CheckIn.status == 'confirmed'
        ).group_by('d').order_by(db.text('d desc')).all()

        if not dates:
            return 0

        from datetime import date as date_type, timedelta
        today = date_type.today()
        streak = 0
        for (d,) in dates:
            if isinstance(d, str):
                d = date_type.fromisoformat(d)
            expected = today - timedelta(days=streak)
            if d == expected:
                streak += 1
            elif d < expected:
                break
        return streak

    @property
    def attributes(self):
        """根据已确认打卡的课程计算六维属性值（每属性上限 100）"""
        attrs = {a: 0 for a in ATTR_NAMES}
        confirmed = self.checkins.filter(CheckIn.status == 'confirmed').all()
        for ci in confirmed:
            course_name = ci.course.name
            for keyword, gains in COURSE_ATTR_MAP.items():
                if keyword in course_name:
                    for attr, val in gains.items():
                        attrs[attr] = min(attrs[attr] + val, ATTR_MAX)
        return attrs

    @property
    def fitness_score(self):
        """体质指数 = 六维属性平均值"""
        attrs = self.attributes
        return int(sum(attrs.values()) / len(attrs))

    @property
    def rank_tier(self):
        """当前段位"""
        score = self.fitness_score
        for tier in RANK_TIERS:
            if tier['min'] <= score <= tier['max']:
                return tier
        return RANK_TIERS[0]

    @property
    def next_rank(self):
        """下一段位信息 {name, icon, color, progress_pct}"""
        tier = self.rank_tier
        idx = RANK_TIERS.index(tier)
        if idx >= len(RANK_TIERS) - 1:
            return None  # 已满级
        nxt = RANK_TIERS[idx + 1]
        score = self.fitness_score
        range_start = tier['max'] if tier['min'] > 0 else 0
        range_total = nxt['min'] - range_start
        progress = score - range_start
        pct = min(100, int(progress / range_total * 100)) if range_total > 0 else 100
        return {**nxt, 'progress_pct': pct, 'current': score, 'target': nxt['min']}


class CheckIn(db.Model):
    __tablename__ = 'checkins'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    checkin_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(10), default='pending')
    # pending: 家长扫码提交，等待教练确认
    # confirmed: 教练已确认 / 教练手动打卡直接确认


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
    # attendance_count / streak_days / manual / assessment
    trigger_value = db.Column(db.Integer)
    trigger_metric = db.Column(db.String(30))
    # 仅 assessment 类型使用: rope_skip / sit_up / seated_forward_bend / standing_long_jump / shuttle_run
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


class Photo(db.Model):
    __tablename__ = 'photos'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    file_path = db.Column(db.String(200), nullable=False)
    thumbnail_path = db.Column(db.String(200))
    is_tagged = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.Float)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('photos', lazy='dynamic',
                                                              order_by='Photo.upload_date.desc()'))


class Booking(db.Model):
    """课程预约"""
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_date = db.Column(db.Date, nullable=False)
    course_session = db.Column(db.String(20), nullable=False)
    # friday_evening / saturday_afternoon / saturday_evening / sunday_afternoon / sunday_evening
    status = db.Column(db.String(10), default='booked')
    # booked / cancelled / attended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('bookings', lazy='dynamic',
                                                              order_by='Booking.course_date.desc()'))


class ContentLog(db.Model):
    """群内容发送日志"""
    __tablename__ = 'content_logs'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(30), nullable=False)
    # weekly_report / progress_star / matchup / booking_reminder / session_report / coach_knowledge
    title = db.Column(db.String(200))
    image_path = db.Column(db.String(200))
    text_content = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setting(db.Model):
    """系统设置 key-value 存储"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False, default='')
