"""인용구 탈출 후보 2차: 연속 ArrowDown(최대 3회) / Tab / 문서 맨 아래 큰 오프셋 클릭.

이전 라운드(inspect_quote_close2.py) 결과: ArrowDown 1회는 인용구의 "내용" 필드에서
"출처" 필드로 이동시킬 뿐(placeholder "출처 입력"이 사라짐), 컴포넌트 밖으로는
못 나갔다. Escape+Enter, 인용구 바로 아래(+15px) 클릭도 모두 실패.

이번엔 ArrowDown을 최대 3회 연속으로 눌러가며 매번 다른 MARKER로 확인하고,
Tab 키, 그리고 훨씬 더 큰 오프셋(+150px)으로 문서 최하단을 클릭하는 것도 시도한다.

실행: uv run python tests/inspect_quote_close3.py
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.post_actions import _ensure_write_page
from naver_blog_mcp.automation.editor_helpers import (
    dismiss_continue_draft_popup,
    dismiss_cascading_alerts,
    is_visible,
    paste_into_focused,
)

_JS = r"""
(els) => els.map((e, i) => ({
  i,
  cls: (e.className || '').toString().slice(0, 100),
  text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80),
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

        last_component = frame.locator(".se-component").last
        try:
            await last_component.click(timeout=8000)
        except Exception as e:
            print("마지막 컴포넌트 클릭 실패(무시):", e)
        await page.keyboard.press("Control+End")
        await page.wait_for_timeout(300)

        before = await frame.locator(".se-component").evaluate_all(_JS)
        print(f"인용구 삽입 전 컴포넌트 수: {len(before)}")

        await dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)

        await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(600)
        style_option = frame.locator(sel.QUOTE_STYLE_CORNER_CSS).first
        if await is_visible(style_option, timeout=2000):
            await style_option.click(timeout=8000)
        else:
            print(">>> 꺾쇠 스타일 옵션을 못 찾음 — 기본 인용구로 폴백")
            await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(500)

        await paste_into_focused(page, "탈출3테스트 내용")
        await page.wait_for_timeout(300)
        await dump("0) 인용구 삽입 + 텍스트 입력 후", frame)

        # 연속 ArrowDown 최대 3회, 매번 다른 마커로 확인
        for n in (1, 2, 3):
            await page.keyboard.press("ArrowDown")
            await paste_into_focused(page, f"MARKER-DOWN{n}")
            await page.wait_for_timeout(300)
            await dump(f"{n}) ArrowDown {n}회 누적 후 MARKER-DOWN{n} 입력", frame)

        # Tab 키 시도
        await page.keyboard.press("Tab")
        await paste_into_focused(page, "MARKER-TAB")
        await page.wait_for_timeout(300)
        await dump("4) Tab 후 MARKER-TAB 입력", frame)

        # 문서 최하단 큰 오프셋(+150px) 클릭
        quote_components = frame.locator(".se-quotation")
        qcount = await quote_components.count()
        if qcount > 0:
            box = await quote_components.last.bounding_box()
            if box:
                click_x = box["x"] + box["width"] / 2
                click_y = box["y"] + box["height"] + 150
                await page.mouse.click(click_x, click_y)
                await page.wait_for_timeout(300)
                await paste_into_focused(page, "MARKER-CLICKFAR")
                await page.wait_for_timeout(300)
                await dump("5) +150px 아래 클릭 후 MARKER-CLICKFAR 입력", frame)
            else:
                print(">>> bounding_box 못 가져옴")

        print(
            "\n>>> MARKER-DOWN1/2/3, MARKER-TAB, MARKER-CLICKFAR 중 어느 것이 "
            "처음으로 se-quotation이 아닌 새 컴포넌트(예: se-text)에 나타나는지 확인하세요."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
