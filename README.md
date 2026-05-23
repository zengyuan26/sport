# 少儿体能训练 H5 打卡系统

Apple Fitness 风格的少儿体能打卡系统。扫码即完成，零额外工作量。

## 三种二维码

| 码 | 谁扫 | 干什么 |
|---|------|------|
| SOP 课程码 | 家长/孩子 | 扫一下 → 选名字 → 打卡完成 |
| 学员个人码 | 家长 | 扫一下 → 出勤日历 + 奖章墙 + 体能趋势图 |
| 教练端 | 教练 | 手机浏览器登录，手动补打卡/录评估/发奖章 |

## 快速开始

```bash
pip install -r requirements.txt
python seed.py      # 初始化数据库 + 预置课程和奖章
python app.py       # 启动 http://localhost:5050
```

## 技术栈

Flask + SQLite + Jinja2 + Chart.js + qrcode
