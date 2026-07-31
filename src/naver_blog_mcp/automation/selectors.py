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
        # 네이버가 패스키/QR 로그인을 추가하며 버튼 구조를 바꿈(2026-07-21 실계정으로 확인:
        # .btn_login, button[type='submit']는 더 이상 없음). 반응형 레이아웃별로
        # #loginBtn_column / #loginBtn_row 둘 중 보이는 쪽이 실제 로그인 버튼.
        "login_btn": ["#loginBtn_column", "#loginBtn_row", ".btn_login", "button[type='submit']"],
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
# 인용구4(밑줄 스타일) — 소제목용. 6개 옵션 전부 라이브 확인(tests/inspect_quote_style4.py):
# 인용구1=default, 인용구2=quotation_line, 인용구3=quotation_bubble,
# 인용구4=quotation_underline, 인용구5=quotation_postit, 인용구6=quotation_corner.
QUOTE_STYLE_UNDERLINE_CSS = ".se-toolbar-option-insert-quotation-quotation_underline-button"

# 이미지 정렬/크기 — 삽입된 이미지를 선택하면 뜨는 속성 툴바(라이브 DOM 확정:
# tests/inspect_image_toolbar.py). 속성 툴바와 컨텍스트 툴바에 같은 버튼이 중복
# 존재할 수 있어(둘 다 동일 동작) 호출부에서 .first로 집는다.
# 가운데 정렬 (data-name='align', data-value='center', 유일 클래스).
IMAGE_ALIGN_CENTER_CSS = ".se-align-center-toolbar-button"
# '크기 변경' 레이어 — 열기 버튼 + 너비/높이 px 입력 + 적용(확인) 버튼
# (라이브 확정: tests/inspect_image_resize_layer.py). 프리셋이 아니라 px 직접 입력이라
# 문서 너비의 정확한 비율(예: 1/2)로 지정할 수 있다. 입력창은 title로 구분(W/H 동일 클래스).
IMAGE_RESIZE_OPEN_CSS = ".se-resizing-toolbar-button"
IMAGE_RESIZE_WIDTH_INPUT = "input[title='너비']"
IMAGE_RESIZE_HEIGHT_INPUT = "input[title='높이']"
IMAGE_RESIZE_APPLY_CSS = ".se-custom-layer-resizing-apply-button"
# '모든사진 적용' 체크박스 — 체크돼 있으면 한 이미지 리사이즈가 전체에 적용돼, 일괄
# 처리 중 이미 줄인 이미지를 또 기준 삼아 연쇄 축소되는 사고가 난다. 각 이미지를
# 독립적으로 1/2로 맞추기 위해 해제한다.
IMAGE_RESIZE_ALL_CHECKBOX = ".se-custom-layer-resizing-checkbox"

# 텍스트 서식(볼드/폰트크기) — 텍스트를 "선택"해야 뜨는 컨텐츠 툴바에 있다
# (캐럿만 있으면 안 보임; 라이브 확정: tests/inspect_text_format_apply2.py,
# inspect_bold_word.py). 볼드는 선택한 부분에만 적용되고 상속되지 않음(문단마다
# 별도 적용 필요).
BOLD_TOOLBAR_CSS = ".se-bold-toolbar-button"
# 폰트 크기는 자유 입력이 아니라 고정 프리셋 드롭다운이다(11/13/15/16/19/24/28/30/34/38).
FONT_SIZE_OPEN_CSS = ".se-font-size-code-toolbar-button"
FONT_SIZE_24_CSS = ".se-toolbar-option-font-size-code-fs24-button"

# 정렬(가운데) — 캐럿만 있어도(텍스트 선택 없이) 뜨는 "정렬 열기" 드롭다운
# (라이브 확정: tests/inspect_align_before_typing.py). 본문 작성 시작 전(빈 문단)
# 딱 한 번만 걸면 되고, 인용구/구분선을 사이에 둬도 계속 상속됨이 확인됐다
# (인용구 자체는 정렬 대상에서 제외됨). "텍스트 선택"이 있어야만 뜨는 컨텐츠
# 툴바 버튼(.se-align-center-toolbar-button, 이미지 정렬과 동일 클래스라
# IMAGE_ALIGN_CENTER_CSS로 그쪽엔 여전히 씀)을 텍스트에도 쓰려 했으나, "문장마다
# 줄바꿈" 지시로 텍스트 블록 하나가 여러 문단으로 쪼개지면서 트레일링 빈 줄을
# 짚어 실패하는 문제가 있어 이 방식으로 교체했다.
TEXT_ALIGN_OPEN_CSS = "[data-name='align-drop-down-with-justify']"
TEXT_ALIGN_CENTER_OPTION_CSS = ".se-toolbar-option-align-center-button"
