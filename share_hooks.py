"""分享钩子引擎 — 心理学驱动的动态文案生成"""

# 复用 consumer-psychology-expert 的方法论:
#   - 信任公式: 信任 = 身份 × 经验 × 逻辑 × 情感
#   - 冲突点设计: 认知冲突 / 情感冲突 / 场景冲突
#   - AIDA 模型: Attention → Interest → Desire → Action
#   - Cialdini 6原则: 互惠 / 承诺一致 / 社会认同 / 权威 / 喜好 / 稀缺

SHARE_CONTEXTS = [
    'rank_1st',      # 排名第1
    'rank_top3',     # 排名前3
    'rank_up',       # 排名上升
    'rank_down',     # 排名下降
    'tier_up',       # 段位晋升
    'badge',         # 获得奖章
    'new_record',    # 新纪录
    'general',       # 通用
]


def get_share_hook(student, context, extra=None):
    """
    根据学员状态和分享场景返回心理驱动文案。

    Args:
        student: dict with keys like name, area, dim_name, rank, etc.
        context: one of SHARE_CONTEXTS
        extra: 额外上下文数据

    Returns:
        { hook_text, sub_text, cta_text, psychology, color }
    """
    if extra is None:
        extra = {}

    hooks = {
        'rank_1st': _hook_rank_1st(student, extra),
        'rank_top3': _hook_rank_top3(student, extra),
        'rank_up': _hook_rank_up(student, extra),
        'rank_down': _hook_rank_down(student, extra),
        'tier_up': _hook_tier_up(student, extra),
        'badge': _hook_badge(student, extra),
        'new_record': _hook_new_record(student, extra),
        'general': _hook_general(student, extra),
    }

    hook = hooks.get(context, hooks['general'])
    # 确保所有必要字段存在
    return {
        'hook_text': hook.get('hook_text', ''),
        'sub_text': hook.get('sub_text', ''),
        'cta_text': hook.get('cta_text', ''),
        'psychology': hook.get('psychology', '从众效应'),
        'color': hook.get('color', '#007AFF'),
    }


def _hook_rank_1st(student, extra):
    area = student.get('area', '我们这儿')
    dim_name = extra.get('dim_name', student.get('dim_name', '综合体质'))
    return {
        'hook_text': f'🏆 {area}体能第一！',
        'sub_text': f'{student["name"]}在「{dim_name}」排名第1',
        'cta_text': '来挑战他！',
        'psychology': '社会认同',
        'color': '#FFD700',
    }


def _hook_rank_top3(student, extra):
    rank = student.get('rank', '?')
    dim_name = extra.get('dim_name', student.get('dim_name', '排行榜'))
    return {
        'hook_text': f'📊 {dim_name}前{rank}！',
        'sub_text': f'{student["name"]}获得第{rank}名',
        'cta_text': '一起见证成长',
        'psychology': '社会认同',
        'color': '#FF9500',
    }


def _hook_rank_up(student, extra):
    old_rank = student.get('old_rank', '?')
    new_rank = student.get('new_rank', '?')
    return {
        'hook_text': f'📈 {student["name"]}排名飙升中！',
        'sub_text': f'从第{old_rank}位升至第{new_rank}位',
        'cta_text': '看看他是怎么练的',
        'psychology': '进步可视化',
        'color': '#34C759',
    }


def _hook_rank_down(student, extra):
    return {
        'hook_text': '⚡ 再不练就要被超越了',
        'sub_text': f'{student["name"]}的排名正在下降，周末来训练！',
        'cta_text': '立即预约训练',
        'psychology': '损失厌恶',
        'color': '#FF3B30',
    }


def _hook_tier_up(student, extra):
    old_tier = student.get('old_tier', '')
    new_tier = student.get('new_tier', '')
    return {
        'hook_text': f'🎊 {student["name"]}段位晋升！',
        'sub_text': f'从「{old_tier}」晋升到「{new_tier}」',
        'cta_text': '下一个晋升的就是你',
        'psychology': '成就感',
        'color': '#FF9500',
    }


def _hook_badge(student, extra):
    badge_name = student.get('badge_name', '')
    badge_desc = student.get('badge_desc', '')
    return {
        'hook_text': f'🏅 {student["name"]}获得新奖章！',
        'sub_text': f'「{badge_name}」— {badge_desc}',
        'cta_text': '分享孩子的高光时刻',
        'psychology': '互惠',
        'color': '#FFD700',
    }


def _hook_new_record(student, extra):
    metric_name = student.get('metric_name', '')
    new_value = student.get('new_value', '?')
    return {
        'hook_text': f'🎯 {student["name"]}打破个人纪录！',
        'sub_text': f'{metric_name}达到{new_value}',
        'cta_text': '下一个纪录由你创造',
        'psychology': '权威',
        'color': '#FF3B30',
    }


def _hook_general(student, extra):
    total = student.get('total_checkins', 0)
    return {
        'hook_text': f'看看{student["name"]}的体能成长',
        'sub_text': f'在春夏体适能训练中心的{total}次训练',
        'cta_text': '加入我们',
        'psychology': '从众效应',
        'color': '#007AFF',
    }


def get_share_card_config(student, context, extra=None):
    """
    返回完整的分享卡配置，供 Jinja2 模板使用。

    返回: {
        hook: { hook_text, sub_text, cta_text, psychology },
        student: { name, avatar, rank, score, tier, ... },
        dim: { name, icon, color, unit },
        branding: { gym_name, qr_url },
        meta: { context, template }
    }
    """
    hook = get_share_hook(student, context, extra)

    return {
        'hook': hook,
        'student': student,
        'meta': {
            'context': context,
        },
        'branding': {
            'gym_name': '春夏体适能训练中心',
        },
    }
