import os
import logging
from flask import Flask
from config import Config
from models import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from routes import fitness_bp
        app.register_blueprint(fitness_bp)

        db.create_all()

        # 首次启动自动初始化预置数据
        from models import Course
        if Course.query.count() == 0:
            from seed import COURSES, BADGES
            from models import BadgeTemplate
            for c in COURSES:
                db.session.add(Course(**c))
            for b in BADGES:
                db.session.add(BadgeTemplate(**b))
            db.session.commit()

        # 确保上传目录
        for d in ['static/uploads/qrcodes', 'static/uploads/photos']:
            os.makedirs(os.path.join(app.root_path, d), exist_ok=True)

    logging.basicConfig(level=logging.INFO)
    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
