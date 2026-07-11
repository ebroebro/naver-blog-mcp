import inspect

from naver_blog_mcp.automation import editor_helpers as eh
from naver_blog_mcp.automation import selectors as sel


def test_helpers_are_async_callables():
    for name in [
        "is_visible", "paste_into_focused", "dismiss_popup_button",
        "dismiss_continue_draft_popup", "dismiss_cascading_alerts",
        "dismiss_help_panel", "click_resilient", "clear_and_focus",
    ]:
        fn = getattr(eh, name)
        assert inspect.iscoroutinefunction(fn), f"{name} must be async"


def test_verified_selectors_present():
    assert sel.MAIN_FRAME == "#mainFrame"
    assert sel.TITLE_PARAGRAPH == ".se-title-text .se-text-paragraph"
    assert sel.BODY_FIRST_PARAGRAPH == ".se-component.se-text .se-text-paragraph"
    assert sel.SAVE_DRAFT_BTN_NAME == "저장"
    assert sel.PHOTO_BTN_NAME == "사진"
