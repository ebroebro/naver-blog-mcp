"""네이버 블로그 글쓰기 자동화."""

import asyncio
import logging
import re
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
    await dismiss_continue_draft_popup(page, frame)
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
    await dismiss_continue_draft_popup(page, frame)
    await dismiss_cascading_alerts(page, frame)
    async with page.expect_file_chooser(timeout=45000) as fc_info:
        await click_resilient(page, frame, frame.get_by_role("button", name=sel.PHOTO_BTN_NAME))
        file_chooser = await fc_info.value
    await file_chooser.set_files(image_path)
    await page.wait_for_timeout(1500)
    await page.keyboard.press("Enter")
    # 크기/정렬은 여기서 하지 않는다. 툴바·크기변경 레이어(본문 밖)를 클릭하면 캐럿이
    # 본문 밖으로 나가 다음 블록(특히 마지막 이미지 뒤 텍스트) 입력이 유실됐다(실계정
    # 확인). 그래서 모든 본문·태그 입력이 끝난 뒤 _apply_size_align_to_all_images로
    # 일괄 처리해 캐럿 흐름과 완전히 분리한다.


# 이미지 크기: 문서 너비 대비 목표 비율(1/2). 사용자 요청값 — 여기만 바꾸면 비율 조정됨.
IMAGE_SIZE_FRACTION = 0.5


async def _wait_image_uploaded(page: Page, img_comp, timeout_ms: int = 60000) -> bool:
    """주어진 이미지 컴포넌트(img_comp)의 업로드 완료를 기다린다.

    라이브 확인(tests/inspect_image_upload_state.py): 삽입 직후 <img> src는 한동안
    비어있다가(업로드 중) 잠깐 data: 플레이스홀더를 거쳐, 완료되면 https 업로드 URL
    (blogfiles.pstatic.net)로 바뀐다. 업로드 시간 편차가 커서(즉시~수십 초) 고정 대기가
    아니라 이 조건을 폴링한다. 업로드 중에는 크기/정렬 기능이 막혀 있어 반드시 선행돼야 한다.

    Returns: 완료(https src)를 확인하면 True, 예산 내 미완이면 False."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_ms / 1000
    img = img_comp.locator("img").first
    while loop.time() < deadline:
        try:
            src = await img.get_attribute("src")
            if src and src.startswith("https"):
                await page.wait_for_timeout(300)  # 완료 직후 안정화 여유
                return True
        except Exception:
            pass
        await page.wait_for_timeout(500)
    logger.warning("이미지 업로드 완료 신호를 시간 내 확인 못 함 — 이 이미지의 크기/정렬 건너뜀.")
    return False


async def _apply_size_align_to_all_images(page: Page, frame) -> None:
    """본문·태그 입력이 모두 끝난 뒤, 모든 이미지를 '문서 너비의 1/2' + 가운데 정렬로
    일괄 처리한다(best-effort). 본문 삽입 중이 아니라 끝난 뒤에 하므로 캐럿 흐름을
    건드리지 않는다 — 삽입 중 인라인 처리 시 마지막 이미지 뒤 텍스트가 유실되던 문제를
    구조적으로 없앤다.

    각 이미지는 (업로드 완료 대기 → 선택 → 1/2 리사이징 → 가운데 정렬) 순으로 처리한다.
    '모든사진 적용'은 해제해 각 이미지를 독립적으로 맞춘다(연쇄 축소 방지)."""
    comps = frame.locator(".se-component.se-image")
    try:
        n = await comps.count()
    except Exception:
        return
    for i in range(n):
        img_comp = comps.nth(i)
        try:
            if not await _wait_image_uploaded(page, img_comp):
                continue
            await img_comp.click(timeout=6000)
            await page.wait_for_timeout(400)
            await _resize_selected_image_half(page, frame, img_comp)
            # 가운데 정렬 (단발 클릭).
            await frame.locator(sel.IMAGE_ALIGN_CENTER_CSS).first.click(timeout=6000)
            await page.wait_for_timeout(300)
        except Exception as e:
            logger.warning(f"이미지 {i} 크기/정렬 실패(무시): {e}")


async def _resize_selected_image_half(page: Page, frame, img_comp) -> None:
    """선택된 이미지를 현재(문서 너비=풀폭) 렌더 크기의 1/2로 리사이징한다.

    '크기 변경' 레이어의 너비/높이 px 입력에 절반 값을 넣는다(라이브 확정:
    tests/inspect_image_resize_layer.py). 비율 자동 잠금 여부와 무관하게 왜곡되지 않도록
    W/H 둘 다 절반으로 지정한다. '모든사진 적용'은 해제해 다른 이미지에 연쇄 적용되지
    않게 한다(이미 줄인 이미지를 또 기준 삼아 재축소되는 사고 방지)."""
    img = img_comp.locator("img").first
    dims = await img.evaluate("(el) => ({ w: el.clientWidth, h: el.clientHeight })")
    target_w = max(1, round(dims["w"] * IMAGE_SIZE_FRACTION))
    target_h = max(1, round(dims["h"] * IMAGE_SIZE_FRACTION))
    await frame.locator(sel.IMAGE_RESIZE_OPEN_CSS).first.click(timeout=6000)
    await page.wait_for_timeout(500)
    # '모든사진 적용' 체크 해제(각 이미지 독립 크기).
    try:
        checkbox = frame.locator(sel.IMAGE_RESIZE_ALL_CHECKBOX).first
        if await checkbox.is_checked():
            await checkbox.uncheck(timeout=3000)
    except Exception as e:
        logger.warning(f"'모든사진 적용' 해제 실패(무시): {e}")
    await frame.locator(sel.IMAGE_RESIZE_WIDTH_INPUT).first.fill(str(target_w))
    await page.wait_for_timeout(150)
    await frame.locator(sel.IMAGE_RESIZE_HEIGHT_INPUT).first.fill(str(target_h))
    await page.wait_for_timeout(150)
    await frame.locator(sel.IMAGE_RESIZE_APPLY_CSS).first.click(timeout=6000)
    await page.wait_for_timeout(500)


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


async def _insert_quote_at_cursor(page: Page, frame, text: str, style: str = "corner") -> None:
    """캐럿 위치에 스마트에디터 인용구 컴포넌트를 삽입하고 그 안에 text를 채운다
    (여러 줄이면 줄마다 Enter로 구분해 붙여넣는다).

    style="corner"(기본, 꺾쇠/모서리 브라켓, data-value='quotation_corner')는 위치
    정보 블록용. style="underline"(밑줄, data-value='quotation_underline')은
    소제목용 — 텍스트를 다 채운 뒤 폰트 크기를 24로 키운다(라이브 확정:
    tests/inspect_quote_style4.py, inspect_text_format_apply2.py).

    실계정에서 세 가지 버그가 확인됐다:
    1) click_resilient로 인용구 삽입 버튼을 클릭하면, 인용구 삽입은 클릭의
       부작용(DOM 생성)이 영속적인데 click_resilient가 실패로 착각하고 재시도해
       인용구가 두 번 삽입됐다. 그래서 여기서는 재시도 없는 단발 클릭만 쓰고,
       클릭 전에 팝업을 미리 정리해 애초에 막힐 일을 줄인다.
    2) 원하는 스타일(꺾쇠)을 화면에 보이는 드롭다운 툴팁 이름("프레임")으로
       찾으려 했으나, 실제 DOM 버튼 텍스트는 "인용구 1"~"인용구 6"이라 텍스트
       매칭이 항상 실패해 조용히 기본 스타일로 폴백됐다(tests/inspect_quote_popup.py
       라이브 덤프로 확인). 유일하게 안정적인 구분값인 data-value='quotation_corner'
       기반 CSS 클래스(QUOTE_STYLE_CORNER_CSS)로 지정해 해결.
    3) 텍스트를 다 채운 뒤 커서가 인용구 안에 그대로 남아, 다음 블록(소제목 등)이
       인용구 안에 이어서 입력됐다. Enter를 눌러도 인용구 컴포넌트 자신의
       "내용" 필드 안에 줄만 추가될 뿐 절대 못 빠져나온다는 게 라이브 DOM
       조사(tests/inspect_quote_close*.py, MARKER 텍스트로 어느 컴포넌트에
       들어갔는지 직접 확인)로 밝혀졌다. 실제로 빠져나오는 유일한 방법은
       ArrowDown을 정확히 2번 누르는 것(1번째: 내용→출처 필드 이동, 2번째:
       출처 필드에서 다음 형제 컴포넌트로 이동 — 문서 맨 끝이면 새 se-text
       컴포넌트가 자동 생성됨. Enter나 Escape+Enter, 인용구 아래 좌표 클릭,
       Tab은 전부 실패하는 것도 같은 조사로 확인됨).

    인용구 삽입 자체가 실패해도(버튼을 못 찾는 등) 예외를 던지지 않고 텍스트만
    일반 문단으로 붙여넣어 내용 손실을 막는다 — 위치 정보는 장식보다 우선이다."""
    try:
        await dismiss_continue_draft_popup(page, frame)
        await dismiss_cascading_alerts(page, frame)

        # 1) 인용구 스타일 드롭다운 열기 (단발 클릭 — 재시도로 인한 중복 삽입 방지)
        await frame.locator(sel.QUOTE_SELECT_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(600)

        # 2) 스타일 선택 (라이브 DOM 확인: data-value='quotation_corner'/'quotation_underline')
        style_css = sel.QUOTE_STYLE_UNDERLINE_CSS if style == "underline" else sel.QUOTE_STYLE_CORNER_CSS
        style_option = frame.locator(style_css).first
        if await is_visible(style_option, timeout=2000):
            await style_option.click(timeout=8000)
        else:
            # 못 찾으면 기본 인용구로 폴백 (역시 단발 클릭)
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await frame.locator(sel.QUOTE_BTN_CSS).first.click(timeout=8000)
        await page.wait_for_timeout(500)

        # 3) 인용구 안에 텍스트 채우기
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                await page.keyboard.press("Enter")
            if line.strip():
                await paste_into_focused(page, line)

        # 3-1) 소제목(밑줄 스타일)이면 폰트 크기를 24로 키운다(best-effort, 장식이므로
        # 실패해도 예외를 던지지 않는다). 붙여넣기 직후 곧바로 트리플클릭하면 DOM이
        # 아직 안 따라와 실패하는 레이스가 실계정에서 확인돼(연속 인용구 중 두 번째부터
        # 실패) 정착 시간을 준다.
        if style == "underline":
            await page.wait_for_timeout(400)
            await _apply_quote_font_size(page, frame, sel.FONT_SIZE_24_CSS)

        # 4) 인용구 밖으로 캐럿 이동 — 안 그러면 다음 블록이 인용구 안에 이어써짐.
        # ArrowDown 2회: 1번째는 내용→출처 필드, 2번째가 실제로 컴포넌트를
        # 빠져나가 다음 형제(또는 문서 끝이면 새 컴포넌트)로 이동한다(라이브 확인).
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(300)
    except Exception as e:
        logger.warning(f"인용구 삽입 실패 — 일반 텍스트로 대체합니다: {e}")
        await paste_into_focused(page, text)
        await page.keyboard.press("Enter")


async def _apply_quote_font_size(page: Page, frame, size_css: str) -> None:
    """방금 채운 인용구 내용 전체를 트리플클릭으로 선택하고 폰트 크기를 적용한다
    (best-effort). 폰트 크기는 자유 입력이 아니라 고정 프리셋 드롭다운이다(라이브
    확정: tests/inspect_text_format_apply.py). 적용 후 인용구 내용을 다시 클릭해
    포커스를 복구한다 — 드롭다운 클릭으로 포커스가 밖으로 나가면 바로 이어지는
    ArrowDown 탈출 시퀀스가 엉뚱한 곳에서 작동할 수 있다. 다른 새 서식 함수들과
    동일하게, 자동저장 "확인" 팝업이 트리플클릭을 막을 수 있어 미리 정리한다."""
    try:
        await dismiss_continue_draft_popup(page, frame)
        await dismiss_cascading_alerts(page, frame)
        content = frame.locator(".se-quotation").last.locator(".se-text-paragraph").first
        await content.click(timeout=4000, click_count=3)  # 트리플클릭 = 전체 선택
        await page.wait_for_timeout(300)
        await frame.locator(sel.FONT_SIZE_OPEN_CSS).first.click(timeout=4000)
        await page.wait_for_timeout(400)
        await frame.locator(size_css).first.click(timeout=4000)
        await page.wait_for_timeout(300)
        await content.click(timeout=4000)
        await page.keyboard.press("End")
    except Exception as e:
        logger.warning(f"인용구 폰트 크기 적용 실패(무시): {e}")


async def _all_body_paragraphs(frame) -> list:
    """제목을 제외한 본문 .se-text-paragraph 전부를 순서대로 반환한다.

    AI 프롬프트가 "문장마다 줄바꿈"하도록 지시하면서, 텍스트 블록 하나(예:
    2~4문장 문단)에 실제 \\n이 여러 개 포함돼 있다. 이 텍스트를 통째로
    paste_into_focused하면, 네이버 에디터가 \\n마다 별도의 .se-text-paragraph를
    만든다는 게 라이브로 확인됐다(tests/inspect_multiline_paste_align.py) —
    즉 "블록 하나 = 문단 하나"라는 가정이 깨진다.

    처음엔 "이 블록이 붙여넣기 전/후로 몇 개를 새로 만들었는지" 개수를 비교해
    추적했는데, 블록과 블록 사이(Enter 직후 등) 문단 생성이 아직 안 따라온
    상태에서 다음 블록의 "이전 개수"를 재는 타이밍 레이스로 실계정에서 볼드
    대상 단어를 못 찾는 실패가 있었다. 매번 정확히 "이 블록이 만든 문단만"
    추릴 필요 없이, 그냥 본문 전체에서 검색하는 쪽이 훨씬 간단하고 견고하다
    (볼드 대상 단어가 여러 블록에 걸쳐 중복되는 경우는 드물다).

    BODY_FIRST_PARAGRAPH와 동일한 CSS(.se-component.se-text .se-text-paragraph)를
    쓴다 — 이미 제목(.se-title-text 스코프)을 제외하도록 스코프돼 있다."""
    return await frame.locator(sel.BODY_FIRST_PARAGRAPH).all()


async def _center_align_body_start(page: Page, frame) -> None:
    """본문 작성 시작 전(빈 첫 문단, 캐럿만 있는 상태)에 미리 가운데 정렬을
    걸어둔다(best-effort). 이후 타이핑/붙여넣기하는 모든 문단이 이 정렬을
    그대로 물려받고, 인용구/구분선 등 다른 블록을 사이에 둬도 계속 유지됨이
    라이브로 확인됐다(tests/inspect_align_before_typing.py) — 인용구 자체는
    정렬 대상에서 제외됨(왼쪽 정렬 유지, 의도된 동작)도 함께 확인.

    "정렬 열기" 드롭다운(data-name='align-drop-down-with-justify')은 텍스트
    선택 없이 캐럿만 있어도 뜬다. 이전엔 텍스트를 붙여넣은 뒤 "텍스트 선택"이
    있어야 뜨는 컨텐츠 툴바(TEXT_ALIGN_CENTER_CSS)로 정렬을 걸었는데, "문장마다
    줄바꿈" 지시로 텍스트 블록 하나가 여러 문단으로 쪼개지면서(라이브 확인:
    tests/inspect_multiline_paste_align.py) 트레일링 빈 줄을 짚어 정렬 버튼을
    못 찾는 실패가 실계정에서 반복됐다. 타이핑 전에 한 번만 걸면 그 문제 자체가
    없어진다.

    자동저장 "확인" 팝업이 드롭다운 클릭을 막을 수 있어 작업 전에 미리 정리한다."""
    try:
        await dismiss_continue_draft_popup(page, frame)
        await dismiss_cascading_alerts(page, frame)
        align_open = frame.locator(sel.TEXT_ALIGN_OPEN_CSS).first
        if not await is_visible(align_open, timeout=2000):
            logger.warning("'정렬 열기' 버튼을 못 찾음(무시)")
            return
        await align_open.click(timeout=4000)
        await page.wait_for_timeout(400)
        center_opt = frame.locator(sel.TEXT_ALIGN_CENTER_OPTION_CSS).first
        if await is_visible(center_opt, timeout=2000):
            await center_opt.click(timeout=4000)
        else:
            logger.warning("'가운데 정렬' 옵션을 못 찾음(무시)")
        await page.wait_for_timeout(300)
    except Exception as e:
        logger.warning(f"본문 시작 가운데 정렬 적용 실패(무시): {e}")


async def _select_text_in_paragraph(page: Page, frame, paragraph, substring: str) -> bool:
    """paragraph(문단 Locator) 안에서 substring의 위치를 찾아 실제 마우스 드래그로
    선택한다. 더블클릭 같은 진짜 마우스 제스처만 볼드 버튼이 뜨는 컨텐츠 툴바를
    반응시킨다는 게 라이브로 확인됐다(tests/inspect_text_format_apply2.py) — 그래서
    JS로 Selection을 직접 설정하는 대신, DOM Range로 정확한 좌표를 계산한 뒤 진짜
    마우스 드래그(down→move→up)를 재현한다.

    좌표는 #mainFrame(iframe) 내부 기준으로 계산되므로, 실제 마우스 좌표로 쓰려면
    iframe 자신의 페이지 내 위치를 더해야 한다.

    Returns: 선택에 성공했으면 True."""
    rects = await paragraph.evaluate(
        """(el, sub) => {
            const text = el.textContent || '';
            const idx = text.indexOf(sub);
            if (idx === -1) return null;
            const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
            let pos = 0, startNode = null, startOffset = 0, endNode = null, endOffset = 0;
            let node;
            while ((node = walker.nextNode())) {
                const len = node.textContent.length;
                if (startNode === null && idx < pos + len) {
                    startNode = node; startOffset = idx - pos;
                }
                if (endNode === null && (idx + sub.length) <= pos + len) {
                    endNode = node; endOffset = (idx + sub.length) - pos;
                    break;
                }
                pos += len;
            }
            if (!startNode || !endNode) return null;
            const range = document.createRange();
            range.setStart(startNode, startOffset);
            range.setEnd(endNode, endOffset);
            const rects = range.getClientRects();
            if (rects.length === 0) return null;
            const first = rects[0];
            const last = rects[rects.length - 1];
            return {
                startX: first.left, startY: first.top + first.height / 2,
                endX: last.right, endY: last.top + last.height / 2,
            };
        }""",
        substring,
    )
    if not rects:
        return False
    frame_element = await page.query_selector(sel.MAIN_FRAME)
    if not frame_element:
        return False
    box = await frame_element.bounding_box()
    if not box:
        return False
    start_x, start_y = box["x"] + rects["startX"], box["y"] + rects["startY"]
    end_x, end_y = box["x"] + rects["endX"], box["y"] + rects["endY"]
    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    await page.mouse.move(end_x, end_y, steps=5)
    await page.mouse.up()
    return True


async def _apply_bold_to_words(page: Page, frame, words: list[str], paragraphs: list) -> None:
    """paragraphs(방금 타이핑한 블록이 실제로 만든 문단들) 안에서 words 각각을
    찾아 볼드 처리한다(best-effort). 문장마다 줄바꿈 지시로 한 텍스트 블록이
    여러 .se-text-paragraph로 쪼개질 수 있어(tests/inspect_multiline_paste_align.py
    라이브 확인), 대상 단어가 어느 문장(문단)에 있는지 몰라 전부 순서대로
    검색한다. 볼드는 선택한 부분에만 적용되고 다른 문단엔 상속되지 않음이
    라이브로 확인됐다(tests/inspect_bold_word.py) — 그래서 단어마다 매번
    적용해야 한다. 강조는 장식이므로 실패해도 예외를 던지지 않는다. 자동저장
    "확인" 팝업이 마우스 드래그 선택을 막을 수 있어(실계정 확인) 시작 전에
    미리 정리한다."""
    if not words or not paragraphs:
        return
    await dismiss_continue_draft_popup(page, frame)
    await dismiss_cascading_alerts(page, frame)
    for word in words:
        found = False
        for paragraph in paragraphs:
            try:
                selected = await _select_text_in_paragraph(page, frame, paragraph, word)
                if not selected:
                    continue
                found = True
                bold_btn = frame.locator(sel.BOLD_TOOLBAR_CSS).first
                if await is_visible(bold_btn, timeout=1500):
                    await bold_btn.click(timeout=3000)
                else:
                    logger.warning(f"'{word}' 선택 후 볼드 버튼이 안 보임 — 건너뜀")
                break
            except Exception as e:
                logger.warning(f"'{word}' 볼드 적용 시도 실패(무시): {e}")
        if not found:
            logger.warning(f"'{word}' 위치를 못 찾음 — 볼드 건너뜀")

    # 볼드 대상 단어가 이 블록의 마지막 문장이 아니라 중간 문장에 있으면, 마우스
    # 선택 후 캐럿이 그 문단(문서 중간)에 남는다. 호출부가 곧이어 누르는 Enter가
    # 문서 끝이 아니라 그 자리에 새 줄을 만들어, 다음 블록이 엉뚱한 위치에
    # 붙여써지는 사고가 실계정에서 확인됐다. 반드시 진짜 마지막 문단으로
    # 캐럿을 복귀시킨 뒤 반환한다.
    #
    # 실계정 확인(2026-08-02): 마지막 볼드 클릭 직후 "선택"이 살아있는 상태에서
    # 아래 클릭이 se-contents-toolbar-wrap(안 닫힌 볼드 툴바)에 막혀 실패하면,
    # 이 try 블록 전체가 스킵돼 선택이 전혀 접히지 않는다. 그 상태로 호출부의
    # 다음 Enter가 눌리면 "선택된 텍스트를 지우고 그 자리에 줄바꿈"이 되어,
    # 방금 볼드 처리한 단어/구절이 그대로 삭제되는 게 라이브 DOM으로 확인됐다
    # (tests/inspect_bold_not_sticking.py). 그래서 클릭 성패와 무관하게 먼저
    # 키보드로 선택부터 반드시 접는다(ArrowRight는 클릭이 필요 없어 툴바
    # 가로채기의 영향을 받지 않는다).
    try:
        await page.keyboard.press("ArrowRight")
    except Exception as e:
        logger.warning(f"볼드 처리 후 선택 접기 실패(무시): {e}")

    try:
        await paragraphs[-1].click(timeout=3000)
    except Exception:
        # 일반 클릭이 잔류 툴바에 막히면, dismiss_help_panel과 동일하게 click
        # 이벤트를 직접 디스패치해 포인터 가로채기를 우회한다.
        try:
            await paragraphs[-1].dispatch_event("click")
        except Exception as e:
            logger.warning(f"볼드 처리 후 캐럿 복구 실패(무시): {e}")

    try:
        await page.keyboard.press("End")
    except Exception as e:
        logger.warning(f"볼드 처리 후 End 키 실패(무시): {e}")


async def _apply_bold_and_color_to_store_name(
    page: Page, frame, store_name: str, paragraphs: list
) -> None:
    """본문 전체에서 가게 이름과 일치하는 부분에 볼드+파란색을 적용한다(사용자
    요청: 강조해야 할 가게 이름을 파란색+볼드로). 문단마다 첫 번째 일치 지점
    에만 적용한다(같은 문단 안에 가게 이름이 여러 번 나오는 경우는 드물어
    범위를 좁혔다). 장식용 서식이므로 실패해도 예외를 던지지 않는다.

    볼드(토글 버튼 클릭)와 색상(팝업 열기 → 스와치 클릭 → 확인 버튼)은 서로
    다른 UI 흐름이라 한 번의 선택으로 동시에 적용할 수 없다 — 볼드를 먼저
    적용한 뒤, 볼드 버튼 클릭으로 풀렸을 수 있는 선택을 다시 잡고 색상을
    적용한다(라이브 확인: 컨텐츠 툴바가 열린 채로 다른 버튼을 클릭하면 팝업이
    닫히며 선택도 함께 풀림 — tests/inspect_text_color3.py)."""
    if not store_name or not paragraphs:
        return
    await dismiss_continue_draft_popup(page, frame)
    await dismiss_cascading_alerts(page, frame)

    for paragraph in paragraphs:
        try:
            selected = await _select_text_in_paragraph(page, frame, paragraph, store_name)
            if not selected:
                continue

            bold_btn = frame.locator(sel.BOLD_TOOLBAR_CSS).first
            if not await is_visible(bold_btn, timeout=1500):
                logger.warning(f"'{store_name}' 선택 후 볼드 버튼이 안 보임 — 건너뜀")
                continue
            await bold_btn.click(timeout=3000)

            # 볼드 클릭으로 선택/툴바가 닫혔을 수 있어 색상 적용 전에 같은
            # 문단에서 다시 선택한다. 실계정 확인(2026-08-08): 제목·인용구·여러
            # 블록이 있는 실제 문서에서는 재선택 직후 컨텐츠 툴바(폰트/크기/볼드/
            # 기울임/글자색/인용구변환/정렬/목록/번역까지 버튼이 많다)가 완전히
            # 다시 렌더링되는 데 걸리는 시간이 간단한 테스트 문서보다 길어, 곧바로
            # 글자색 버튼을 찾으면 못 찾는 레이스가 있었다(글자색 버튼이 안 보임
            # 경고). 정착 시간을 주고 타임아웃도 넉넉히 늘린다.
            reselected = await _select_text_in_paragraph(page, frame, paragraph, store_name)
            if not reselected:
                logger.warning(f"'{store_name}' 볼드 후 재선택 실패 — 색상 적용 건너뜀")
                continue
            await page.wait_for_timeout(400)

            color_btn = frame.locator(sel.TEXT_COLOR_OPEN_CSS).first
            if not await is_visible(color_btn, timeout=3000):
                logger.warning(f"'{store_name}' 글자색 버튼이 안 보임 — 색상 적용 건너뜀")
                continue
            await color_btn.click(timeout=3000)
            await page.wait_for_timeout(400)

            blue_swatch = frame.locator(sel.TEXT_COLOR_BLUE_SWATCH_CSS).first
            if not await is_visible(blue_swatch, timeout=2500):
                logger.warning(f"'{store_name}' 파란색 스와치를 못 찾음")
                continue
            await blue_swatch.click(timeout=3000)
            await page.wait_for_timeout(200)

            apply_btn = frame.locator(sel.TEXT_COLOR_APPLY_CSS).first
            if await is_visible(apply_btn, timeout=2500):
                await apply_btn.click(timeout=3000)
            else:
                logger.warning(f"'{store_name}' 색상 적용(확인) 버튼이 안 보임")
        except Exception as e:
            logger.warning(f"'{store_name}' 볼드+색상 적용 시도 실패(무시): {e}")

    # 캐럿 복구 — _apply_bold_to_words와 동일한 이유(선택이 남아있으면 이후
    # 호출부의 Enter 등이 선택 영역을 지울 수 있다). ArrowRight로 먼저 선택을
    # 접고, 진짜 마지막 문단으로 클릭 이동(실패 시 dispatch_event로 우회)한다.
    try:
        await page.keyboard.press("ArrowRight")
    except Exception as e:
        logger.warning(f"가게 이름 서식 처리 후 선택 접기 실패(무시): {e}")

    try:
        await paragraphs[-1].click(timeout=3000)
    except Exception:
        try:
            await paragraphs[-1].dispatch_event("click")
        except Exception as e:
            logger.warning(f"가게 이름 서식 처리 후 캐럿 복구 실패(무시): {e}")

    try:
        await page.keyboard.press("End")
    except Exception as e:
        logger.warning(f"가게 이름 서식 처리 후 End 키 실패(무시): {e}")


_BOLD_MARKUP_RE = re.compile(r"\*\*(.+?)\*\*")


def _extract_bold_markup(text: str) -> tuple[str, list[str]]:
    """AI가 표시한 **단어** 강조 마크업을 걷어낸 깨끗한 텍스트와, 볼드 처리할
    부분 문자열 목록을 반환한다. 마커 자체는 네이버 에디터에 그대로 타이핑하지
    않는다 — 실제 볼드 서식으로 별도 적용한다."""
    bold_words: list[str] = []

    def _repl(m: re.Match) -> str:
        bold_words.append(m.group(1))
        return m.group(1)

    clean = _BOLD_MARKUP_RE.sub(_repl, text)
    return clean, bold_words


async def _fill_body_v2(page: Page, frame, blocks: list[dict]) -> None:
    body_field = frame.locator(sel.BODY_FIRST_PARAGRAPH).first
    await clear_and_focus(page, frame, body_field)
    # 타이핑 시작 전에 한 번만 가운데 정렬을 걸어둔다 — 이후 모든 문단이
    # 상속받으므로(인용구를 사이에 둬도 유지, 인용구 자체는 제외) 문단마다
    # 다시 적용할 필요가 없다.
    await _center_align_body_start(page, frame)
    for block in blocks:
        if block.get("type") == "text":
            raw_text = block.get("text", "")
            if not raw_text.strip():
                continue
            clean_text, bold_words = _extract_bold_markup(raw_text)
            await paste_into_focused(page, clean_text)
            if bold_words:
                # 붙여넣기 직후 곧바로 텍스트 검색을 하면 DOM이 아직 안 따라와
                # 실패하는 레이스가 실계정에서 확인됐다. 정착 시간을 준다.
                await page.wait_for_timeout(400)
                # "이 블록이 새로 만든 문단만" 추리려던 이전 방식은 블록 사이
                # 타이밍 레이스로 대상 단어를 못 찾는 실패가 있었다(실계정 확인).
                # 본문 전체에서 검색하는 쪽이 더 간단하고 견고하다.
                all_paragraphs = await _all_body_paragraphs(frame)
                await _apply_bold_to_words(page, frame, bold_words, all_paragraphs)
            await page.keyboard.press("Enter")
            # Enter 직후 곧바로 다음 블록을 붙여넣으면 에디터가 새 줄 생성을
            # 아직 못 따라와 다음 블록의 앞부분(심하면 문장 전체)이 씹히는
            # 레이스가 실계정에서 확인됐다. 정착 시간을 준다.
            await page.wait_for_timeout(300)
        elif block.get("type") == "image":
            path = block.get("path")
            if not path:
                continue
            await _insert_image_at_cursor(page, frame, path)
        elif block.get("type") == "divider":
            await _insert_divider_at_cursor(page, frame)
        elif block.get("type") == "quote":
            text = block.get("text", "")
            if text.strip():
                await _insert_quote_at_cursor(page, frame, text, style=block.get("style", "corner"))


async def _append_tags_v2(page: Page, tags) -> None:
    if not tags:
        return
    await paste_into_focused(page, " ".join(tags))


async def _save_draft_v2(page: Page, frame) -> None:
    draft_button = frame.get_by_role("button", name=sel.SAVE_DRAFT_BTN_NAME).first
    # 타이핑 중 자동저장으로 "이어서 작성" 팝업이 저장 직전 다시 뜰 수 있어 재정리.
    await dismiss_continue_draft_popup(page, frame)
    await dismiss_cascading_alerts(page, frame)
    await dismiss_help_panel(page, frame)
    await click_resilient(page, frame, draft_button)
    await page.wait_for_timeout(2000)


async def _ensure_write_page(page: Page) -> None:
    """글쓰기 페이지로 이동한다. nid.naver.com(로그인)으로 튕기면:
    - HEADLESS=false: 사용자가 열린 브라우저에서 직접 로그인/CAPTCHA를 풀 수 있도록
      최대 3분간 대기한다(원래 postToNaver.ts의 로그인 재시도 동작 이식).
    - HEADLESS=true: 아무도 화면을 볼 수 없으므로 3분을 그냥 흘려보내지 않고, 저장된
      아이디/비번으로 즉시 재로그인을 1회 시도한다. 일반적인(CAPTCHA 없는) 세션 만료는
      이걸로 headless 상태 그대로 자동 복구된다. CAPTCHA가 뜨거나 자격증명이 잘못됐으면
      (headless로는 원천적으로 풀 수 없으므로) 재시도 없이 바로 명확한 에러로 실패시켜
      `scripts/login.py`를 헤드 모드로 한 번 실행해 재인증하라고 안내한다."""
    from ..config import config

    await page.goto(sel.GO_BLOG_WRITE_URL, wait_until="domcontentloaded")
    if "nid.naver.com" not in page.url:
        return

    if config.HEADLESS:
        from .login import (
            CaptchaDetectedError,
            InvalidCredentialsError,
            NaverLoginError,
            login_to_naver,
        )

        logger.warning(
            "글쓰기 페이지 진입 중 로그인 페이지로 튕김 — 저장된 자격증명으로 재로그인 시도(headless)"
        )
        try:
            await login_to_naver(
                page=page,
                user_id=config.NAVER_BLOG_ID,
                password=config.NAVER_BLOG_PASSWORD,
                storage_state_path=config.SESSION_STORAGE_PATH,
                headless=True,
            )
        except CaptchaDetectedError:
            raise NaverBlogPostError(
                "세션이 만료되어 재로그인을 시도했지만 CAPTCHA가 감지되어 headless 상태로는 풀 수 없습니다. "
                "`uv run python scripts/login.py`를 실행해 브라우저에서 직접 로그인/CAPTCHA를 해결한 뒤 다시 실행하세요."
            )
        except InvalidCredentialsError as e:
            raise NaverBlogPostError(f"저장된 계정 정보로 재로그인에 실패했습니다: {e}")
        except NaverLoginError as e:
            raise NaverBlogPostError(f"재로그인 중 오류가 발생했습니다: {e}")
    else:
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
        await page.context.storage_state(path=config.SESSION_STORAGE_PATH)
    except Exception:
        pass


async def _ensure_fresh_editor(page: Page, frame) -> None:
    """"이어서 작성" 팝업이 뜨면 취소하고, 이전 임시저장 내용이 화면에 남지 않도록
    글쓰기 페이지를 다시 불러와 완전히 새 에디터로 시작한다.

    "취소"는 팝업 질문만 닫을 뿐, 이미 렌더링된 이전 글 내용(제목·본문 여러 블록)까지
    지워준다는 보장이 없음이 실계정에서 확인됐다(제목이 이전 글과 겹쳐 저장됨). 팝업을
    취소한 뒤 페이지를 새로 불러오면 이전 내용이 없는 진짜 새 에디터로 시작한다.

    방금 수동 로그인을 마친 직후처럼 콜드 상태에서는 이 팝업이 늦게(수 초 뒤) 렌더링될
    수 있어(실계정 확인: 짧은 판정 때문에 놓쳐서 "이어쓰기" 상태로 진행돼 이전 임시저장
    글을 그대로 덮어씀), 매 시도마다 넉넉한 예산으로 폭넓게 재확인한다.

    이 팝업이 page 최상단이 아니라 #mainFrame "안"에서 뜨는 변형("작성 중인 글이
    있습니다")이 실계정에서 확인됐다(tests/inspect_continue_draft2.py). frame을
    안 넘기면 이 변형을 못 찾아 조용히 "팝업 없음"으로 오판하고, 뒤이어
    dismiss_cascading_alerts가 같은 팝업의 "확인"(=이어쓰기) 버튼을 먼저 찾아
    클릭해버려 이전 글을 그대로 덮어쓰는 사고로 이어진다 — 반드시 frame을 넘긴다."""
    for _ in range(3):
        dismissed = await wait_and_dismiss_continue_draft_popup(page, frame)
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
    place_name: str | None = None,
    publish: bool = False,
) -> Dict[str, Any]:
    """blocks(텍스트/이미지 순서열)로 글을 작성한다. publish=False면 임시저장.
    place_name이 주어지면 본문에서 그 이름과 일치하는 부분에 볼드+파란색을
    적용한다(문단마다 첫 일치 지점만, best-effort).

    Returns: {"success": bool, "message": str, "post_url": str | None, "title": str}
    """
    try:
        await _ensure_write_page(page)
        frame = page.frame_locator(sel.MAIN_FRAME)
        await _ensure_fresh_editor(page, frame)
        await dismiss_cascading_alerts(page, frame)

        await _fill_title_v2(page, frame, title)
        await _fill_body_v2(page, frame, blocks)
        if place_name:
            all_paragraphs = await _all_body_paragraphs(frame)
            await _apply_bold_and_color_to_store_name(page, frame, place_name, all_paragraphs)
        await _append_tags_v2(page, tags)
        # 본문·태그 입력이 끝난 뒤 이미지 크기(1/2)·가운데 정렬을 일괄 처리한다
        # (캐럿 흐름과 분리 — 인라인 처리 시 마지막 이미지 뒤 텍스트 유실 문제 해결).
        await _apply_size_align_to_all_images(page, frame)

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
