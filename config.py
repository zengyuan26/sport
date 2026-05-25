import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)  # CloudBase CFS 挂载路径


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
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(DATA_DIR, "fitness.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FITNESS_COACH_PASSWORD = os.environ.get('FITNESS_COACH_PASSWORD', 'coach123')
    _env_url = os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('PUBLIC_BASE_URL')
    if _env_url:
        PUBLIC_BASE_URL = _env_url
    else:
        # 自动检测局域网 IP，手机扫码可访问
        import subprocess, re
        lan_ip = '127.0.0.1'
        try:
            out = subprocess.check_output(['ifconfig'], text=True)
            # 找所有 inet 地址，排除 127.x
            ips = re.findall(r'inet (\d+\.\d+\.\d+\.\d+)', out)
            ips = [ip for ip in ips if not ip.startswith('127.')]
            # 优先 192.168，其次 10.，再次 172.
            for ip in ips:
                if ip.startswith('192.168.'):
                    lan_ip = ip; break
            if lan_ip == '127.0.0.1':
                for ip in ips:
                    if ip.startswith('10.'):
                        lan_ip = ip; break
            if lan_ip == '127.0.0.1':
                for ip in ips:
                    if ip.startswith('172.'):
                        lan_ip = ip; break
            if lan_ip == '127.0.0.1' and ips:
                lan_ip = ips[0]
        except Exception:
            pass
        PUBLIC_BASE_URL = f'http://{lan_ip}:5050'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
