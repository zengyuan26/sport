import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(BASE_DIR, "fitness.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FITNESS_COACH_PASSWORD = os.environ.get('FITNESS_COACH_PASSWORD', 'coach123')
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:5050')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
