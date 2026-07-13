"""네이버 블로그 DOM 셀렉터 정의.

네이버 UI 변경에 대응하기 위해 대체 셀렉터를 리스트로 관리합니다.
"""

from typing import List, Union

# 타입 정의
Selector = Union[str, List[str]]


class NaverSelectors:
    """네이버 블로그 셀렉터 클래스."""

    # 로그인 페이지
    LOGIN = {
        "id_input": "#id",
        "pw_input": "#pw",
        "login_btn": [".btn_login", "button[type='submit']"],
        "error_message": ".error_message",
    }

    # 블로그 메인
    BLOG_MAIN = {
        "profile": [".my_nick", ".profile_info"],
        "write_btn": ["a[href*='PostWriteForm']", ".write_btn"],
    }

    # 글쓰기 페이지
    POST_WRITE = {
        "title_input": [
            "div[contenteditable='true'][data-placeholder='제목']",  # 스마트에디터 ONE
            "div[contenteditable='true']:has-text('제목')",
            "input[placeholder*='제목']",
            "#title",
            ".se-title-input",
        ],
        "content_frame": ["iframe.se-iframe", "iframe#mainFrame"],
        "content_body": [
            "div[contenteditable='true']",  # 일반 contenteditable
            ".se-component-content",
            ".se-text-paragraph",
        ],
        "category_select": [".blog2_series", "select[name='category']"],
        "tag_input": ["input[placeholder*='태그']", ".tag_input"],
        "publish_btn": [
            "button:has-text('발행')",
            ".publish_btn",
            "button[type='submit']",
        ],
        "temp_save_btn": ["button:has-text('임시저장')", ".temp_save_btn"],
        "image_upload_btn": [
            "button[aria-label='사진']",
            ".image_upload",
            "button:has-text('사진')",
        ],
    }

    # 글 보기 페이지
    POST_VIEW = {
        "post_url_pattern": "**/PostView.naver*",
        "edit_btn": ["a:has-text('수정')", ".edit_btn"],
        "delete_btn": ["a:has-text('삭제')", ".delete_btn"],
    }

    @classmethod
    def get_selector(cls, category: str, key: str) -> Selector:
        """
        카테고리와 키로 셀렉터 가져오기.

        Args:
            category: 셀렉터 카테고리 (LOGIN, BLOG_MAIN, POST_WRITE, POST_VIEW)
            key: 셀렉터 키

        Returns:
            셀렉터 문자열 또는 대체 셀렉터 리스트

        Raises:
            KeyError: 존재하지 않는 카테고리나 키
        """
        category_dict = getattr(cls, category, None)
        if category_dict is None:
            raise KeyError(f"존재하지 않는 카테고리: {category}")

        selector = category_dict.get(key)
        if selector is None:
            raise KeyError(f"존재하지 않는 셀렉터 키: {key}")

        return selector


# 편의를 위한 상수
LOGIN_ID_INPUT = NaverSelectors.LOGIN["id_input"]
LOGIN_PW_INPUT = NaverSelectors.LOGIN["pw_input"]
LOGIN_BTN = NaverSelectors.LOGIN["login_btn"]

# 글쓰기 관련 상수
POST_WRITE_TITLE = NaverSelectors.POST_WRITE["title_input"]
POST_WRITE_CONTENT_FRAME = NaverSelectors.POST_WRITE["content_frame"]
POST_WRITE_CONTENT_BODY = NaverSelectors.POST_WRITE["content_body"]
POST_WRITE_PUBLISH_BTN = NaverSelectors.POST_WRITE["publish_btn"]
POST_WRITE_CATEGORY_BTN = NaverSelectors.POST_WRITE["category_select"]
POST_WRITE_TAG_INPUT = NaverSelectors.POST_WRITE["tag_input"]

# ── postToNaver.ts에서 실계정 검증된 셀렉터 (스마트에디터 ONE) ──────────────
MAIN_FRAME = "#mainFrame"
TITLE_PARAGRAPH = ".se-title-text .se-text-paragraph"
BODY_FIRST_PARAGRAPH = ".se-component.se-text .se-text-paragraph"
SAVE_DRAFT_BTN_NAME = "저장"   # role=button, 임시저장
PHOTO_BTN_NAME = "사진"        # role=button, 이미지 삽입
HELP_TITLE = ".se-help-title"  # 저장 버튼을 가릴 수 있는 도움말 패널
GO_BLOG_WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"

# 구분선(수평선) — 스마트에디터 ONE 툴바 버튼(라이브 확정).
# 툴바에 "구분선 추가"(기본 삽입, data-value=default)와 "구분선 선택"(스타일 드롭다운)
# 두 버튼이 있어 name="구분선"은 strict 위반이 난다. 기본 삽입 버튼만 정확히 지정한다.
# role 이름("구분선 추가"/"구분선 선택")은 충돌 위험이 있어 유일한 CSS 클래스로 지정한다.
# 기본(구분선1) 삽입 버튼 (라이브 DOM 확인: data-value=default, data-log=dot.horizt).
DIVIDER_BTN_CSS = ".se-insert-horizontal-line-default-toolbar-button"
# 구분선2 스타일을 쓰려면 "구분선 선택" 드롭다운을 열고 2번째 스타일을 고른다.
# 드롭다운 버튼(라이브 DOM 확인): aria-haspopup, data-name='horizontal-line'.
DIVIDER_SELECT_BTN_CSS = ".se-document-toolbar-select-option-button[data-name='horizontal-line']"
# 드롭다운 팝업 안 "구분선 2" 옵션 (라이브 DOM 확인: text='구분선 2', data-value='line1',
# 유일 CSS 클래스). 참고로 '구분선 1'=default, '구분선 3'=line2 … 순.
DIVIDER_STYLE2_CSS = ".se-toolbar-option-insert-horizontal-line-line1-button"

# 인용구 — 구분선과 동일한 툴바 패턴(기본 삽입 버튼 + "인용구 선택" 스타일 드롭다운).
# 기본 삽입 버튼/드롭다운 버튼 클래스는 라이브 DOM 덤프(tests/inspect_quote_popup.py)로
# 확인됨: "se-document-toolbar-icon-select-button se-insert-quotation-default-toolbar-button ..."
# / data-name='quotation'.
QUOTE_BTN_CSS = ".se-insert-quotation-default-toolbar-button"
QUOTE_SELECT_BTN_CSS = ".se-document-toolbar-select-option-button[data-name='quotation']"
# 원하는 꺾쇠(모서리 브라켓) 스타일 옵션 (라이브 DOM 확인: tests/inspect_quote_popup.py).
# 드롭다운 옵션의 실제 버튼 텍스트는 "인용구 1"~"인용구 6"이라 화면에 보이는 스타일
# 이름("따옴표/버티컬 라인/말풍선/라인&따옴표/포스트잇/프레임")으로는 못 찾는다
# (텍스트 매칭이 항상 실패해 기본 스타일로 폴백되던 원인). 실제 구분값은
# data-value='quotation_corner' (6번째 옵션, 유일 CSS 클래스).
QUOTE_STYLE_CORNER_CSS = ".se-toolbar-option-insert-quotation-quotation_corner-button"
