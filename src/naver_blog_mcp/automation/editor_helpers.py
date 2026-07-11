"""스마트에디터 ONE 상호작용 헬퍼.

postToNaver.ts(naver-blog-writer)에서 실계정으로 ~15회 검증된 팝업 방어/
클릭 재시도/클립보드 붙여넣기 로직을 Playwright async로 이식한 모듈.
"""

import logging

from playwright.async_api import Page, FrameLocator, Locator

logger = logging.getLogger(__name__)


async def is_visible(locator: Locator, timeout: int = 1500) -> bool:
    """Playwright Python의 Locator.is_visible()는 timeout을 받지 않으므로,
    wait_for(state="visible")를 try/except로 감싸 timeout 있는 가시성 확인을 제공한다."""
    try:
        await locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


async def paste_into_focused(page: Page, text: str) -> None:
    """현재 포커스된 요소에 클립보드로 text를 붙여넣는다."""
    await page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    await page.keyboard.press("Control+V")


async def dismiss_popup_button(scope, name: str) -> bool:
    """scope(page 또는 frame)에서 정확히 name인 버튼을 찾으면 클릭하고 True."""
    button = scope.get_by_role("button", name=name, exact=True).first
    if await is_visible(button, timeout=1500):
        await button.click()
        return True
    return False


async def dismiss_continue_draft_popup(page: Page) -> None:
    """"이어서 작성" 팝업의 취소를 눌러 새 글로 시작. 이 팝업은 #mainFrame 밖(page 최상단)에 뜬다."""
    if await dismiss_popup_button(page, "취소"):
        return
    by_text = page.get_by_text("취소", exact=True).first
    if await is_visible(by_text, timeout=2000):
        await by_text.click()


async def dismiss_cascading_alerts(page: Page, frame: FrameLocator) -> None:
    """se-popup-alert-confirm류 연쇄 "확인" 팝업을 page/frame 양쪽에서 더 없을 때까지 정리."""
    for _ in range(3):
        dismissed_page = await dismiss_popup_button(page, "확인")
        dismissed_frame = await dismiss_popup_button(frame, "확인")
        if not dismissed_page and not dismissed_frame:
            return
        await page.wait_for_timeout(300)


async def dismiss_help_panel(page: Page, frame: FrameLocator) -> None:
    """저장 버튼을 가릴 수 있는 도움말 사이드 패널을 닫기 버튼→Escape 순으로 닫는다."""
    help_title = frame.locator(".se-help-title").first
    if not await is_visible(help_title, timeout=2000):
        return
    close_button = frame.get_by_role("button", name="닫기").first
    if await is_visible(close_button, timeout=2000):
        await close_button.click()
        return
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass


async def click_resilient(page: Page, frame: FrameLocator, locator: Locator) -> None:
    """클릭이 팝업에 막히면 팝업을 정리하고 한 번 더 시도한다."""
    try:
        await locator.click(timeout=8000)
        return
    except Exception:
        await dismiss_cascading_alerts(page, frame)
        await locator.click(timeout=30000)


async def clear_and_focus(page: Page, frame: FrameLocator, field: Locator) -> None:
    """필드를 클릭→전체선택→삭제→재클릭. 지운 직후 붙여넣기가 씹히는 문제를 재포커스로 방지."""
    await click_resilient(page, frame, field)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await click_resilient(page, frame, field)
