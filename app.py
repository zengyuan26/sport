import os
import logging
from flask import Flask
from config import Config
from models import db


def create_app():
    from datetime import timedelta
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    db.init_app(app)

    with app.app_context():
        from routes import fitness_bp
        app.register_blueprint(fitness_bp)

        db.create_all()

        # 数据库迁移：为已有 students 表添加新列
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'students' in inspector.get_table_names():
            existing_cols = {c['name'] for c in inspector.get_columns('students')}
            new_cols = {
                'gender': 'VARCHAR(4)',
                'height_cm': 'FLOAT',
                'weight_kg': 'FLOAT',
                'goal': 'VARCHAR(30)',
                'weekly_sessions': 'INTEGER'
            }
            for col_name, col_type in new_cols.items():
                if col_name not in existing_cols:
                    db.session.execute(db.text(f'ALTER TABLE students ADD COLUMN {col_name} {col_type}'))
                    logging.info(f'Migrated: added students.{col_name}')
            db.session.commit()

        # 首次启动自动初始化预置数据
        from models import Course
        if Course.query.count() == 0:
            from seed import seed, COURSES, BADGES
            from models import BadgeTemplate
            for c in COURSES:
                db.session.add(Course(**c))
            for b in BADGES:
                db.session.add(BadgeTemplate(**b))
            db.session.commit()

        # 确保上传目录
        for d in ['static/uploads/qrcodes', 'static/uploads/photos', 'static/uploads/photos/faces']:
            os.makedirs(os.path.join(app.root_path, d), exist_ok=True)

        # 生成教练/品牌二维码（指向排行榜公开页）
        import qrcode
        coach_qr_path = os.path.join(app.root_path, 'static', 'uploads', 'qrcodes', 'coach_wechat.png')
        if not os.path.exists(coach_qr_path):
            base = app.config['PUBLIC_BASE_URL']
            qr = qrcode.make(f'{base}/leaderboard')
            qr.save(coach_qr_path)

    logging.basicConfig(level=logging.INFO)
    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
