"""인용구 스타일 드롭다운 팝업의 옵션 DOM을 덤프한다 (브라켓/꺾쇠 스타일 셀렉터 확정용).

실행: uv run python tests/inspect_quote_popup.py
동작: 글쓰기 페이지 진입 → 팝업 닫기 → 본문 포커스 → "인용구 선택" 드롭다운 열기
      → 관련 요소(button/option/li/a)의 tag/text/aria/data-value/class 덤프.
출력을 그대로 붙여주면 원하는 꺾쇠 스타일의 정확한 CSS 클래스를 확정한다
(구분선2 확정 때와 동일한 절차).
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.post_actions import _ensure_write_page
from naver_blog_mcp.automation.editor_helpers import (
    dismiss_continue_draft_popup,
    dismiss_cascading_alerts,
    click_resilient,
)

_JS = r"""
(els) => els
  .map(e => ({
    tag: e.tagName.toLowerCase(),
    text: (e.textContent || '').trim().slice(0, 24),
    aria: e.getAttribute('aria-label'),
    dataValue: e.getAttribute('data-value'),
    dataName: e.getAttribute('data-name'),
    cls: (e.className || '').toString().slice(0, 170),
    visible: e.offsetParent !== null,
  }))
  .filter(x => x.visible && (
    /quotation|quote|인용/i.test(x.cls) ||
    /인용/.test(x.aria || '') ||
    /인용/.test(x.text || '') ||
    x.dataName === 'quotation'
  ))
"""

_SEL = "button, [role='option'], li, a"


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()
        await _ensure_write_page(page)
        frame = page.frame_locator(sel.MAIN_FRAME)

        await dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)
        try:
            await frame.locator(sel.BODY_FIRST_PARAGRAPH).first.click(timeout=8000)
        except Exception as e:
            print("본문 포커스 실패(무시):", e)
        await page.wait_for_timeout(500)

        print(f"열기: {sel.QUOTE_SELECT_BTN_CSS}")
        await click_resilient(page, frame, frame.locator(sel.QUOTE_SELECT_BTN_CSS).first)
        await page.wait_for_timeout(1200)

        frame_els = await frame.locator(_SEL).evaluate_all(_JS)
        page_els = await page.locator(_SEL).evaluate_all(_JS)

        print("\n=== #mainFrame 안 (인용구 관련) ===")
        for i, x in enumerate(frame_els):
            print(i, x)
        print("\n=== page 최상단 (인용구 관련) ===")
        for i, x in enumerate(page_els):
            print(i, x)
        print(f"\n(frame {len(frame_els)}개 / page {len(page_els)}개)")
        if not frame_els and not page_els:
            print(">>> 관련 요소가 하나도 안 잡힘 — 드롭다운이 안 열렸거나 다른 컨테이너일 수 있음.")
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
