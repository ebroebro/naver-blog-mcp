"""인용구(꺾쇠 스타일) 삽입 후 커서가 어떻게 빠져나오는지 확인하는 라이브 DOM 조사 스크립트.

실행: uv run python tests/inspect_quote_close.py
동작: 글쓰기 페이지 진입 → 팝업 닫기 → 본문 포커스 → 인용구(꺾쇠) 삽입
      → 텍스트 채우기 → Enter 1회/2회 시도마다 최상위 .se-component 목록을
      (class, textContent 일부) 스냅샷으로 덤프한다.

핵심 질문: Enter를 눌렀을 때 "MARKER1"/"MARKER2"가 인용구 컴포넌트 자신의
textContent 안에 남는지(= 아직 인용구 안), 아니면 별도의 새 .se-component로
분리되는지(= 인용구를 빠져나옴)를 눈으로 확인한다.
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.post_actions import _ensure_write_page
from naver_blog_mcp.automation.editor_helpers import (
    dismiss_continue_draft_popup,
    dismiss_cascading_alerts,
    click_resilient,
    is_visible,
    paste_into_focused,
)

_JS = r"""
(els) => els.map((e, i) => ({
  i,
  cls: (e.className || '').toString().slice(0, 100),
  text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60),
}))
"""


async def dump(label: str, frame) -> None:
    comps = await frame.locator(".se-component").evaluate_all(_JS)
    print(f"\n=== {label} ({len(comps)}개) ===")
    for c in comps:
        print(c)


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

        # 1) 인용구(꺾쇠) 삽입
        await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(600)
        style_option = frame.locator(sel.QUOTE_STYLE_CORNER_CSS).first
        if await is_visible(style_option, timeout=2000):
            await style_option.click(timeout=8000)
        else:
            print(">>> 꺾쇠 스타일 옵션을 못 찾음 — 기본 인용구로 폴백")
            await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(500)

        await dump("A) 인용구 삽입 직후 (텍스트 입력 전)", frame)

        # 2) 텍스트 채우기 (실제 코드와 동일하게 줄바꿈마다 Enter)
        lines = ["테스트 인용구 첫줄", "테스트 인용구 둘째줄"]
        for i, line in enumerate(lines):
            if i > 0:
                await page.keyboard.press("Enter")
            await paste_into_focused(page, line)
        await page.wait_for_timeout(300)

        await dump("B) 인용구 텍스트 입력 후", frame)

        # 3) Enter 1회 후 MARKER1 입력
        await page.keyboard.press("Enter")
        await paste_into_focused(page, "MARKER1")
        await page.wait_for_timeout(300)

        await dump("C) Enter 1회 + MARKER1 입력 후", frame)

        # 4) Enter 1회 더(누적 2회) 후 MARKER2 입력
        await page.keyboard.press("Enter")
        await paste_into_focused(page, "MARKER2")
        await page.wait_for_timeout(300)

        await dump("D) Enter 2회(누적) + MARKER2 입력 후", frame)

        print(
            "\n>>> B/C/D에서 MARKER1/MARKER2가 어느 컴포넌트(class)의 text 안에 "
            "포함돼 있는지 확인하세요. 인용구 컴포넌트(se-quotation 등) 안에 "
            "그대로 있으면 아직 못 빠져나온 것이고, 별도의 새 컴포넌트(se-text 등)로 "
            "분리됐으면 빠져나온 것입니다."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
