import asyncio

from naver_blog_mcp.mcp import tools


def test_blocks_route_calls_v2(monkeypatch):
    calls = {}

    async def fake_v2(page, *, title, blocks, tags, publish):
        calls.update(title=title, blocks=blocks, tags=tags, publish=publish)
        return {"success": True, "message": "임시저장 완료", "post_url": None, "title": title}

    monkeypatch.setattr(
        "naver_blog_mcp.automation.post_actions.create_blog_post_v2", fake_v2
    )

    blocks = [{"type": "text", "text": "안녕"}, {"type": "image", "path": "/tmp/a.jpg"}]
    result = asyncio.run(
        tools.handle_create_post(
            page=object(), title="제목", blocks=blocks, tags=["#맛집"], publish=False
        )
    )

    assert calls["title"] == "제목"
    assert calls["blocks"] == blocks
    assert calls["tags"] == ["#맛집"]
    assert calls["publish"] is False
    assert result["success"] is True
    assert result["images_uploaded"] == 1


def test_blocks_route_error_returns_dict(monkeypatch):
    from naver_blog_mcp.automation.post_actions import NaverBlogPostError

    async def fake_v2_raises(page, *, title, blocks, tags, publish):
        raise NaverBlogPostError("셀렉터 실패")

    monkeypatch.setattr(
        "naver_blog_mcp.automation.post_actions.create_blog_post_v2", fake_v2_raises
    )
    result = asyncio.run(
        tools.handle_create_post(
            page=object(), title="제목", blocks=[{"type": "text", "text": "x"}], publish=False
        )
    )
    assert result["success"] is False
    assert "셀렉터 실패" in result["message"]
