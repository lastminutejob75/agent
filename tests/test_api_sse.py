import asyncio
import json
import pytest
from httpx import AsyncClient

from backend.main import app, stream as sse_stream


@pytest.mark.asyncio
async def test_chat_returns_conversation_id():
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as ac:
        r = await ac.post("/chat", json={"message": "Quels sont vos horaires ?"})
        assert r.status_code == 200
        data = r.json()
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], str)
        assert len(data["conversation_id"]) > 10


@pytest.mark.asyncio
async def test_sse_stream_emits_events():
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as ac:
        r = await ac.post("/chat", json={"message": "Quels sont vos horaires ?"})
        conv_id = r.json()["conversation_id"]

    response = await sse_stream(conv_id)
    assert response.status_code == 200

    got_any = False
    body_iter = response.body_iterator
    try:
        for _ in range(20):
            try:
                chunk = await asyncio.wait_for(body_iter.__anext__(), timeout=5.0)
            except (asyncio.TimeoutError, StopAsyncIteration):
                break
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            for line in text.splitlines():
                if not line or not line.startswith("data: "):
                    continue
                got_any = True
                payload = json.loads(line.replace("data: ", "", 1))
                assert payload["type"] in ("partial", "final", "transfer", "error")
                if payload["type"] == "final":
                    assert "Source :" in payload.get("text", "")
                    return
    finally:
        await body_iter.aclose()

    assert got_any is True
    pytest.fail("Aucun événement final SSE reçu dans le délai imparti")
