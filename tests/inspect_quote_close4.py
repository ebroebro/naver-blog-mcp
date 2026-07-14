"""인용구 탈출 3차: 문서 "진짜 맨 끝"에서 후보를 정밀 테스트한다.

이전 라운드(close2/close3) 핵심 발견:
- ArrowDown 1회: 인용구의 "내용" 필드 → "출처" 필드로 이동(placeholder "출처 입력"이
  사라짐). 아직 컴포넌트 안.
- ArrowDown 2회(누적): 실제로 컴포넌트를 빠져나가 다음 형제로 이동함(단, 이전
  라운드는 컴포넌트 목록 로딩 타이밍 레이스 때문에 "다음 형제"가 기존 문단 중간
  이었음 — 진짜 문서 끝에서는 어떻게 되는지 아직 정밀 확인 안 됨).
- Escape+Enter, 인용구 아래 좌표 클릭(+15px/+150px), Tab: 전부 실패.

이번엔 컴포넌트 개수가 안정될 때까지 폴링해 타이밍 레이스를 없애고, 문서 "진짜
맨 끝"에 인용구를 삽입해 두 후보를 정밀 테스트한다:
  A) ArrowDown 1회(내용→출처 필드) 후 Enter
  B) ArrowDown 2회(내용→출처→다음 형제, 다음 형제가 없을 때 어떻게 되는지)

실행: uv run python tests/inspect_quote_close4.py
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

_JS = r"""
(els) => els.map((e, i) => ({
  i,
  cls: (e.className || '').toString().slice(0, 100),
  text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 80),
}))
"""


async def dump(label: str, frame) -> list:
    comps = await frame.locator(".se-component").evaluate_all(_JS)
    print(f"\n=== {label} ({len(comps)}개) ===")
    for c in comps:
        print(c)
    return comps


async def wait_stable_count(frame, label: str) -> int:
    """컴포넌트 개수가 500ms 간격으로 2번 연속 같으면 안정된 것으로 본다(최대 5초)."""
    prev = -1
    for _ in range(10):
        count = await frame.locator(".se-component").count()
        if count == prev:
            print(f"[{label}] 컴포넌트 수 안정화: {count}개")
            return count
        prev = count
        await asyncio.sleep(0.5)
    print(f"[{label}] 안정화 확인 실패(마지막 값 {prev}개로 진행)")
    return prev


async def insert_quote(frame, content_text: str) -> None:
    await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
    await asyncio.sleep(0.6)
    style_option = frame.locator(sel.QUOTE_STYLE_CORNER_CSS).first
    if await is_visible(style_option, timeout=2000):
        await style_option.click(timeout=8000)
    else:
        print(">>> 꺾쇠 스타일 옵션을 못 찾음 — 기본 인용구로 폴백")
        await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
    await asyncio.sleep(0.5)


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()
        await _ensure_write_page(page)
        frame = page.frame_locator(sel.MAIN_FRAME)

        await wait_and_dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)

        # 컴포넌트 개수가 안정될 때까지 대기(초안 로딩 레이스 방지)
        await wait_stable_count(frame, "초기 로딩")

        last_component = frame.locator(".se-component").last
        await last_component.click(timeout=8000)
        await page.keyboard.press("Control+End")
        await asyncio.sleep(0.3)

        base_count = await wait_stable_count(frame, "Control+End 후")
        await dump("시작 상태(문서 끝)", frame)

        await wait_and_dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)

        # ── 후보 A: 인용구 삽입(진짜 끝) → 내용 입력 → ArrowDown 1회(출처 필드) → Enter ──
        await insert_quote(frame, "A후보 내용")
        await paste_into_focused(page, "A후보 내용")
        await asyncio.sleep(0.3)
        await dump("A-0) 인용구 삽입+내용 입력 (문서 끝)", frame)

        await page.keyboard.press("ArrowDown")  # 내용 -> 출처 필드
        await asyncio.sleep(0.2)
        await page.keyboard.press("Enter")
        await paste_into_focused(page, "MARKER-A-ENTER")
        await asyncio.sleep(0.3)
        after_a = await dump("A-1) ArrowDown 1회(출처 필드) + Enter + MARKER-A-ENTER", frame)

        # ── 후보 B: 새 인용구를 다시 "진짜 끝"에 삽입 → ArrowDown 2회 ──
        last_component = frame.locator(".se-component").last
        await last_component.click(timeout=8000)
        await page.keyboard.press("Control+End")
        await asyncio.sleep(0.3)
        await wait_stable_count(frame, "B 준비 — Control+End 후")

        await wait_and_dismiss_continue_draft_popup(page)
        await dismiss_cascading_alerts(page, frame)

        await insert_quote(frame, "B후보 내용")
        await paste_into_focused(page, "B후보 내용")
        await asyncio.sleep(0.3)
        await dump("B-0) 새 인용구 삽입+내용 입력 (문서 끝)", frame)

        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(0.2)
        await page.keyboard.press("ArrowDown")
        await asyncio.sleep(0.2)
        await paste_into_focused(page, "MARKER-B-DOWN2")
        await asyncio.sleep(0.3)
        await dump("B-1) ArrowDown 2회 + MARKER-B-DOWN2", frame)

        print(
            "\n>>> A-1에서 MARKER-A-ENTER가 인용구(se-quotation) 밖 새 컴포넌트에 "
            "나타나는지, B-1에서 MARKER-B-DOWN2가 새 컴포넌트로 나타나는지(문서 끝이라 "
            "형제가 없으므로 새로 생겼는지, 아니면 안 움직였는지) 확인하세요."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
