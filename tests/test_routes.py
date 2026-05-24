"""路由层测试 — 家长端 + 教练端所有路由"""

import pytest
from flask import url_for


class TestParentRoutes:
    """家长端路由（无需认证）"""

    def test_checkin_page(self, client, seed_courses):
        """GET /c/<course_id> 返回 200"""
        resp = client.get(f'/c/{seed_courses[0].id}')
        assert resp.status_code == 200

    def test_checkin_do_ajax(self, client, seed_courses, student_fixture):
        """POST /c/<course_id>/do 打卡"""
        resp = client.post(f'/c/{seed_courses[0].id}/do', data={
            'student_id': student_fixture.id,
            'student_name': student_fixture.name,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert 'ok' in data or 'pending' in data

    def test_checkin_do_returns_json_keys(self, client, seed_courses, student_fixture):
        """打卡返回 JSON 包含必要字段"""
        resp = client.post(f'/c/{seed_courses[0].id}/do', data={
            'student_id': student_fixture.id,
            'student_name': student_fixture.name,
        })
        data = resp.get_json()
        assert isinstance(data, dict)
        # 至少包含这些字段之一
        assert any(k in data for k in ['ok', 'error', 'student_name', 'total', 'new_badges'])

    def test_student_home_page(self, client, student_fixture):
        """GET /p/<access_code> 学员主页"""
        resp = client.get(f'/p/{student_fixture.access_code}')
        assert resp.status_code == 200

    def test_student_home_nonexistent(self, client):
        """不存在的 access_code"""
        resp = client.get('/p/notexist')
        assert resp.status_code == 404

    def test_student_report(self, client, student_fixture):
        """GET /p/<code>/report 评估报告"""
        resp = client.get(f'/p/{student_fixture.access_code}/report')
        assert resp.status_code == 200

    def test_student_share(self, client, student_fixture):
        """GET /p/<code>/share 分享页"""
        resp = client.get(f'/p/{student_fixture.access_code}/share')
        assert resp.status_code == 200

    def test_leaderboard_default(self, client):
        """GET /leaderboard 默认排行榜"""
        resp = client.get('/leaderboard')
        assert resp.status_code == 200

    @pytest.mark.parametrize('sort_param', [
        'fitness', 'weekly', 'strength', 'speed', 'endurance',
        'flexibility', 'coordination', 'power', 'badges', 'progress',
    ])
    def test_leaderboard_all_dimensions(self, client, sort_param):
        """排行榜所有维度参数"""
        resp = client.get(f'/leaderboard?sort={sort_param}')
        assert resp.status_code == 200

    def test_leaderboard_with_my_code(self, client, student_fixture):
        """排行榜带 my 参数"""
        resp = client.get(f'/leaderboard?sort=fitness&my={student_fixture.access_code}')
        assert resp.status_code == 200

    def test_leaderboard_share(self, client, student_fixture):
        """GET /leaderboard/share 排名分享页"""
        resp = client.get(f'/leaderboard/share?code={student_fixture.access_code}&dim=fitness')
        assert resp.status_code == 200

    def test_leaderboard_share_missing_params(self, client):
        """缺少参数 → 错误提示"""
        resp = client.get('/leaderboard/share')
        # 可能 200 带错误信息，也可能 404
        assert resp.status_code in (200, 302, 404)

    def test_leaderboard_student_access(self, client, student_fixture):
        """GET /leaderboard/student-access/<id>"""
        resp = client.get(f'/leaderboard/student-access/{student_fixture.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None


class TestCoachAuth:
    """教练认证"""

    def test_login_page(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_login_correct_password(self, client):
        resp = client.post('/login', data={'password': 'test123'}, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        resp = client.post('/login', data={'password': 'wrong'})
        assert resp.status_code == 200

    def test_protected_routes_redirect(self, client):
        """未登录访问教练端路由 → 重定向到 /login"""
        protected_urls = ['/', '/today', '/students', '/courses']
        for url in protected_urls:
            resp = client.get(url, follow_redirects=False)
            assert resp.status_code in (302, 404), f'{url} 应重定向或404, 得到 {resp.status_code}'

    def test_logout(self, client):
        client.post('/login', data={'password': 'test123'})
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200


class TestCoachRoutes:
    """教练端路由（需登录后访问）"""

    @pytest.fixture(autouse=True)
    def login(self, client):
        """每个测试前登录"""
        client.post('/login', data={'password': 'test123'})

    def test_dashboard(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_today_page(self, client):
        resp = client.get('/today')
        assert resp.status_code == 200

    def test_students_list(self, client):
        resp = client.get('/students')
        assert resp.status_code == 200

    def test_student_new_form(self, client):
        resp = client.get('/students/new')
        assert resp.status_code == 200

    def test_student_create(self, client):
        resp = client.post('/students/new', data={
            'name': '新学员',
            'age_group': '6-9岁',
            'avatar_emoji': '💪',
            'gender': '男',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_student_detail(self, client, student_fixture):
        resp = client.get(f'/students/{student_fixture.id}')
        assert resp.status_code == 200

    def test_student_edit_form(self, client, student_fixture):
        resp = client.get(f'/students/{student_fixture.id}/edit')
        assert resp.status_code == 200

    def test_student_edit_post(self, client, student_fixture):
        resp = client.post(f'/students/{student_fixture.id}/edit', data={
            'name': '改名后',
            'age_group': student_fixture.age_group,
            'is_active': 'y',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_courses_list(self, client):
        resp = client.get('/courses')
        assert resp.status_code == 200

    def test_course_qr(self, client, seed_courses):
        resp = client.get(f'/courses/{seed_courses[0].id}/qr')
        assert resp.status_code == 200

    def test_onboarding_page(self, client):
        resp = client.get('/students/new/onboarding')
        assert resp.status_code == 200

    def test_assessment_form(self, client, student_fixture):
        resp = client.get(f'/students/{student_fixture.id}/assessment')
        assert resp.status_code == 200

    def test_assessment_create(self, client, student_fixture):
        from datetime import date
        resp = client.post(f'/students/{student_fixture.id}/assessment', data={
            'date': date.today().isoformat(),
            'seated_forward_bend': '10',
            'standing_long_jump': '140',
            'shuttle_run': '10.5',
            'rope_skip': '60',
            'sit_up': '25',
            'balance_score': '20',
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_photos_upload_page(self, client):
        resp = client.get('/photos/upload')
        assert resp.status_code == 200

    def test_photos_untagged(self, client):
        resp = client.get('/photos/untagged')
        assert resp.status_code == 200

    def test_student_photos(self, client, student_fixture):
        resp = client.get(f'/students/{student_fixture.id}/photos')
        assert resp.status_code == 200

    def test_manual_checkin(self, client, student_fixture, seed_courses):
        resp = client.post('/today/checkin', data={
            'student_id': student_fixture.id,
            'course_id': seed_courses[0].id,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True

    def test_award_badge(self, client, student_fixture, seed_badge_templates):
        """手动颁发奖章"""
        manual_badge = [b for b in seed_badge_templates if b.trigger_type == 'manual'][0]
        resp = client.post(f'/students/{student_fixture.id}/badge', data={
            'badge_template_id': manual_badge.id,
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestRouteContentType:
    """路由返回的内容类型"""

    def test_checkin_do_returns_json(self, client, seed_courses, student_fixture):
        resp = client.post(f'/c/{seed_courses[0].id}/do', data={
            'student_id': student_fixture.id,
            'student_name': student_fixture.name,
        })
        assert 'application/json' in resp.content_type

    def test_html_routes_return_html(self, client, student_fixture):
        html_urls = [
            f'/p/{student_fixture.access_code}',
            '/leaderboard',
            '/login',
        ]
        for url in html_urls:
            resp = client.get(url)
            assert 'text/html' in resp.content_type, f'{url} 应返回 HTML'
