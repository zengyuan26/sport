"""预置 SOP 课程和奖章模板"""
from app import create_app
from models import db, Course, BadgeTemplate

app = create_app()

COURSES = [
    # 3-6岁 感统体适能
    {'name': '感统训练·基础循环第1节', 'age_group': '3-6岁', 'duration': 60,
     'description': '动物爬行模仿 + 平衡木行走 + 前滚翻启蒙', 'icon': '🐻'},
    {'name': '感统训练·基础循环第2节', 'age_group': '3-6岁', 'duration': 60,
     'description': '触觉感知 + 障碍跳跃 + 球类游戏', 'icon': '⚽'},
    {'name': '感统训练·基础循环第3节', 'age_group': '3-6岁', 'duration': 60,
     'description': '本体感觉 + 爬行穿越 + 追逐游戏', 'icon': '🦀'},
    {'name': '感统训练·基础循环第4节', 'age_group': '3-6岁', 'duration': 60,
     'description': '前庭觉训练 + 翻滚进阶 + 团队协作', 'icon': '🤸'},

    # 6-9岁 基础体能
    {'name': '基础体能·力量入门', 'age_group': '6-9岁', 'duration': 60,
     'description': '自重训练 + 核心力量 + 弹力带基础', 'icon': '💪'},
    {'name': '基础体能·速度敏捷', 'age_group': '6-9岁', 'duration': 60,
     'description': '折返跑 + 绳梯 + 反应训练', 'icon': '⚡'},
    {'name': '基础体能·协调跳跃', 'age_group': '6-9岁', 'duration': 60,
     'description': '跳绳基础 + 跳箱入门 + 跨栏步', 'icon': '🦘'},
    {'name': '基础体能·柔韧平衡', 'age_group': '6-9岁', 'duration': 60,
     'description': '动态拉伸 + 瑜伽启蒙 + 平衡进阶', 'icon': '🧘'},

    # 9-12岁 进阶体能
    {'name': '进阶体能·爆发力', 'age_group': '9-12岁', 'duration': 60,
     'description': '立定跳远 + 冲刺跑 + 跳箱进阶', 'icon': '🚀'},
    {'name': '进阶体能·耐力心肺', 'age_group': '9-12岁', 'duration': 60,
     'description': '间歇跑 + 跳绳耐力 + 循环训练', 'icon': '🏃'},
    {'name': '进阶体能·力量进阶', 'age_group': '9-12岁', 'duration': 60,
     'description': '哑铃基础 + 阻力训练 + 核心进阶', 'icon': '🏋️'},

    # 中考体育
    {'name': '中考体育·跳绳专项', 'age_group': '11-15岁', 'duration': 60,
     'description': '跳绳技巧 + 速度突破 + 耐力训练', 'icon': '🪢'},
    {'name': '中考体育·跑步专项', 'age_group': '11-15岁', 'duration': 60,
     'description': '800/1000米训练 + 起跑技巧 + 配速策略', 'icon': '🏃'},
    {'name': '中考体育·跳远专项', 'age_group': '11-15岁', 'duration': 60,
     'description': '立定跳远技术 + 爆发力训练', 'icon': '📏'},
    {'name': '中考体育·仰卧起坐专项', 'age_group': '11-15岁', 'duration': 60,
     'description': '核心力量 + 技巧优化 + 速度突破', 'icon': '🔄'},
    {'name': '中考体育·综合模拟', 'age_group': '11-15岁', 'duration': 90,
     'description': '全项目模拟测试 + 弱项分析', 'icon': '📋'},
]

BADGES = [
    # ── 出勤里程碑（自动）──
    {'name': '初次打卡', 'description': '开启体能之旅的第一步', 'icon': '🌟',
     'trigger_type': 'attendance_count', 'trigger_value': 1},
    {'name': '坚持10次', 'description': '累计完成10次训练', 'icon': '⭐',
     'trigger_type': 'attendance_count', 'trigger_value': 10},
    {'name': '坚持30次', 'description': '累计完成30次训练', 'icon': '🔥',
     'trigger_type': 'attendance_count', 'trigger_value': 30},
    {'name': '坚持50次', 'description': '累计完成50次训练', 'icon': '👑',
     'trigger_type': 'attendance_count', 'trigger_value': 50},
    {'name': '坚持100次', 'description': '累计完成100次训练', 'icon': '💎',
     'trigger_type': 'attendance_count', 'trigger_value': 100},

    # ── 连续出勤（自动）──
    {'name': '一周全勤', 'description': '连续7天坚持训练', 'icon': '📅',
     'trigger_type': 'streak_days', 'trigger_value': 7},
    {'name': '两周坚持', 'description': '连续14天坚持训练', 'icon': '🗓️',
     'trigger_type': 'streak_days', 'trigger_value': 14},
    {'name': '月度全勤王', 'description': '连续30天不间断训练', 'icon': '🏆',
     'trigger_type': 'streak_days', 'trigger_value': 30},

    # ── 体能突破（手动颁发）──
    {'name': '跳绳破百', 'description': '1分钟跳绳突破100个', 'icon': '🪢',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '跳绳150+', 'description': '1分钟跳绳突破150个', 'icon': '⛓️',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '仰卧起坐50+', 'description': '1分钟仰卧起坐突破50个', 'icon': '💪',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '体前屈15cm+', 'description': '坐位体前屈突破15厘米', 'icon': '🤸',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '跳远180cm+', 'description': '立定跳远突破180厘米', 'icon': '🚀',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '折返跑破8秒', 'description': '10米折返跑突破8秒', 'icon': '⚡',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '平衡30秒+', 'description': '闭眼单脚站立突破30秒', 'icon': '🧘',
     'trigger_type': 'manual', 'trigger_value': None},

    # ── 阶段成就（手动颁发）──
    {'name': '感统达人', 'description': '完成感统训练全部4节循环', 'icon': '🧩',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '基础体能毕业', 'description': '完成基础体能全部课程', 'icon': '🎓',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '全项目A级', 'description': '体测所有项目达到优秀', 'icon': '🎖️',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '中考满分冲刺', 'description': '中考体育模拟达到满分标准', 'icon': '💯',
     'trigger_type': 'manual', 'trigger_value': None},

    # ── 专项训练次数（自动，按课程类型）──
    {'name': '跳绳专项×10', 'description': '完成10次跳绳专项训练', 'icon': '🪢',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '跑步专项×10', 'description': '完成10次跑步专项训练', 'icon': '🏃',
     'trigger_type': 'manual', 'trigger_value': None},
    {'name': '感统训练×10', 'description': '完成10次感统训练', 'icon': '🧠',
     'trigger_type': 'manual', 'trigger_value': None},
]


def seed():
    with app.app_context():
        db.create_all()

        if Course.query.count() == 0:
            for c in COURSES:
                db.session.add(Course(**c))
            print(f'添加了 {len(COURSES)} 个预置课程')

        if BadgeTemplate.query.count() == 0:
            for b in BADGES:
                db.session.add(BadgeTemplate(**b))
            print(f'添加了 {len(BADGES)} 个奖章模板')

        db.session.commit()
        print('初始化完成！')


if __name__ == '__main__':
    seed()
