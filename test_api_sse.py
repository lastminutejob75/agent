# tests/test_api_sse.py
import json
import pytest
from httpx import AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_chat_returns_conversation_id():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/chat", json={"message": "Quels sont vos horaires ?"})
        assert r.status_code == 200
        data = r.json()
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], str)
        assert len(data["conversation_id"]) > 10


@pytest.mark.asyncio
async def test_sse_stream_emits_events():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/chat", json={"message": "Quels sont vos horaires ?"})
        conv_id = r.json()["conversation_id"]

        async with ac.stream("GET", f"/stream/{conv_id}") as stream:
            assert stream.status_code == 200

            got_any = False
            async for line in stream.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    got_any = True
                    payload = json.loads(line.replace("data: ", "", 1))
                    assert payload["type"] in ("partial", "final", "transfer", "error")
                    if payload["type"] == "final":
                        assert "Source :" in payload.get("text", "")
                        break

            assert got_any is True
