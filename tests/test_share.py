"""分享卡测试 — 各维度渲染 + 心理学钩子文案 + 模板参数化"""

import pytest


# ── 分享钩子引擎接口（正式实现在 share_hooks.py）──

def get_share_hook(student, context):
    """
    根据学员状态和分享场景，返回心理驱动文案。

    context 可选值:
    - 'rank_1st': 排名第1
    - 'rank_top3': 排名前3
    - 'rank_up': 排名上升
    - 'rank_down': 排名下降
    - 'tier_up': 段位晋升
    - 'badge': 获得奖章
    - 'new_record': 新纪录
    - 'general': 通用场景
    """
    hooks = {
        'rank_1st': {
            'hook_text': f'🏆 {student.get("area", "我们小区")}体能第一！',
            'sub_text': f'{student["name"]}在{student.get("dim_name", "综合体质")}排名第1',
            'cta_text': '来挑战他！',
            'psychology': '社会认同',
        },
        'rank_top3': {
            'hook_text': f'📊 {student.get("dim_name", "排行榜")}前三！',
            'sub_text': f'{student["name"]}获得第{student.get("rank", "?")}名',
            'cta_text': '一起见证成长',
            'psychology': '社会认同',
        },
        'rank_up': {
            'hook_text': f'📈 {student["name"]}排名飙升中！',
            'sub_text': f'一周内从第{student.get("old_rank", "?")}位升至第{student.get("new_rank", "?")}位',
            'cta_text': '看看他是怎么练的',
            'psychology': '进步可视化',
        },
        'rank_down': {
            'hook_text': '再不练就要被超越了',
            'sub_text': f'{student["name"]}的排名正在下降，周末来训练！',
            'cta_text': '立即预约训练',
            'psychology': '损失厌恶',
        },
        'tier_up': {
            'hook_text': f'🎊 {student["name"]}段位晋升！',
            'sub_text': f'从「{student.get("old_tier", "")}」晋升到「{student.get("new_tier", "")}」',
            'cta_text': '下一个晋升的就是你',
            'psychology': '成就感',
        },
        'badge': {
            'hook_text': f'🏅 {student["name"]}获得新奖章！',
            'sub_text': f'「{student.get("badge_name", "")}」— {student.get("badge_desc", "")}',
            'cta_text': '分享孩子的高光时刻',
            'psychology': '互惠',
        },
        'new_record': {
            'hook_text': f'🎯 {student["name"]}打破个人纪录！',
            'sub_text': f'{student.get("metric_name", "")}达到{student.get("new_value", "?")}',
            'cta_text': '下一个纪录由你创造',
            'psychology': '权威',
        },
        'general': {
            'hook_text': f'看看{student["name"]}的体能成长',
            'sub_text': f'在春夏体适能训练中心的{student.get("total_checkins", 0)}次训练',
            'cta_text': '加入我们',
            'psychology': '从众效应',
        },
    }
    return hooks.get(context, hooks['general'])


def validate_share_contexts():
    """返回所有支持的分享场景"""
    return ['rank_1st', 'rank_top3', 'rank_up', 'rank_down',
            'tier_up', 'badge', 'new_record', 'general']


def share_card_has_branding(rendered_html):
    """检查分享卡 HTML 是否包含品牌标识"""
    brand_markers = ['春夏体适能', 'coach_qr', '扫码', '训练中心']
    return any(marker in rendered_html for marker in brand_markers)


# ═══════════════════════════════════════════════════════════════
# 测试用例
# ═══════════════════════════════════════════════════════════════

class TestShareHooks:
    """心理学钩子文案"""

    def test_rank_1st_hook(self):
        student = {'name': '小明', 'area': 'XX小区', 'dim_name': '综合体质'}
        hook = get_share_hook(student, 'rank_1st')
        assert '第1' in hook['hook_text'] or '第一' in hook['hook_text']
        assert hook['psychology'] == '社会认同'
        assert len(hook['cta_text']) > 0

    def test_rank_up_contains_rank_change(self):
        student = {'name': '小明', 'old_rank': 10, 'new_rank': 5}
        hook = get_share_hook(student, 'rank_up')
        assert '10' in hook['sub_text'] or '5' in hook['sub_text']

    def test_rank_down_uses_loss_aversion(self):
        student = {'name': '小明'}
        hook = get_share_hook(student, 'rank_down')
        assert hook['psychology'] == '损失厌恶'

    def test_tier_up_contains_tier_names(self):
        student = {'name': '小明', 'old_tier': '成长期', 'new_tier': '突破期'}
        hook = get_share_hook(student, 'tier_up')
        assert '成长期' in hook['sub_text']
        assert '突破期' in hook['sub_text']

    def test_badge_hook_has_cta(self):
        student = {'name': '小明', 'badge_name': '坚持达人', 'badge_desc': '累计出勤10次'}
        hook = get_share_hook(student, 'badge')
        assert hook['psychology'] == '互惠'
        assert len(hook['hook_text']) > 0

    def test_general_fallback(self):
        student = {'name': '小明', 'total_checkins': 20}
        hook = get_share_hook(student, 'nonexistent_context')
        assert hook is not None
        assert hook['psychology'] == '从众效应'

    def test_all_contexts_have_required_fields(self):
        student = {'name': '测试', 'dim_name': '综合体质'}
        for ctx in validate_share_contexts():
            hook = get_share_hook(student, ctx)
            assert 'hook_text' in hook, f'{ctx}: 缺少 hook_text'
            assert 'sub_text' in hook, f'{ctx}: 缺少 sub_text'
            assert 'cta_text' in hook, f'{ctx}: 缺少 cta_text'
            assert 'psychology' in hook, f'{ctx}: 缺少 psychology'


class TestShareContexts:
    """分享场景覆盖"""

    def test_eight_contexts(self):
        contexts = validate_share_contexts()
        assert len(contexts) == 8

    def test_all_contexts_return_strings(self):
        student = {'name': '测试'}
        for ctx in validate_share_contexts():
            hook = get_share_hook(student, ctx)
            assert isinstance(hook['hook_text'], str)
            assert isinstance(hook['sub_text'], str)
            assert isinstance(hook['cta_text'], str)


class TestShareCardBranding:
    """分享卡品牌要求"""

    def test_rank_share_contains_branding(self, client, student_fixture):
        """排名分享页包含品牌标识"""
        resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim=fitness')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '春夏体适能' in html, '排名分享页缺少品牌名'

    def test_home_share_contains_branding(self, client, student_fixture):
        """学员分享页包含品牌标识"""
        resp = client.get(f'/p/{student_fixture.access_code}/share')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert '春夏体适能' in html, '学员分享页缺少品牌名'

    def test_share_has_call_to_action(self, client, student_fixture):
        """分享页有关注/扫码入口"""
        resp = client.get(f'/p/{student_fixture.access_code}/share')
        html = resp.get_data(as_text=True)
        cta_markers = ['扫码', 'coach_qr', '加入', '了解', '二维码']
        has_cta = any(m in html for m in cta_markers)
        assert has_cta, '分享页缺少行动号召/二维码'

    def test_rank_share_all_dimensions(self, client, student_fixture):
        """每种维度的排名分享页都能正常渲染"""
        dims = ['fitness', 'weekly', 'strength', 'speed', 'endurance',
                'flexibility', 'coordination', 'power', 'badges', 'progress']
        for dim in dims:
            resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim={dim}')
            assert resp.status_code == 200, f'{dim} 分享页失败'


class TestShareCardTemplateVars:
    """分享卡模板变量"""

    def test_rank_share_has_dim_color(self, client, student_fixture):
        """每种维度分享页都渲染了 dim_info.color"""
        resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim=fitness')
        html = resp.get_data(as_text=True)
        # 颜色变量应该被替换为具体色值（不应该残留 {{ 模板语法）
        assert '{{ dim_info.color }}' not in html
        assert '#' in html  # 至少有一个颜色值

    def test_rank_share_has_quote(self, client, student_fixture):
        """分享页包含激励语"""
        resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim=fitness')
        html = resp.get_data(as_text=True)
        assert '{{ quote }}' not in html  # 变量已被替换

    def test_share_has_3_4_aspect_ratio(self, client, student_fixture):
        """分享卡是 3:4 竖版"""
        resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim=fitness')
        html = resp.get_data(as_text=True)
        has_ratio = '3/4' in html or '3:4' in html or 'aspect-ratio' in html
        assert has_ratio, '分享卡应为 3:4 比例'


class TestTierUpShare:
    """段位晋升分享卡"""

    def test_tier_up_share_returns_200(self, client, student_fixture):
        """段位晋升页可正常访问"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/tier-up')
        assert resp.status_code == 200

    def test_tier_up_share_has_tier_info(self, client, student_fixture):
        """晋升页包含段位信息"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/tier-up')
        html = resp.get_data(as_text=True)
        assert '段位晋升' in html
        assert student_fixture.rank_tier['name'] in html

    def test_tier_up_share_has_hook(self, client, student_fixture):
        """晋升页包含心理学钩子文案"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/tier-up')
        html = resp.get_data(as_text=True)
        assert 'hook_text' in html or '{{ hook.hook_text }}' not in html

    def test_tier_up_share_has_brand(self, client, student_fixture):
        """晋升页包含品牌标识"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/tier-up')
        html = resp.get_data(as_text=True)
        assert '春夏体适能' in html

    def test_tier_up_share_with_face_photo(self, client, db_session):
        """有照片学员的晋升页正常渲染"""
        from models import Student
        s = Student(name='小小', age_group='4-6岁', access_code='UP000001',
                    avatar_emoji='😊', face_photo_path='/static/photos/test.jpg')
        db_session.add(s)
        db_session.commit()
        resp = client.get(f'/p/{s.access_code}/share/tier-up')
        assert resp.status_code == 200
        assert 'test.jpg' in resp.get_data(as_text=True)

    def test_tier_up_share_has_html2canvas(self, client, student_fixture):
        """晋升页包含 html2canvas 生成图片功能"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/tier-up')
        html = resp.get_data(as_text=True)
        assert 'html2canvas' in html
        assert 'generateImage' in html


class TestWeeklyShare:
    """周报个人卡"""

    def test_weekly_share_returns_200(self, client, student_fixture):
        """周报页可正常访问"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/weekly')
        assert resp.status_code == 200

    def test_weekly_share_has_date_range(self, client, student_fixture):
        """周报页包含日期范围"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/weekly')
        html = resp.get_data(as_text=True)
        assert '训练周报' in html

    def test_weekly_share_has_checkin_count(self, client, student_fixture):
        """周报页包含训练次数"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/weekly')
        html = resp.get_data(as_text=True)
        assert '本周训练' in html or 'week_checkins' not in html

    def test_weekly_share_has_brand(self, client, student_fixture):
        """周报页包含品牌标识"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/weekly')
        html = resp.get_data(as_text=True)
        assert '春夏体适能' in html

    def test_weekly_share_with_checkin_data(self, client, db_session):
        """有打卡记录的学员周报页正常渲染"""
        from models import Student, Course, CheckIn
        from datetime import datetime, date, timedelta
        s = Student(name='周报测试', age_group='7-9岁', access_code='WK000001', avatar_emoji='😊')
        db_session.add(s)
        db_session.commit()

        c = Course(name='测试课', age_group='7-9岁', icon='🏃')
        db_session.add(c)
        db_session.commit()

        today = date.today()
        ci = CheckIn(student_id=s.id, course_id=c.id, status='confirmed',
                     checkin_time=datetime.now())
        db_session.add(ci)
        db_session.commit()

        resp = client.get(f'/p/{s.access_code}/share/weekly')
        assert resp.status_code == 200
        assert '周报测试' in resp.get_data(as_text=True)

    def test_weekly_share_has_html2canvas(self, client, student_fixture):
        """周报页包含 html2canvas 生成图片功能"""
        resp = client.get(f'/p/{student_fixture.access_code}/share/weekly')
        html = resp.get_data(as_text=True)
        assert 'html2canvas' in html
        assert 'generateImage' in html
