"""라이브 수동 검증: blocks + 임시저장.

실행: cd naver-blog-mcp && uv run python tests/test_blocks_draft_live.py
사전조건: .env에 NAVER_BLOG_ID/PASSWORD, (권장) HEADLESS=false.
성공 기준: 네이버 블로그 글쓰기에 임시저장된 글이 생기고, 텍스트 사이에
이미지가 들어가며, 마지막 줄에 해시태그가 붙는다. 콘솔에 success=True 출력.
"""

import asyncio
from pathlib import Path

from naver_blog_mcp.server import NaverBlogMCPServer
from naver_blog_mcp.mcp.tools import handle_create_post


async def main():
    # 검증용 이미지 1장 준비 (없으면 경로만 바꿔서 실행)
    sample = Path(__file__).parent / "fixtures" / "sample.jpg"
    blocks = [
        {"type": "text", "text": "첫 문단입니다. 부드러운 톤 테스트 🙂"},
        {"type": "divider"},
        {"type": "image", "path": str(sample)},
        {"type": "text", "text": "이미지 다음 문단입니다."},
        {"type": "divider"},
        {"type": "text", "text": "마지막 문단, 총평입니다."},
    ]

    server = NaverBlogMCPServer()
    await server.initialize()
    try:
        page = await server.get_page()
        result = await handle_create_post(
            page=page,
            title="[검증] blocks 임시저장 테스트",
            blocks=blocks,
            tags=["#검증", "#mcp"],
            publish=False,
        )
        print("RESULT:", result)
        assert result["success"] is True, result
    finally:
        input("브라우저에서 임시저장 글을 확인한 뒤 Enter를 누르세요...")
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
