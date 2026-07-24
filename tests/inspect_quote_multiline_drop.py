"""실제 실패 사례와 동일한 5줄 인용구 내용으로 재현 — 어느 줄부터 씹히는지 확인.

실행: uv run python tests/inspect_quote_multiline_drop.py
동작: 문서 끝에 인용구(꺾쇠)를 삽입하고, 실패 사례와 동일한 텍스트를 현재 코드와
      똑같은 방식(줄마다 Enter + paste, 지연 없음)으로 채우되, 매 줄마다 그 시점의
      인용구 textContent를 덤프한다. 어느 줄에서부터 내용이 안 늘어나는지(씹히는지)
      직접 확인한다.
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.post_actions import _ensure_write_page
from naver_blog_mcp.automation.editor_helpers import (
    wait_and_dismiss_continue_draft_popup,
    dismiss_cascading_alerts,
    is_visible,
    paste_into_focused,
)

# 실패 사례와 완전히 동일한 텍스트.
QUOTE_TEXT = (
    "✅ 위치 & 기본정보\n\nLP바 제플린\n\n"
    "서울 서초구 사평대로56길 8 양정빌딩 지하1층\n\n신논현역\n\n영업시간 18:00~01:00"
)


async def dump_quote_text(frame, label: str) -> None:
    try:
        text = await frame.locator(".se-quotation").last.evaluate(
            "(e) => (e.textContent || '').replace(/\\s+/g, ' ').trim()"
        )
    except Exception as e:
        text = f"(조회 실패: {e})"
    print(f"[{label}] 인용구 현재 내용: {text!r}")


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()
        await _ensure_write_page(page)
        frame = page.frame_locator(sel.MAIN_FRAME)

        await wait_and_dismiss_continue_draft_popup(page, frame)
        await dismiss_cascading_alerts(page, frame)

        last_component = frame.locator(".se-component").last
        await last_component.click(timeout=8000)
        await page.keyboard.press("Control+End")
        await page.wait_for_timeout(300)

        await wait_and_dismiss_continue_draft_popup(page, frame)
        await dismiss_cascading_alerts(page, frame)

        # 인용구(꺾쇠) 삽입 — 현재 코드와 동일한 절차
        await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(600)
        style_option = frame.locator(sel.QUOTE_STYLE_CORNER_CSS).first
        if await is_visible(style_option, timeout=2000):
            await style_option.click(timeout=8000)
        else:
            print(">>> 꺾쇠 스타일 옵션을 못 찾음 — 기본 인용구로 폴백")
            await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(500)

        # 현재 코드와 완전히 동일한 방식(지연 없음)으로 줄마다 채우면서, 매 줄 직후 덤프.
        lines = QUOTE_TEXT.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                await page.keyboard.press("Enter")
            if line.strip():
                await paste_into_focused(page, line)
            await dump_quote_text(frame, f"줄 {i} 처리 후 (line={line!r})")

        print("\n>>> 어느 '줄 N 처리 후'부터 내용이 더 이상 안 늘어나는지 확인하세요.")
        print(">>> 만약 다 늘어났다면(5줄 다 보임) 타이핑 자체는 문제가 아니고, ")
        print(">>> 그 다음 ArrowDown 탈출 단계에서 뭔가 지우는지 별도로 봐야 합니다.")

        # 탈출 시도 후에도 덤프(내용이 탈출 과정에서 지워지는지 확인)
        await page.keyboard.press("ArrowDown")
        await dump_quote_text(frame, "ArrowDown 1회 후")
        await page.keyboard.press("ArrowDown")
        await dump_quote_text(frame, "ArrowDown 2회 후")
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
