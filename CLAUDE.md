# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 启动与开发

```bash
pip install -r requirements.txt
python seed.py      # 初始化 SQLite + 预置课程/奖章（首次或重置时运行）
python app.py       # 启动 http://localhost:5050
```

教练端默认密码: `coach123`（在 `.env` 的 `FITNESS_COACH_PASSWORD` 中修改）。

端口在 `app.py:30`，默认 5050（避开 macOS AirPlay 占用的 5000）。

## 架构

单文件 Flask 应用，所有代码平铺在根目录：

- `app.py` — Flask 工厂，注册 blueprint，`db.create_all()` 建表
- `config.py` — 配置从环境变量读取，fallback 到默认值
- `models.py` — 6 个 SQLAlchemy 模型，SQLite
- `routes.py` — 唯一的 Blueprint `fitness_bp`，无 url_prefix
- `seed.py` — 预置数据（16 个 Course + 22 个 BadgeTemplate）

**数据模型**: Student → CheckIn（打卡记录，FK 到 Course） / Assessment（体能评估） / StudentBadge（获得的奖章，FK 到 BadgeTemplate）

**二维码**: 服务端 `qrcode` 库生成 PNG，存 `static/uploads/qrcodes/`。课程码指向 `/c/<course_id>`，学员个人码指向 `/p/<access_code>`。

**认证**: 教练端基于 Flask session，密码比对 `FITNESS_COACH_PASSWORD`。家长端无需登录。

## 路由结构

| 前缀 | 认证 | 用途 |
|------|------|------|
| `/login` `/logout` | 无 | 教练登录 |
| `/` `/today` `/students` `/courses` | coach_required | 教练端管理页 |
| `/students/<id>` `/students/<id>/assessment` | coach_required | 学员详情、评估录入 |
| `/c/<course_id>` `/c/<course_id>/do` | 无 | 家长扫码打卡 |
| `/p/<access_code>` | 无 | 家长查看孩子主页 |

## 模板

- `templates/coach/` — 教练端 9 个页面，继承 `base.html`（移动优先 CSS，无 Bootstrap）
- `templates/parent/` — 家长端 2 个独立页面（自包含 CSS，微信浏览器兼容）
  - `checkin.html` — 打卡确认页，AJAX 提交
  - `home.html` — 孩子主页，Chart.js CDN 画体能趋势图

## 奖章系统

`check_auto_badges()` 在每次打卡后自动检查出勤次数和连续天数奖章。评估突破类奖章由教练手动颁发。
