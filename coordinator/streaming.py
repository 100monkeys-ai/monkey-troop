"""Streaming utilities for SSE (Server-Sent Events) responses."""

from typing import AsyncIterator
import json


async def stream_chat_completion(response_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
    """
    Convert streaming response to SSE format.

    Yields SSE-formatted chunks: data: {...}\n\n
    """
    async for chunk in response_stream:
        # Parse chunk (assuming JSON lines format from Ollama)
        try:
            # Ollama sends newline-delimited JSON
            for line in chunk.decode("utf-8").strip().split("\n"):
                if line:
                    data = json.loads(line)
                    # Convert to SSE format
                    sse_data = f"data: {json.dumps(data)}\n\n"
                    yield sse_data
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            # Log error but continue streaming
            error_data = {"error": f"Parse error: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
            continue

    # Send done signal
    yield "data: [DONE]\n\n"


def is_streaming_request(request_data: dict) -> bool:
    """Check if request asks for streaming response."""
    return request_data.get("stream", False) is True
