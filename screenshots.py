"""使用 Playwright 截取关键页面截图，用于使用说明文档"""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5050"
OUT = os.path.join(os.path.dirname(__file__), "static", "screenshots")
PASSWORD = "coach123"
VIEWPORT = {"width": 375, "height": 812}

os.makedirs(OUT, exist_ok=True)


def shot(page, name, full_page=False):
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=full_page)
    print(f"  OK {name}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)

        # ── 公开页 ──
        print("公开页...")
        page = ctx.new_page()
        page.goto(f"{BASE}/leaderboard", wait_until="networkidle")
        page.wait_for_timeout(800)
        shot(page, "01-leaderboard.png")

        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "02-login.png")

        # ── 教练端（登录） ──
        print("教练端...")
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE}/", timeout=10000)
        page.wait_for_timeout(800)
        shot(page, "03-dashboard.png")

        page.goto(f"{BASE}/coach/today", wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "04-today.png")

        page.goto(f"{BASE}/coach/content", wait_until="networkidle")
        page.wait_for_timeout(800)
        shot(page, "05-content.png")

        page.goto(f"{BASE}/coach/students", wait_until="networkidle")
        page.wait_for_timeout(500)
        shot(page, "06-students.png")

        # 学员评估录入
        page.goto(f"{BASE}/coach/student/2/assessment/new", wait_until="networkidle")
        page.wait_for_timeout(600)
        shot(page, "07-assessment.png")

        # ── 家长端 ──
        print("家长端...")
        page.goto(f"{BASE}/p/0551a167", wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot(page, "08-student-home.png", full_page=True)

        page.goto(f"{BASE}/p/0551a167/report", wait_until="networkidle")
        page.wait_for_timeout(1000)
        shot(page, "09-report.png", full_page=True)

        page.goto(f"{BASE}/booking?code=0551a167", wait_until="networkidle")
        page.wait_for_timeout(600)
        shot(page, "10-booking.png")

        page.goto(f"{BASE}/p/0551a167/share", wait_until="networkidle")
        page.wait_for_timeout(800)
        shot(page, "11-share-card.png")

        browser.close()
        print(f"\n完成！截图目录: {OUT}")


if __name__ == "__main__":
    main()
