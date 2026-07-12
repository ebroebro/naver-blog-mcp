"""네이버 블로그 글쓰기 자동화."""

import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .selectors import (
    POST_WRITE_TITLE,
    POST_WRITE_CONTENT_FRAME,
    POST_WRITE_CONTENT_BODY,
    POST_WRITE_PUBLISH_BTN,
    POST_WRITE_CATEGORY_BTN,
    POST_WRITE_TAG_INPUT,
)

from . import selectors as sel
from .editor_helpers import (
    is_visible,
    paste_into_focused,
    dismiss_continue_draft_popup,
    wait_and_dismiss_continue_draft_popup,
    dismiss_cascading_alerts,
    dismiss_help_panel,
    click_resilient,
    clear_and_focus,
)


logger = logging.getLogger(__name__)


class NaverBlogPostError(Exception):
    """네이버 블로그 글쓰기 관련 에러."""

    pass


async def navigate_to_post_write_page(
    page: Page, blog_id: Optional[str] = None, timeout: int = 30000
) -> None:
    """
    네이버 블로그 글쓰기 페이지로 이동합니다.

    Args:
        page: Playwright Page 객체
        blog_id: 블로그 ID (옵션, 없으면 자동으로 현재 로그인된 블로그 사용)
        timeout: 페이지 로딩 대기 시간 (ms)

    Raises:
        NaverBlogPostError: 페이지 이동 실패 시
    """
    try:
        # 방법 1: blog_id가 주어진 경우
        if blog_id:
            url = f"https://blog.naver.com/{blog_id}/postwrite"
        else:
            # 방법 2: 블로그 메인에서 글쓰기 버튼 찾아서 클릭
            # 먼저 블로그 메인으로 이동
            await page.goto("https://blog.naver.com", wait_until="load", timeout=timeout)
            await asyncio.sleep(2)

            # 글쓰기 버튼 찾기 (여러 셀렉터 시도)
            write_btn_selectors = [
                "a[href*='postwrite']",
                "a:has-text('글쓰기')",
                "button:has-text('글쓰기')",
            ]

            write_btn_found = False
            for selector in write_btn_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    # href 가져오기
                    element = page.locator(selector).first
                    href = await element.get_attribute("href")
                    if href:
                        # 절대 URL로 변환
                        if href.startswith("/"):
                            url = f"https://blog.naver.com{href}"
                        elif href.startswith("http"):
                            url = href
                        else:
                            url = f"https://blog.naver.com/{href}"
                        write_btn_found = True
                        print(f"   글쓰기 버튼 발견: {url}")
                        break

            if not write_btn_found:
                # 기본 URL 사용
                url = "https://blog.naver.com/postwrite"
                print(f"   글쓰기 버튼을 찾지 못했습니다. 기본 URL 사용: {url}")

        await page.goto(url, wait_until="load", timeout=timeout)
        await asyncio.sleep(3)  # 에디터 로딩 충분히 대기

        # 글쓰기 페이지인지 확인
        current_url = page.url
        print(f"   현재 URL: {current_url}")

        # URL에 postwrite, PostWriteForm, Redirect=Write가 포함되어 있으면 성공으로 간주
        if ("postwrite" in current_url.lower() or
            "PostWriteForm" in current_url or
            "Redirect=Write" in current_url):
            logger.info(f"글쓰기 페이지로 이동: {current_url}")
            return

        # 제목 입력란 확인 (추가 검증)
        title_input_exists = False
        if isinstance(POST_WRITE_TITLE, list):
            for selector in POST_WRITE_TITLE:
                count = await page.locator(selector).count()
                if count > 0:
                    title_input_exists = True
                    print(f"   제목 입력란 발견: {selector}")
                    break
        else:
            count = await page.locator(POST_WRITE_TITLE).count()
            title_input_exists = count > 0

        if title_input_exists:
            logger.info(f"글쓰기 페이지로 이동: {url}")
            return

        raise NaverBlogPostError(f"글쓰기 페이지 로딩에 실패했습니다. 현재 URL: {current_url}")

    except PlaywrightTimeout as e:
        raise NaverBlogPostError(f"글쓰기 페이지 이동 시간 초과: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise NaverBlogPostError(f"글쓰기 페이지 이동 중 오류: {str(e)}")


async def fill_post_title(page: Page, title: str) -> None:
    """
    블로그 글 제목을 입력합니다.

    Args:
        page: Playwright Page 객체
        title: 글 제목

    Raises:
        NaverBlogPostError: 제목 입력 실패 시
    """
    try:
        # 제목 입력란 찾기 (대체 셀렉터 시도)
        title_filled = False

        # 방법 1: 일반적인 셀렉터 시도
        if isinstance(POST_WRITE_TITLE, list):
            for selector in POST_WRITE_TITLE:
                try:
                    element_count = await page.locator(selector).count()
                    if element_count > 0:
                        # contenteditable div는 fill 대신 type 사용
                        element = page.locator(selector).first

                        # contenteditable인지 확인
                        is_contenteditable = await element.get_attribute("contenteditable")

                        if is_contenteditable:
                            # contenteditable div: 클릭 후 타이핑
                            await element.click()
                            await asyncio.sleep(0.3)
                            await element.type(title, delay=50)
                        else:
                            # 일반 input: fill 사용
                            await element.fill(title)

                        title_filled = True
                        logger.info(f"제목 입력 완료: {title} (selector: {selector})")
                        break
                except Exception as e:
                    print(f"   셀렉터 {selector} 실패: {e}")
                    continue

        # 방법 2: 제목 영역을 직접 클릭 (좌표 기반)
        if not title_filled:
            try:
                # 제목 영역 대략적인 위치 클릭 (상단 중앙)
                await page.mouse.click(450, 250)
                await asyncio.sleep(0.5)
                await page.keyboard.type(title, delay=50)
                title_filled = True
                logger.info(f"제목 입력 완료 (클릭 방식): {title}")
            except Exception as e:
                print(f"   클릭 방식 실패: {e}")

        # 방법 3: Tab 키로 이동
        if not title_filled:
            try:
                # 페이지 최상단으로 포커스 이동 후 Tab으로 제목까지 이동
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.3)
                await page.keyboard.type(title, delay=50)
                title_filled = True
                logger.info(f"제목 입력 완료 (Tab 방식): {title}")
            except Exception as e:
                print(f"   Tab 방식 실패: {e}")

        if not title_filled:
            raise NaverBlogPostError("제목 입력란을 찾을 수 없습니다.")

        await asyncio.sleep(0.5)

    except Exception as e:
        raise NaverBlogPostError(f"제목 입력 중 오류: {str(e)}")


async def fill_post_content(page: Page, content: str, use_html: bool = False) -> None:
    """
    블로그 글 본문을 입력합니다.
    스마트에디터 ONE은 iframe 없이 직접 contenteditable을 사용합니다.

    Args:
        page: Playwright Page 객체
        content: 글 본문 내용
        use_html: HTML 모드로 입력할지 여부 (기본: False, 텍스트 모드)

    Raises:
        NaverBlogPostError: 본문 입력 실패 시
    """
    try:
        # 팝업이 있으면 먼저 닫기
        try:
            popup_selectors = [
                "button:has-text('확인')",
                "button:has-text('닫기')",
                "button.se-popup-button-confirm",
                ".se-popup-button-confirm",
            ]
            for popup_selector in popup_selectors:
                popup_count = await page.locator(popup_selector).count()
                if popup_count > 0:
                    await page.click(popup_selector, timeout=2000)
                    print(f"   팝업 닫기: {popup_selector}")
                    await asyncio.sleep(0.5)
                    break
        except Exception as e:
            print(f"   팝업 확인 실패 (무시): {e}")

        content_filled = False

        # 방법 1: iframe이 있는 경우 (구형 스마트에디터)
        iframe_selectors = POST_WRITE_CONTENT_FRAME if isinstance(POST_WRITE_CONTENT_FRAME, list) else [POST_WRITE_CONTENT_FRAME]

        for iframe_selector in iframe_selectors:
            try:
                iframe_count = await page.locator(iframe_selector).count()
                if iframe_count > 0:
                    print(f"   iframe 발견: {iframe_selector}")
                    frame_element = await page.wait_for_selector(iframe_selector, timeout=5000)
                    iframe_found = await frame_element.content_frame()

                    if iframe_found:
                        # iframe 내부 팝업 닫기
                        try:
                            iframe_popup_selectors = [
                                "button:has-text('확인')",
                                "button:has-text('닫기')",
                                ".se-popup-button-confirm",
                            ]
                            for popup_sel in iframe_popup_selectors:
                                popup_count = await iframe_found.locator(popup_sel).count()
                                if popup_count > 0:
                                    await iframe_found.locator(popup_sel).click(timeout=2000)
                                    print(f"   iframe 내부 팝업 닫기: {popup_sel}")
                                    await asyncio.sleep(0.5)
                                    break
                        except Exception as e:
                            print(f"   iframe 팝업 닫기 실패 (무시): {e}")

                        # iframe 내부에서 contenteditable 찾기
                        body_selectors = POST_WRITE_CONTENT_BODY if isinstance(POST_WRITE_CONTENT_BODY, list) else [POST_WRITE_CONTENT_BODY]

                        for body_selector in body_selectors:
                            try:
                                content_body = await iframe_found.wait_for_selector(body_selector, timeout=3000)
                                if content_body:
                                    await content_body.click()
                                    await asyncio.sleep(0.5)
                                    await content_body.type(content, delay=10)
                                    content_filled = True
                                    logger.info(f"본문 입력 완료 (iframe 방식, selector: {body_selector})")
                                    break
                            except Exception as e:
                                print(f"   iframe 내부 셀렉터 {body_selector} 실패: {e}")
                                continue

                        if content_filled:
                            # iframe에서 메인 페이지로 포커스 전환
                            await page.evaluate("() => { window.focus(); }")
                            await asyncio.sleep(0.5)
                            break
            except:
                continue

        # 방법 2: iframe 없이 직접 contenteditable (스마트에디터 ONE)
        if not content_filled:
            print("   iframe 없음, 직접 contenteditable 찾기 시도")

            # 본문 영역 찾기 - 여러 방법 시도
            content_selectors = [
                "div[contenteditable='true']:not([data-placeholder='제목'])",  # 제목이 아닌 contenteditable
                "div[contenteditable='true'][role='textbox']",
                "div.se-component",  # 스마트에디터 컴포넌트
                "div:has-text('글감과 함께')",  # 플레이스홀더 텍스트로 찾기
            ]

            for selector in content_selectors:
                try:
                    element_count = await page.locator(selector).count()
                    if element_count > 0:
                        element = page.locator(selector).first
                        await element.click()
                        await asyncio.sleep(0.5)

                        # 기존 플레이스홀더 텍스트 제거
                        await page.keyboard.press("Control+A")
                        await asyncio.sleep(0.2)

                        # 본문 입력
                        await page.keyboard.type(content, delay=10)
                        content_filled = True
                        logger.info(f"본문 입력 완료 (직접 방식, selector: {selector})")
                        break
                except Exception as e:
                    print(f"   셀렉터 {selector} 실패: {e}")
                    continue

        if not content_filled:
            raise NaverBlogPostError("본문 입력 영역을 찾을 수 없습니다.")

        await asyncio.sleep(1)

    except PlaywrightTimeout as e:
        raise NaverBlogPostError(f"본문 입력 시간 초과: {str(e)}")
    except Exception as e:
        raise NaverBlogPostError(f"본문 입력 중 오류: {str(e)}")


async def publish_post(
    page: Page, wait_for_completion: bool = True, timeout: int = 30000
) -> Dict[str, Any]:
    """
    블로그 글을 발행합니다.

    Args:
        page: Playwright Page 객체
        wait_for_completion: 발행 완료를 기다릴지 여부
        timeout: 발행 완료 대기 시간 (ms)

    Returns:
        발행 결과 딕셔너리
        {
            "success": bool,
            "message": str,
            "post_url": str (발행된 글 URL, 성공 시)
        }

    Raises:
        NaverBlogPostError: 발행 실패 시
    """
    try:
        # 0. 메인 페이지로 포커스 전환 (iframe에서 나오기)
        # 명시적으로 메인 페이지로 전환
        await page.bring_to_front()
        await page.evaluate("() => { if (window.parent) { window.parent.focus(); } window.focus(); }")
        await asyncio.sleep(1)

        # 페이지가 실제로 로드되었는지 확인
        print(f"   현재 URL: {page.url}")
        print(f"   페이지 타이틀: {await page.title()}")

        # 페이지 내 모든 팝업/모달 닫기 (도움말 팝업 등)
        try:
            # 도움말 팝업 닫기
            popup_close_selectors = [
                "button.se-popup-button-cancel",  # 취소 버튼
                "button:has-text('닫기')",
                "button:has-text('확인')",
                "button.se-popup-close",
                ".se-popup-dim",  # 팝업 배경 클릭
            ]
            for close_sel in popup_close_selectors:
                popup_count = await page.locator(close_sel).count()
                if popup_count > 0:
                    try:
                        await page.locator(close_sel).first.click(timeout=2000)
                        print(f"   페이지 팝업 닫기: {close_sel}")
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
        except Exception:
            pass

        # 1. 발행 버튼 찾기 (대체 셀렉터 시도)
        publish_clicked = False

        # 추가 발행 버튼 셀렉터
        # 네이버 블로그는 하단 중앙에 "글쓰기" 버튼이 있음 (이것이 발행 버튼)
        publish_selectors = [
            "div.publish_area button:has-text('글쓰기')",  # 하단 중앙 글쓰기 버튼
            "button.publish_btn",
            "a.publish_btn:has-text('글쓰기')",
            "button:has-text('글쓰기'):visible",
            "a:has-text('글쓰기'):visible",
            "button:has-text('발행'):visible",
            "button.se-toolbar-group-button.se-toolbar-publish-button",
            "button:has-text('등록')",
            "button.publish",
            "button.btn_post",
            "a:has-text('발행')",
            "a.btn_submit",
            "button[type='submit']",
        ]

        # 기존 셀렉터와 병합
        if isinstance(POST_WRITE_PUBLISH_BTN, list):
            publish_selectors = POST_WRITE_PUBLISH_BTN + publish_selectors
        else:
            publish_selectors.insert(0, POST_WRITE_PUBLISH_BTN)

        # 1. 모든 iframe에서 발행 버튼 찾기
        all_frames = page.frames
        for idx, frame in enumerate(all_frames):
            try:
                # Frame 내부의 도움말 팝업 닫기
                help_popup_selectors = [
                    "button.se-help-close-btn",
                    "button:has-text('닫기')",
                    ".se-help-close",
                ]
                for help_sel in help_popup_selectors:
                    help_count = await frame.locator(help_sel).count()
                    if help_count > 0:
                        await frame.locator(help_sel).first.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        break

                # 발행 버튼 찾기 (우선순위: 발행 > 글쓰기)
                search_texts = ["발행", "글쓰기"]
                for search_text in search_texts:
                    write_btn_count = await frame.locator(f"button:has-text('{search_text}'):visible").count()
                    if write_btn_count > 0:
                        element = frame.locator(f"button:has-text('{search_text}'):visible").first
                        await element.click(timeout=5000)
                        publish_clicked = True
                        logger.info(f"발행 버튼 클릭 성공 (Frame {idx})")
                        await asyncio.sleep(2)
                        break

                if publish_clicked:
                    break
            except Exception:
                continue

        if not publish_clicked:
            await page.screenshot(path="playwright-state/error_publish_btn.png")
            raise NaverBlogPostError("발행 버튼을 찾을 수 없습니다.")

        # 2. 발행 설정 대화상자에서 최종 "발행" 버튼 클릭
        if publish_clicked:
            try:
                await asyncio.sleep(1)  # 대화상자 로딩 대기

                # 대화상자 내 발행 버튼을 force=True로 클릭 시도
                final_publish_clicked = False
                for idx, frame in enumerate(page.frames):
                    try:
                        dialog_publish_selectors = [
                            ".layer_popup__i0QOY button[class*='confirm']:has-text('발행')",
                            ".layer_popup__i0QOY button:has-text('발행')",
                        ]

                        for selector in dialog_publish_selectors:
                            try:
                                btn_count = await frame.locator(selector).count()
                                if btn_count > 0:
                                    await frame.locator(selector).first.click(force=True, timeout=5000)
                                    final_publish_clicked = True
                                    await asyncio.sleep(2)
                                    break
                            except Exception:
                                continue

                        if final_publish_clicked:
                            break
                    except Exception:
                        continue

                # JavaScript로 대화상자 내 발행 버튼 클릭 (fallback)
                if not final_publish_clicked:
                    for frame in page.frames:
                        try:
                            result = await frame.evaluate("""
                                () => {
                                    const popup = document.querySelector('.layer_popup__i0QOY.is_show__TMSLq');
                                    if (!popup) return 'No popup';

                                    const buttons = popup.querySelectorAll('button');
                                    for (let btn of buttons) {
                                        if ((btn.textContent || '').trim() === '발행') {
                                            btn.click();
                                            return 'Clicked';
                                        }
                                    }
                                    return 'No button';
                                }
                            """)
                            if 'Clicked' in result:
                                await asyncio.sleep(3)
                                break
                        except Exception:
                            continue

            except Exception:
                pass

        # 3. 발행 완료 대기 (옵션)
        if wait_for_completion:
            try:
                # 발행 후 글 보기 페이지로 리다이렉트되는지 확인
                # URL 패턴: https://blog.naver.com/{blog_id}/{post_id}
                await page.wait_for_url("**/blog.naver.com/*/**", timeout=timeout)
                post_url = page.url

                # PostView 페이지인지 확인 (본문 영역이 있는지)
                # 글쓰기 페이지가 아닌 글 보기 페이지인지 체크
                if "postwrite" not in post_url.lower() and "redirect=write" not in post_url.lower():
                    # URL이 {blog_id}/{post_id} 형태인지 확인
                    logger.info(f"발행 완료: {post_url}")
                    return {
                        "success": True,
                        "message": "글이 성공적으로 발행되었습니다.",
                        "post_url": post_url,
                    }
                else:
                    raise NaverBlogPostError("발행 후 페이지 이동에 실패했습니다.")

            except PlaywrightTimeout:
                raise NaverBlogPostError("발행 완료 대기 시간 초과")
        else:
            return {
                "success": True,
                "message": "발행 요청을 전송했습니다.",
                "post_url": None,
            }

    except Exception as e:
        raise NaverBlogPostError(f"발행 중 오류: {str(e)}")


async def create_blog_post(
    page: Page,
    title: str,
    content: str,
    blog_id: Optional[str] = None,
    use_html: bool = False,
    wait_for_completion: bool = True,
) -> Dict[str, Any]:
    """
    네이버 블로그에 새 글을 작성하고 발행하는 전체 프로세스.

    Args:
        page: Playwright Page 객체 (로그인된 상태여야 함)
        title: 글 제목
        content: 글 본문
        blog_id: 블로그 ID (옵션)
        use_html: HTML 모드로 본문 입력할지 여부
        wait_for_completion: 발행 완료를 기다릴지 여부

    Returns:
        발행 결과 딕셔너리
        {
            "success": bool,
            "message": str,
            "post_url": str,
            "title": str,
        }

    Raises:
        NaverBlogPostError: 글 작성 실패 시
    """
    try:
        # 1. 글쓰기 페이지로 이동
        await navigate_to_post_write_page(page, blog_id)

        # 2. 제목 입력
        await fill_post_title(page, title)

        # 3. 본문 입력
        await fill_post_content(page, content, use_html)

        # 4. 발행
        result = await publish_post(page, wait_for_completion)

        result["title"] = title
        return result

    except NaverBlogPostError:
        raise
    except Exception as e:
        raise NaverBlogPostError(f"글 작성 중 오류: {str(e)}")


# ============================================================================
# v2: blocks 기반 작성 (postToNaver.ts 패리티) — 임시저장 지원
# ============================================================================


async def _fill_title_v2(page: Page, frame, title: str) -> None:
    title_field = frame.locator(sel.TITLE_PARAGRAPH).first
    # 콜드 컨텍스트에서 에디터 iframe 번들이 30초 넘게 걸릴 수 있어 넉넉히 대기.
    await title_field.wait_for(state="visible", timeout=60000)
    # "이어서 작성" 팝업 취소 후에도, 에디터 자체의 임시저장 복원이 비동기로 뒤늦게
    # 끼어들어 이전 글 제목과 겹치는 경우가 실계정에서 확인됐다. 잠깐 정착을 기다리고
    # 팝업을 한 번 더 정리한 뒤 입력한다.
    await page.wait_for_timeout(1200)
    await dismiss_continue_draft_popup(page)
    await clear_and_focus(page, frame, title_field)
    await paste_into_focused(page, title)
    # 이전 글 제목이 뒤늦게 끼어들어 겹치는 경우를 대비해 결과를 검증하고, 다르면
    # 한 번 더 지우고 다시 입력한다(자가치유).
    await page.wait_for_timeout(300)
    actual = (await title_field.inner_text()).strip()
    # 에디터가 일반 공백을 렌더링 시 \xa0(줄바꿈방지 공백)로 정규화하는 경우가 있어
    # (실계정 확인: 내용은 동일한데 공백 문자만 달라 겹침으로 오판·불필요 재입력이
    # 발생했었다), 공백 종류 차이는 무시하고 비교한다.
    normalize = lambda s: " ".join(s.split())
    if normalize(actual) != normalize(title):
        logger.warning(f"제목이 예상과 다름(겹침 의심) — 재입력합니다. actual={actual!r}")
        await clear_and_focus(page, frame, title_field)
        await paste_into_focused(page, title)


async def _insert_image_at_cursor(page: Page, frame, image_path: str) -> None:
    # expect_file_chooser()의 대기 시계는 진입 시점부터 흐른다. click_resilient가
    # 팝업 때문에 재시도하면(최대 4회 재시도) 그 시간이 같은 예산을 갉아먹어, 클릭은
    # 결국 성공해도 파일선택창 이벤트 대기가 먼저 타임아웃되는 문제가 실계정에서
    # 확인됐다. 그래서 이벤트 대기에 들어가기 전에 팝업을 미리 정리해 클릭이 보통
    # 한 번에 성공하게 하고, 대기 시계 자체도 넉넉히 늘린다.
    await dismiss_continue_draft_popup(page)
    await dismiss_cascading_alerts(page, frame)
    async with page.expect_file_chooser(timeout=45000) as fc_info:
        await click_resilient(page, frame, frame.get_by_role("button", name=sel.PHOTO_BTN_NAME))
        file_chooser = await fc_info.value
    await file_chooser.set_files(image_path)
    await page.wait_for_timeout(1500)
    await page.keyboard.press("Enter")


async def _insert_divider_at_cursor(page: Page, frame) -> None:
    """캐럿 위치에 스마트에디터 '구분선 2' 스타일 수평선을 삽입한다(best-effort).

    '구분선 선택' 드롭다운을 열고 '구분선 2'를 고른다. 옵션을 못 찾으면 기본 구분선을,
    그마저도 실패하면(예: 드롭다운이 계속 막힘) 구분선은 장식이므로 예외를 던지지 않고
    건너뛴다 — 글 작성 자체는 계속된다."""
    try:
        # 1) 구분선 스타일 드롭다운 열기
        await click_resilient(page, frame, frame.locator(sel.DIVIDER_SELECT_BTN_CSS).first)
        await page.wait_for_timeout(600)
        # 2) "구분선 2" 스타일 선택 (유일 CSS 클래스)
        opt2 = frame.locator(sel.DIVIDER_STYLE2_CSS).first
        if await is_visible(opt2, timeout=2000):
            await click_resilient(page, frame, opt2)
        else:
            # 3) 옵션을 못 찾으면 기본 구분선(구분선1) 폴백
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await click_resilient(page, frame, frame.locator(sel.DIVIDER_BTN_CSS).first)
        await page.wait_for_timeout(500)
    except Exception as e:
        logger.warning(f"구분선 삽입 실패 — 건너뜁니다: {e}")


async def _fill_body_v2(page: Page, frame, blocks: list[dict]) -> None:
    body_field = frame.locator(sel.BODY_FIRST_PARAGRAPH).first
    await clear_and_focus(page, frame, body_field)
    for block in blocks:
        if block.get("type") == "text":
            text = block.get("text", "")
            if not text.strip():
                continue
            await paste_into_focused(page, text)
            await page.keyboard.press("Enter")
        elif block.get("type") == "image":
            path = block.get("path")
            if not path:
                continue
            await _insert_image_at_cursor(page, frame, path)
        elif block.get("type") == "divider":
            await _insert_divider_at_cursor(page, frame)


async def _append_tags_v2(page: Page, tags) -> None:
    if not tags:
        return
    await paste_into_focused(page, " ".join(tags))


async def _save_draft_v2(page: Page, frame) -> None:
    draft_button = frame.get_by_role("button", name=sel.SAVE_DRAFT_BTN_NAME).first
    # 타이핑 중 자동저장으로 "이어서 작성" 팝업이 저장 직전 다시 뜰 수 있어 재정리.
    await dismiss_continue_draft_popup(page)
    await dismiss_cascading_alerts(page, frame)
    await dismiss_help_panel(page, frame)
    await click_resilient(page, frame, draft_button)
    await page.wait_for_timeout(2000)


async def _ensure_write_page(page: Page) -> None:
    """글쓰기 페이지로 이동한다. nid.naver.com(로그인)으로 튕기면 세션 적용/수동 로그인을
    최대 3분간 기다렸다가 다시 이동한다. HEADLESS=false면 열린 브라우저에서 직접
    로그인/CAPTCHA를 풀 수 있다(원래 postToNaver.ts의 로그인 재시도 동작 이식)."""
    await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
    if "nid.naver.com" not in page.url:
        return
    deadline = asyncio.get_running_loop().time() + 180
    while "nid.naver.com" in page.url:
        if asyncio.get_running_loop().time() > deadline:
            raise NaverBlogPostError(
                "로그인 페이지에서 벗어나지 못했습니다(세션 만료/CAPTCHA). "
                "열린 브라우저에서 직접 로그인한 뒤 다시 실행하세요."
            )
        await page.wait_for_timeout(2000)
    # 로그인을 벗어났으면 글쓰기 페이지로 다시 이동
    await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
    if "nid.naver.com" in page.url:
        raise NaverBlogPostError("로그인 후에도 글쓰기 페이지 진입에 실패했습니다.")
    # 다음 실행에서 재사용하도록 세션 저장(best-effort)
    try:
        from ..config import config
        await page.context.storage_state(path=config.SESSION_STORAGE_PATH)
    except Exception:
        pass


async def _ensure_fresh_editor(page: Page) -> None:
    """"이어서 작성" 팝업이 뜨면 취소하고, 이전 임시저장 내용이 화면에 남지 않도록
    글쓰기 페이지를 다시 불러와 완전히 새 에디터로 시작한다.

    "취소"는 팝업 질문만 닫을 뿐, 이미 렌더링된 이전 글 내용(제목·본문 여러 블록)까지
    지워준다는 보장이 없음이 실계정에서 확인됐다(제목이 이전 글과 겹쳐 저장됨). 팝업을
    취소한 뒤 페이지를 새로 불러오면 이전 내용이 없는 진짜 새 에디터로 시작한다.

    방금 수동 로그인을 마친 직후처럼 콜드 상태에서는 이 팝업이 늦게(수 초 뒤) 렌더링될
    수 있어(실계정 확인: 짧은 판정 때문에 놓쳐서 "이어쓰기" 상태로 진행돼 이전 임시저장
    글을 그대로 덮어씀), 매 시도마다 넉넉한 예산으로 폭넓게 재확인한다."""
    for _ in range(3):
        dismissed = await wait_and_dismiss_continue_draft_popup(page)
        if not dismissed:
            return
        logger.info("'이어서 작성' 팝업 취소 — 새 에디터로 다시 불러옵니다.")
        await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")


async def create_blog_post_v2(
    page: Page,
    *,
    title: str,
    blocks: list[dict],
    tags: list[str] | None = None,
    publish: bool = False,
) -> Dict[str, Any]:
    """blocks(텍스트/이미지 순서열)로 글을 작성한다. publish=False면 임시저장.

    Returns: {"success": bool, "message": str, "post_url": str | None, "title": str}
    """
    try:
        await _ensure_write_page(page)
        await _ensure_fresh_editor(page)

        frame = page.frame_locator(sel.MAIN_FRAME)
        await dismiss_cascading_alerts(page, frame)

        await _fill_title_v2(page, frame, title)
        await _fill_body_v2(page, frame, blocks)
        await _append_tags_v2(page, tags)

        if publish:
            result = await publish_post(page, wait_for_completion=False)
            result["title"] = title
            return result

        await _save_draft_v2(page, frame)
        return {
            "success": True,
            "message": "임시저장 완료",
            "post_url": None,
            "title": title,
        }
    except NaverBlogPostError:
        raise
    except Exception as e:
        raise NaverBlogPostError(f"글 작성 중 오류: {str(e)}")
