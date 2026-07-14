""""이어서 작성" 팝업 취소 + 페이지 리로드가 실제로 깨끗한 새 에디터를 만드는지 확인.

실제 전송 흐름에서 재현된 문제: 팝업이 뜨고 "취소"를 누른 것 같은데, 화면에는
이전 글 내용이 남아있고 결국 그 위에 덮어써졌다. _ensure_fresh_editor는
"취소 후 페이지를 다시 불러오면 깨끗해진다"는 가정으로 최대 3번 반복하는데,
이 가정 자체가 틀렸을 수 있다(리로드해도 네이버가 서버에 남아있는 같은
임시저장 draft를 계속 다시 제안할 수 있음 — 그러면 3번을 반복해도 절대
안 끝나고, 마지막엔 검증 없이 그냥 진행됨).

실행: uv run python tests/inspect_continue_draft.py
동작: 글쓰기 페이지에 처음 진입 → 팝업이 뜨는지, 뜬다면 그 안의 제목/전체
      텍스트를 덤프 → "취소" 클릭 → 그 직후 제목 필드 내용 덤프(취소만으로
      내용이 지워지는지) → 페이지 리로드 → 팝업이 또 뜨는지, 제목이 여전히
      이전 값인지 반복 확인(최대 4라운드).
"""

import asyncio

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.automation import selectors as sel
from naver_blog_mcp.automation.editor_helpers import is_visible

_POPUP_JS = r"""
() => {
  const dialogs = Array.from(document.querySelectorAll("[class*='popup'], [role='dialog'], [role='alertdialog']"))
    .filter(e => e.offsetParent !== null);
  return dialogs.map(e => ({
    cls: (e.className || '').toString().slice(0, 120),
    text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 150),
  }));
}
"""


async def dump_state(label: str, page) -> None:
    popups = await page.evaluate(_POPUP_JS)
    print(f"\n--- {label} ---")
    print(f"page.url = {page.url}")
    print(f"보이는 팝업류 {len(popups)}개:")
    for p in popups:
        print(" ", p)

    try:
        frame = page.frame_locator(sel.MAIN_FRAME)
        title_locator = frame.locator(sel.TITLE_PARAGRAPH).first
        if await is_visible(title_locator, timeout=1500):
            title_text = await title_locator.text_content()
            print(f"제목 필드 내용: {title_text!r}")
        else:
            print("제목 필드: 안 보임")
        comp_count = await frame.locator(".se-component").count()
        print(f"현재 .se-component 개수: {comp_count}")
    except Exception as e:
        print(f"본문 프레임 접근 실패: {e}")


async def try_cancel(page) -> bool:
    """"취소" 버튼을 찾아 클릭. 클릭했으면 True."""
    button = page.get_by_role("button", name="취소", exact=True).first
    if await is_visible(button, timeout=3000):
        await button.click()
        return True
    by_text = page.get_by_text("취소", exact=True).first
    if await is_visible(by_text, timeout=2000):
        await by_text.click()
        return True
    return False


async def main():
    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()

        for round_i in range(1, 5):
            await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            await dump_state(f"라운드 {round_i} — 페이지 진입 직후", page)

            clicked = await try_cancel(page)
            print(f"'취소' 클릭 시도 결과: {clicked}")
            await page.wait_for_timeout(1000)
            await dump_state(f"라운드 {round_i} — '취소' 클릭 직후(리로드 전)", page)

        print(
            "\n>>> 매 라운드 진입 직후 팝업이 계속 뜨는지, '제목 필드 내용'이 매번 "
            "이전 라운드와 똑같이 남아있는지 확인하세요. 계속 같은 내용이 반복되면 "
            "'취소 후 리로드'가 절대 깨끗해지지 않는다는 뜻입니다."
        )
    finally:
        input("\n확인 후 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
