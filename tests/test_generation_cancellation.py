import asyncio
from unittest.mock import Mock
import pytest
from src.llm.ollama_client import OllamaClient
from src.utils.operations import Operation, current_operation, CancelledError


def test_cancel_closes_inflight_generation():
    client = OllamaClient('test')
    closed = []
    async def blocked(messages):
        try:
            await asyncio.sleep(100)
        finally:
            closed.append(True)
    client._stream = blocked
    operation = Operation()
    token = current_operation.set(operation)
    async def scenario():
        asyncio.get_running_loop().call_later(.03, operation.cancelled.set)
        with pytest.raises(CancelledError):
            await client._cancellable([])
    try:
        asyncio.run(scenario())
    finally:
        current_operation.reset(token)
    assert closed == [True]


def test_partial_stream_is_not_returned(monkeypatch):
    import httpx
    class Response:
        def raise_for_status(self): pass
        async def aiter_lines(self):
            yield '{"message":{"content":"partial text"}}'
    class Context:
        async def __aenter__(self): return Response()
        async def __aexit__(self, *args): pass
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def stream(self, *args, **kwargs): return Context()
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: Client())
    with pytest.raises(RuntimeError, match='disconnected'):
        OllamaClient('test')._generate('system', 'question')
