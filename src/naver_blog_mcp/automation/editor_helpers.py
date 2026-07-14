"""스마트에디터 ONE 상호작용 헬퍼.

postToNaver.ts(naver-blog-writer)에서 실계정으로 ~15회 검증된 팝업 방어/
클릭 재시도/클립보드 붙여넣기 로직을 Playwright async로 이식한 모듈.
"""

import asyncio
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


async def dismiss_continue_draft_popup(page: Page, frame: FrameLocator | None = None) -> bool:
    """"이어서 작성" 팝업의 취소를 눌러 새 글로 시작(이어쓰기를 절대 선택하지 않는다).

    이 팝업은 se-popup-alert-confirm 클래스로, page 최상단에 뜨는 경우와 #mainFrame
    "안"에 뜨는 경우가 둘 다 있음이 실계정에서 확인됐다(전에는 page 밖에만 뜬다고
    가정했으나 "작성 중인 글이 있습니다" 변형은 #mainFrame 안에서 뜬다 —
    tests/inspect_continue_draft2.py 라이브 확인). frame이 주어지면 두 스코프를
    순서대로 검사한다. 이게 안 되면 dismiss_cascading_alerts가 이 팝업의 "확인"
    버튼을 먼저 찾아 클릭해버려(이어쓰기 = 이전 글 덮어쓰기) 취소가 무의미해진다.

    취소를 클릭한 뒤에는 팝업이 실제로 사라졌는지 확인해, 클릭이 씹혀 "이어쓰기"
    상태로 남는 일을 방지한다.

    Returns: 팝업을 발견해 취소를 클릭했고 실제로 닫힌 게 확인되면 True, 애초에
    팝업이 없었거나 재시도해도 안 닫히면 False. (재시도 후에도 안 닫혔는데 True를
    반환하던 이전 버전의 버그를 수정 — 호출자가 실패를 실패로 알아야 한다.)"""
    scopes = [page] if frame is None else [page, frame]
    for scope in scopes:
        clicked = await dismiss_popup_button(scope, "취소")
        if clicked:
            button = scope.get_by_role("button", name="취소", exact=True).first
        else:
            by_text = scope.get_by_text("취소", exact=True).first
            if await is_visible(by_text, timeout=2000):
                await by_text.click()
                button = by_text
                clicked = True
        if not clicked:
            continue
        # 취소 클릭 후 팝업이 실제로 닫혔는지 확인(안 닫혔으면 한 번 더 시도)
        if await is_visible(button, timeout=1500):
            logger.warning("'이어서 작성' 팝업의 취소 클릭이 반영되지 않아 재시도합니다.")
            try:
                await button.click()
            except Exception:
                pass
            if await is_visible(button, timeout=1000):
                logger.error("'이어서 작성' 팝업의 취소 클릭이 재시도 후에도 실패했습니다.")
                return False
        return True
    return False


async def wait_and_dismiss_continue_draft_popup(
    page: Page, frame: FrameLocator | None = None, timeout_ms: int = 8000
) -> bool:
    """dismiss_continue_draft_popup을 짧은 간격으로 반복 호출해, 네비게이션 직후
    "이어서 작성" 팝업이 늦게 렌더링되는 경우까지 폭넓게 잡아낸다.

    dismiss_continue_draft_popup 자체는, 팝업이 "없을" 때 없는 버튼이 나타나길
    타임아웃까지 기다리느라 한 번 호출에 ~7초(page/frame 두 스코프 × 각 is_visible
    타임아웃)가 걸린다. 방금 수동 로그인을 마친 직후처럼 페이지가 콜드 상태면 팝업이
    늦게 뜨는 경우가 실계정에서 확인됐다(취소를 못 누르고 그대로 "이어쓰기" 상태로
    진행돼 이전 임시저장 글을 덮어씀). 이 함수는 전체 예산(timeout_ms) 안에서
    재확인해, 늦게 뜬 팝업도 놓치지 않는다.

    NOTE(성능 버그 수정): 이전 구현은 `timeout_ms // 500`으로 "고정 횟수"(8000이면
    16회)를 돌았는데, 한 번 확인이 ~0.5초라고 가정한 것이다. 실제로는 팝업이 없을 때
    한 번에 ~7초가 걸려, 8초 예산이 아니라 100초 넘게 도는 경우가 있었다(리로드 후
    "팝업 없음"을 확정하는 구간에서 사용자가 긴 지연을 겪음). 경과 시간(벽시계) 기준
    예산으로 바꿔 주석의 의도대로 실제 timeout_ms 안에서 끝나게 한다. 개별 타임아웃은
    그대로라 팝업을 놓칠 위험은 없다.

    Returns: 팝업을 발견해 취소했으면 True, 예산 안에 끝내 안 뜨면 False."""
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    while True:
        if await dismiss_continue_draft_popup(page, frame):
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await page.wait_for_timeout(500)


async def dismiss_cascading_alerts(page: Page, frame: FrameLocator) -> None:
    """se-popup-alert-confirm류 연쇄 "확인" 팝업을 page/frame 양쪽에서 더 없을 때까지 정리."""
    for _ in range(3):
        dismissed_page = await dismiss_popup_button(page, "확인")
        dismissed_frame = await dismiss_popup_button(frame, "확인")
        if not dismissed_page and not dismissed_frame:
            return
        await page.wait_for_timeout(300)


async def dismiss_help_panel(page: Page, frame: FrameLocator) -> None:
    """저장 버튼을 가릴 수 있는 도움말 사이드 패널을 닫는다.

    도움말 헤더(se-help-header)가 닫기 버튼 위에 겹쳐 포인터 이벤트를 가로채므로
    일반 click()은 30초간 재시도만 하다 실패한다(실계정 확인). 그래서 닫기 버튼에
    click 이벤트를 직접 디스패치해 가로채기를 우회하고, Escape도 함께 시도한다.
    닫지 못하더라도 여기서 멈추지 않고(예외 없이) 반환해 저장 시도로 넘어간다."""
    help_title = frame.locator(".se-help-title").first
    if not await is_visible(help_title, timeout=2000):
        return
    close_button = frame.get_by_role("button", name="닫기").first
    for _ in range(3):
        try:
            if await is_visible(close_button, timeout=1000):
                # 포인터 가로채기를 우회하려 좌표 클릭 대신 click 이벤트를 직접 발사한다.
                await close_button.dispatch_event("click")
        except Exception:
            pass
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        if not await is_visible(help_title, timeout=1000):
            return


async def click_resilient(page: Page, frame: FrameLocator, locator: Locator) -> None:
    """클릭이 팝업에 막히면 그때 떠 있는 팝업을 닫고 재시도한다.

    "이어서 작성"(취소)·연쇄 "확인" 팝업은 예측 불가한 시점에 0~여러 번 뜰 수 있어
    한 번 닫는 것으로는 부족하다. 클릭이 막힐 때마다 팝업을 정리하고 여러 번 재시도한다."""
    last_err: Exception | None = None
    for _ in range(4):
        try:
            await locator.click(timeout=8000)
            return
        except Exception as e:
            last_err = e
            await dismiss_continue_draft_popup(page)
            await dismiss_cascading_alerts(page, frame)
    if last_err is not None:
        raise last_err


async def clear_and_focus(page: Page, frame: FrameLocator, field: Locator) -> None:
    """필드를 클릭→전체선택→삭제→재클릭. 지운 직후 붙여넣기가 씹히는 문제를 재포커스로 방지."""
    await click_resilient(page, frame, field)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await click_resilient(page, frame, field)
