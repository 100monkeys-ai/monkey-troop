import pytest
from domain.inference.streaming import (is_streaming_request,
                                        stream_chat_completion)


@pytest.mark.asyncio
async def test_stream_chat_completion():
    async def mock_response_stream():
        yield b'{"message": "Hello"}\n'
        yield b'{"message": " World"}\n'

    stream = stream_chat_completion(mock_response_stream())
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0] == 'data: {"message": "Hello"}\n\n'
    assert chunks[1] == 'data: {"message": " World"}\n\n'
    assert chunks[2] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_stream_chat_completion_parse_error():
    async def mock_response_stream():
        yield b"invalid json\n"

    stream = stream_chat_completion(mock_response_stream())
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    assert "error" in chunks[0]
    assert chunks[1] == "data: [DONE]\n\n"


def test_is_streaming_request():
    assert is_streaming_request({"stream": True}) is True
    assert is_streaming_request({"stream": False}) is False
    assert is_streaming_request({}) is False
