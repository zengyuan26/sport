import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    _db_url = os.environ.get('DATABASE_URL')
    if _db_url:
        # Railway 提供的 PostgreSQL URL 以 postgres:// 开头
        # SQLAlchemy 1.4+ 需要 postgresql://
        if _db_url.startswith('postgres://'):
            _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "fitness.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FITNESS_COACH_PASSWORD = os.environ.get('FITNESS_COACH_PASSWORD', 'coach123')
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:5050')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
