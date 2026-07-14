""""이어서 작성" 팝업 취소 수정 검증: dismiss_continue_draft_popup(page, frame)이
#mainFrame 안에 뜨는 변형("작성 중인 글이 있습니다")도 실제로 닫는지 확인한다.

이전 라운드에서 확인된 사실:
- 이 팝업(se-popup-alert-confirm)은 #mainFrame 안에서 뜬다(page 최상단이 아님).
- 기존 dismiss_continue_draft_popup(page)는 page 스코프만 봐서 이 변형을 못 찾고
  조용히 "팝업 없음"으로 오판 → 뒤이어 dismiss_cascading_alerts가 같은 팝업의
  "확인"(이어쓰기) 버튼을 먼저 클릭해버려 이전 글을 덮어쓰는 사고로 이어졌다.

수정본은 dismiss_continue_draft_popup(page, frame)처럼 frame도 받아 두 스코프를
검사한다. 이 스크립트는 그 수정이 실제로 통하는지 검증한다.

실행: uv run python tests/inspect_continue_draft2.py
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.editor_helpers import is_visible, dismiss_continue_draft_popup

_BUTTON_DUMP_JS = r"""
(name) => {
  const all = Array.from(document.querySelectorAll("button, [role='button']"));
  return all
    .filter(e => (e.textContent || '').trim() === name || e.getAttribute('aria-label') === name)
    .map(e => ({
      visible: e.offsetParent !== null,
      text: (e.textContent || '').trim().slice(0, 20),
      cls: (e.className || '').toString().slice(0, 80),
    }));
}
"""


async def dump_cancel_buttons(label: str, page, frame) -> None:
    top = await page.evaluate(_BUTTON_DUMP_JS, "취소")
    print(f"\n[{label}] page 최상단 '취소' 버튼 {len(top)}개:")
    for r in top:
        print(" ", r)
    try:
        in_frame = await frame.locator(".se-popup-alert-confirm").evaluate_all(
            "(els) => els.map(e => ({visible: e.offsetParent !== null, "
            "text: (e.textContent||'').replace(/\\s+/g,' ').trim().slice(0,120)}))"
        )
        print(f"[{label}] frame 안 se-popup-alert-confirm {len(in_frame)}개:")
        for r in in_frame:
            print(" ", r)
    except Exception as e:
        print(f"[{label}] frame 조회 실패: {e}")


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()

        await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        frame = page.frame_locator(sel.MAIN_FRAME)
        print(f"1) 진입 직후 url={page.url}")
        await dump_cancel_buttons("진입 직후", page, frame)

        print("\n2) dismiss_continue_draft_popup(page, frame) 호출...")
        dismissed = await dismiss_continue_draft_popup(page, frame)
        print(f"반환값: {dismissed}")
        await page.wait_for_timeout(1000)
        await dump_cancel_buttons("취소 클릭 시도 후", page, frame)

        title_locator = frame.locator(sel.TITLE_PARAGRAPH).first
        try:
            await title_locator.click(timeout=8000)
            print("\n3) 제목 필드 클릭 성공(팝업이 더 이상 클릭을 막지 않음)")
            title_text = await title_locator.text_content()
            print(f"현재 제목 필드 내용: {title_text!r}")
        except Exception as e:
            print(f"\n3) 제목 필드 클릭 실패(팝업이 여전히 막고 있을 수 있음): {e}")

        print(
            "\n>>> 2)에서 반환값이 True이고, 3)에서 제목 필드 클릭이 성공했으면 "
            "수정이 통한 것입니다. frame 안 se-popup-alert-confirm 개수가 취소 후 "
            "0개가 됐는지도 확인하세요."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
