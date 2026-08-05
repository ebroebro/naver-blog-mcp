"""네이버 로그인 전용 스크립트 — 세션이 만료됐거나 CAPTCHA가 떴을 때 수동으로 재인증한다.

.env의 HEADLESS 설정과 무관하게 이 스크립트는 항상 브라우저 창을 띄운다(headed) —
CAPTCHA가 뜨면 직접 풀 수 있도록. 로그인에 성공하면 세션을 config.SESSION_STORAGE_PATH에
저장하고 종료한다. 이후 MCP 서버(naver-blog-mcp)는 이 세션을 재사용해 계속 HEADLESS=true로
빠르게 동작한다 — 평소엔 이 스크립트를 돌릴 필요 없고, 세션이 만료될 때만 가끔 실행하면 된다.

사용법:
    uv run python scripts/login.py
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from playwright.async_api import async_playwright  # noqa: E402

from naver_blog_mcp.automation.login import NaverLoginError, login_to_naver  # noqa: E402
from naver_blog_mcp.config import config, get_context_config  # noqa: E402


async def main() -> None:
    config.validate()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=config.BROWSER_ARGS)
        context = await browser.new_context(**get_context_config())
        page = await context.new_page()

        try:
            result = await login_to_naver(
                page=page,
                user_id=config.NAVER_BLOG_ID,
                password=config.NAVER_BLOG_PASSWORD,
                storage_state_path=config.SESSION_STORAGE_PATH,
                headless=False,
            )
            print(f"\n✅ {result['message']}")
            print(f"   세션 저장: {result['storage_state_path']}")
            print("   이제 MCP 서버(HEADLESS=true)를 실행하면 이 세션을 재사용합니다.")
        except NaverLoginError as e:
            print(f"\n❌ 로그인 실패: {e}")
            Path("playwright-state").mkdir(parents=True, exist_ok=True)
            await page.screenshot(path="playwright-state/login_error.png")
            print("   에러 스크린샷 저장: playwright-state/login_error.png")
            sys.exit(1)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
