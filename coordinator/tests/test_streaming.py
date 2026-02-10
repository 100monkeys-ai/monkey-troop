import pytest
import asyncio
from streaming import is_streaming_request, stream_chat_completion

@pytest.mark.parametrize("input_data,expected", [
    ({"stream": True}, True),
    ({"stream": False}, False),
    ({}, False),
    ({"stream": None}, False),
    ({"stream": "true"}, False),
    ({"stream": 1}, False),
    ({"stream": True, "other": "value"}, True),
])
def test_is_streaming_request(input_data, expected):
    assert is_streaming_request(input_data) is expected

def test_stream_chat_completion_valid():
    async def mock_stream():
        yield b'{"message": "Hello"}\n'
        yield b'{"message": " world"}\n'

    async def run_test():
        stream = mock_stream()
        results = []
        async for chunk in stream_chat_completion(stream):
            results.append(chunk)

        assert results == [
            'data: {"message": "Hello"}\n\n',
            'data: {"message": " world"}\n\n',
            'data: [DONE]\n\n'
        ]

    asyncio.run(run_test())

def test_stream_chat_completion_multi_line_chunk():
    async def mock_stream():
        yield b'{"part1": 1}\n{"part2": 2}\n'

    async def run_test():
        stream = mock_stream()
        results = []
        async for chunk in stream_chat_completion(stream):
            results.append(chunk)

        assert results == [
            'data: {"part1": 1}\n\n',
            'data: {"part2": 2}\n\n',
            'data: [DONE]\n\n'
        ]

    asyncio.run(run_test())

def test_stream_chat_completion_malformed_json():
    async def mock_stream():
        yield b'{"valid": true}\n'
        yield b'invalid json\n'
        yield b'{"after": "error"}\n'

    async def run_test():
        stream = mock_stream()
        results = []
        async for chunk in stream_chat_completion(stream):
            results.append(chunk)

        assert results[0] == 'data: {"valid": true}\n\n'
        assert "Parse error" in results[1]
        assert results[2] == 'data: {"after": "error"}\n\n'
        assert results[3] == 'data: [DONE]\n\n'

    asyncio.run(run_test())

def test_stream_chat_completion_empty():
    async def mock_stream():
        if False:
            yield b''

    async def run_test():
        stream = mock_stream()
        results = []
        async for chunk in stream_chat_completion(stream):
            results.append(chunk)

        assert results == ['data: [DONE]\n\n']

    asyncio.run(run_test())
