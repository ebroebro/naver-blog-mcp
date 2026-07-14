"""_ensure_fresh_editor(실제 프로덕션 함수)가 "이어서 작성" 팝업을 진짜로
처리하고 완전히 빈 에디터를 만드는지 end-to-end로 검증한다.

절차(프로덕션과 동일한 순서로 진행):
0) 글쓰기 페이지 진입 직후 _ensure_fresh_editor(page, frame)부터 호출해
   기존에 남아있을 수 있는 팝업/이전 내용을 먼저 정리한다(프로덕션은 제목을
   만지기 전에 반드시 이걸 먼저 한다 — 순서가 다르면 재현이 안 됨).
1) 제목에 고유 마커 문자열 입력 → 임시저장(새 draft 확실히 생성)
2) 다른 페이지로 이동했다가 글쓰기 페이지 재진입(팝업 재현)
3) _ensure_fresh_editor(page, frame) 다시 호출
4) 제목 필드가 플레이스홀더("제목")로 완전히 비어있는지 확인
   (마커가 섞여 들어오면 실패 — 이전 글이 덮어써질 위험이 있다는 뜻)

실행: uv run python tests/inspect_continue_draft3.py
"""

import asyncio
import time

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.editor_helpers import is_visible, dismiss_help_panel
from naver_blog_mcp.automation.post_actions import _ensure_fresh_editor


async def get_title_text(page) -> str | None:
    frame = page.frame_locator(sel.MAIN_FRAME)
    title_locator = frame.locator(sel.TITLE_PARAGRAPH).first
    if await is_visible(title_locator, timeout=3000):
        return (await title_locator.text_content()).strip()
    return None


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()
        marker = f"이어쓰기검증{int(time.time())}"

        # 0) 진입 직후 먼저 정리(프로덕션 순서와 동일)
        await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        frame = page.frame_locator(sel.MAIN_FRAME)
        print("0) 진입 직후 _ensure_fresh_editor(page, frame) 호출...")
        await _ensure_fresh_editor(page, frame)
        frame = page.frame_locator(sel.MAIN_FRAME)
        print(f"   정리 후 제목 필드: {await get_title_text(page)!r}")

        # 1) 마커 입력 + 임시저장 (새 draft 생성)
        title_field = frame.locator(sel.TITLE_PARAGRAPH).first
        await title_field.click(timeout=8000)
        await page.keyboard.type(marker)
        await page.wait_for_timeout(500)
        print(f"\n1) 제목에 마커 입력: {marker!r}")

        draft_button = frame.get_by_role("button", name=sel.SAVE_DRAFT_BTN_NAME).first
        await dismiss_help_panel(page, frame)
        await draft_button.click(timeout=8000)
        await page.wait_for_timeout(2000)
        print("   임시저장 완료")

        # 2) 페이지 이탈 후 재진입 (팝업 재현)
        await page.goto("https://blog.naver.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        frame = page.frame_locator(sel.MAIN_FRAME)
        print(f"\n2) 재진입: url={page.url}")
        print(f"   재진입 직후 제목 필드: {await get_title_text(page)!r}")

        # 3) 실제 프로덕션 함수로 정리
        print("\n3) _ensure_fresh_editor(page, frame) 재호출...")
        await _ensure_fresh_editor(page, frame)
        print("   완료(예외 없음)")

        # _ensure_fresh_editor가 리로드했을 수 있으므로 frame을 다시 잡는다
        frame2 = page.frame_locator(sel.MAIN_FRAME)
        title_locator2 = frame2.locator(sel.TITLE_PARAGRAPH).first
        await title_locator2.wait_for(state="visible", timeout=15000)
        final_title = (await title_locator2.text_content()).strip()
        print(f"\n4) 최종 제목 필드 내용: {final_title!r}")

        if marker in final_title:
            print(f">>> 실패: 마커({marker})가 여전히 남아있음 — 이전 글이 덮어써질 위험이 있습니다.")
        elif final_title in ("", "제목"):
            print(">>> 성공: 제목 필드가 완전히 비어있음(플레이스홀더 상태) — 진짜 새 에디터입니다.")
        else:
            print(f">>> 애매함: 마커는 없지만 예상 못한 값({final_title!r})입니다.")
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
