"""인용구 탈출 방법 후보(ArrowDown / 아래 영역 클릭 / Escape+Enter)를 한 번에 테스트한다.

inspect_quote_close.py 결과: Enter를 아무리 눌러도 인용구(se-quotation) 컴포넌트
자신의 textContent 안에 계속 누적될 뿐 별도 컴포넌트로 절대 분리되지 않음을 확인함
(Enter로는 인용구를 빠져나올 수 없다).

실행: uv run python tests/inspect_quote_close2.py
동작: 문서 맨 끝(기존 컴포넌트들 뒤)에 새 인용구(꺾쇠)를 삽입하고 텍스트를 채운 뒤,
      후보 탈출 방법을 순서대로 시도하며 그때마다 최상위 .se-component 목록을 덤프한다.
      각 후보는 고유 MARKER를 입력해, 그 MARKER가 인용구 안에 남는지 새 컴포넌트로
      분리되는지 바로 비교할 수 있게 한다.

주의: 실제 작성 중인 초안 문서 맨 끝에 테스트용 인용구/텍스트가 추가된다(임시저장
전이므로 저장하지 않으면 사라짐 — 필요하면 나중에 브라우저에서 지우면 됨).
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

        # 문서 맨 끝으로 이동 (마지막 컴포넌트 클릭 후 Ctrl+End)
        last_component = frame.locator(".se-component").last
        try:
            await last_component.click(timeout=8000)
        except Exception as e:
            print("마지막 컴포넌트 클릭 실패(무시):", e)
        await page.keyboard.press("Control+End")
        await page.wait_for_timeout(300)

        before = await frame.locator(".se-component").evaluate_all(_JS)
        base_count = len(before)
        print(f"인용구 삽입 전 컴포넌트 수: {base_count}")

        # 클릭 직전 재정리 — 자동저장 등으로 "확인" 알림 팝업이 뒤늦게 뜰 수 있음
        await dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)

        # 인용구(꺾쇠) 삽입
        await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(600)
        style_option = frame.locator(sel.QUOTE_STYLE_CORNER_CSS).first
        if await is_visible(style_option, timeout=2000):
            await style_option.click(timeout=8000)
        else:
            print(">>> 꺾쇠 스타일 옵션을 못 찾음 — 기본 인용구로 폴백")
            await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(500)

        await paste_into_focused(page, "탈출테스트 인용구 내용")
        await page.wait_for_timeout(300)
        await dump("0) 인용구 삽입 + 텍스트 입력 후", frame)

        # 후보 1: ArrowDown
        await page.keyboard.press("ArrowDown")
        await paste_into_focused(page, "MARKER-ARROWDOWN")
        await page.wait_for_timeout(300)
        await dump("1) ArrowDown 후 MARKER-ARROWDOWN 입력", frame)

        # 후보 2: Escape 후 Enter
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await page.wait_for_timeout(200)
        await page.keyboard.press("Enter")
        await paste_into_focused(page, "MARKER-ESCAPE-ENTER")
        await page.wait_for_timeout(300)
        await dump("2) Escape + Enter 후 MARKER-ESCAPE-ENTER 입력", frame)

        # 후보 3: 인용구 컴포넌트 바로 아래 좌표 클릭
        quote_components = frame.locator(".se-quotation")
        qcount = await quote_components.count()
        if qcount > 0:
            box = await quote_components.last.bounding_box()
            if box:
                click_x = box["x"] + box["width"] / 2
                click_y = box["y"] + box["height"] + 15
                await page.mouse.click(click_x, click_y)
                await page.wait_for_timeout(300)
                await paste_into_focused(page, "MARKER-CLICKBELOW")
                await page.wait_for_timeout(300)
                await dump("3) 인용구 아래 좌표 클릭 후 MARKER-CLICKBELOW 입력", frame)
            else:
                print(">>> 인용구 bounding_box를 못 가져옴")
        else:
            print(">>> se-quotation 요소를 못 찾음(후보3 스킵)")

        print(
            "\n>>> 각 단계에서 MARKER-*가 인용구(se-quotation) 컴포넌트 안에 남아있는지, "
            "아니면 새로운 se-text(또는 다른) 컴포넌트로 분리됐는지 비교하세요. "
            "분리된 첫 후보가 실제로 쓸 수 있는 탈출 방법입니다."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
