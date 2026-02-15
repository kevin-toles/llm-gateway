"""
Tests for Streaming Support - WBS 2.2.3 Streaming Support

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- GUIDELINES p. 2149: Token generation and streaming patterns, iterator protocol
- GUIDELINES p. 2043: Reactive programming patterns with Observable streams
- Sinha (FastAPI): Coroutine functions emitting streams (Observable patterns)
- Newman (Microservices): Reactive Extensions patterns

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses
- ANTI_PATTERN_ANALYSIS §4.1: Cognitive complexity < 15 per function
"""

import pytest
import json
from fastapi.testclient import TestClient

from src.models.responses import (
    ChatCompletionChunk,
    ChunkChoice,
    ChunkDelta,
)


class TestStreamingResponseModels:
    """
    Test suite for streaming response models - WBS 2.2.3.1

    Pattern: Pydantic validation (Sinha pp. 193-195)
    """

    def test_chat_completion_chunk_model_exists(self):
        """WBS 2.2.3.1.1: ChatCompletionChunk model must exist."""
        from pydantic import BaseModel

        assert issubclass(ChatCompletionChunk, BaseModel)

    def test_chunk_delta_model_exists(self):
        """WBS 2.2.3.1.2: ChunkDelta model must exist."""
        from pydantic import BaseModel

        assert issubclass(ChunkDelta, BaseModel)

    def test_chunk_choice_model_exists(self):
        """WBS 2.2.3.1.3: ChunkChoice model must exist."""
        from pydantic import BaseModel

        assert issubclass(ChunkChoice, BaseModel)

    def test_chunk_has_correct_object_type(self):
        """WBS 2.2.3.1.4: ChatCompletionChunk.object must be 'chat.completion.chunk'."""
        chunk = ChatCompletionChunk(
            id="chatcmpl-test",
            created=1234567890,
            model="gpt-4",
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )
        assert chunk.object == "chat.completion.chunk"

    def test_chunk_delta_supports_role(self):
        """WBS 2.2.3.1.5: ChunkDelta must support 'role' field."""
        delta = ChunkDelta(role="assistant")
        assert delta.role == "assistant"
        assert delta.content is None

    def test_chunk_delta_supports_content(self):
        """WBS 2.2.3.1.6: ChunkDelta must support 'content' field."""
        delta = ChunkDelta(content="Hello")
        assert delta.content == "Hello"
        assert delta.role is None


class TestStreamingEndpoint:
    """Test suite for streaming endpoint - WBS 2.2.3.2"""

    # =========================================================================
    # WBS 2.2.3.2.1: Streaming Response Format
    # =========================================================================

    def test_streaming_request_accepted(self, client: TestClient):
        """
        WBS 2.2.3.2.1: POST /v1/chat/completions with stream=true must be accepted.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_streaming_returns_event_stream_content_type(self, client: TestClient):
        """
        WBS 2.2.3.2.2: Streaming response must have text/event-stream content type.

        Pattern: Server-Sent Events (SSE) format
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_streaming_chunks_use_sse_format(self, client: TestClient):
        """
        WBS 2.2.3.2.3: Streaming chunks must use 'data: ' prefix (SSE format).

        Pattern: Iterator protocol with yield (GUIDELINES p. 2149)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        # Each chunk should start with 'data: '
        lines = [line for line in content.split("\n") if line.strip()]
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(data_lines) > 0, "Response should contain SSE data lines"

    def test_streaming_first_chunk_has_role(self, client: TestClient):
        """
        WBS 2.2.3.2.4: First streaming chunk must include role='assistant'.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        # Parse first data chunk
        lines = [line for line in content.split("\n") if line.startswith("data: ")]
        assert len(lines) > 0

        first_data = lines[0].replace("data: ", "")
        if first_data != "[DONE]":
            chunk = json.loads(first_data)
            assert chunk["choices"][0]["delta"].get("role") == "assistant"

    def test_streaming_content_chunks_have_delta(self, client: TestClient):
        """
        WBS 2.2.3.2.5: Content chunks must have delta.content field.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        lines = [line for line in content.split("\n") if line.startswith("data: ")]

        # Find content chunks (not first role chunk, not [DONE])
        content_chunks = []
        for line in lines:
            data = line.replace("data: ", "")
            if data != "[DONE]":
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"]
                if "content" in delta and delta["content"]:
                    content_chunks.append(chunk)

        assert len(content_chunks) > 0, "Should have at least one content chunk"


class TestStreamTermination:
    """Test suite for stream termination - WBS 2.2.3.3"""

    # =========================================================================
    # WBS 2.2.3.3.1: [DONE] Marker
    # =========================================================================

    def test_streaming_ends_with_done_marker(self, client: TestClient):
        """
        WBS 2.2.3.3.1: Streaming must end with 'data: [DONE]' marker.

        Pattern: Stream completion signaling (OpenAI SSE protocol)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        lines = [line for line in content.split("\n") if line.startswith("data: ")]
        assert len(lines) > 0
        assert lines[-1] == "data: [DONE]"

    def test_streaming_last_chunk_has_finish_reason(self, client: TestClient):
        """
        WBS 2.2.3.3.2: Last content chunk must have finish_reason='stop'.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        lines = [line for line in content.split("\n") if line.startswith("data: ")]

        # Find last non-[DONE] chunk
        last_chunk = None
        for line in reversed(lines):
            data = line.replace("data: ", "")
            if data != "[DONE]":
                last_chunk = json.loads(data)
                break

        assert last_chunk is not None
        assert last_chunk["choices"][0]["finish_reason"] == "stop"

    def test_streaming_chunks_have_consistent_id(self, client: TestClient):
        """
        WBS 2.2.3.3.3: All chunks must have the same response ID.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        response = client.post("/v1/chat/completions", json=payload)
        content = response.text

        lines = [line for line in content.split("\n") if line.startswith("data: ")]

        chunk_ids = set()
        for line in lines:
            data = line.replace("data: ", "")
            if data != "[DONE]":
                chunk = json.loads(data)
                chunk_ids.add(chunk["id"])

        assert len(chunk_ids) == 1, "All chunks should have the same ID"


class TestStreamingService:
    """
    Test suite for streaming service methods - WBS 2.2.3.2

    Pattern: Cognitive complexity reduction (ANTI_PATTERN §4.1)
    Pattern: Observable patterns (Sinha)
    """

    @pytest.mark.asyncio
    async def test_chat_service_has_stream_completion_method(self):
        """
        WBS 2.2.3.2.6: ChatService must have stream_completion async generator.

        Pattern: Async generators with yield (GUIDELINES p. 2149)
        """
        from src.api.routes.chat import ChatService
        from src.models.requests import ChatCompletionRequest

        service = ChatService()
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )

        # Verify it's an async generator
        gen = service.stream_completion(request)
        assert hasattr(gen, "__anext__"), "stream_completion must be async generator"

        # Consume generator
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_completion_yields_chunks(self):
        """
        WBS 2.2.3.2.7: stream_completion must yield ChatCompletionChunk objects.
        """
        from src.api.routes.chat import ChatService
        from src.models.requests import ChatCompletionRequest
        from src.models.responses import ChatCompletionChunk

        service = ChatService()
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )

        async for chunk in service.stream_completion(request):
            assert isinstance(chunk, ChatCompletionChunk)


class TestNonStreamingStillWorks:
    """Test suite to ensure non-streaming still works - WBS 2.2.3 Regression"""

    def test_non_streaming_request_returns_full_response(self, client: TestClient):
        """
        WBS 2.2.3.4.1: Non-streaming requests must still return full response.

        Regression test: Ensure streaming changes don't break existing behavior.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["object"] == "chat.completion"
        assert "choices" in data
        assert "usage" in data

    def test_default_non_streaming_when_stream_omitted(self, client: TestClient):
        """
        WBS 2.2.3.4.2: Request without 'stream' field defaults to non-streaming.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            # No 'stream' field
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

        # Should return JSON, not event-stream
        assert "application/json" in response.headers.get("content-type", "")


# =============================================================================
# Fixtures - Following Repository Pattern for Test Doubles
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with chat router mounted.

    Pattern: FakeRepository (Architecture Patterns p. 157)
    """
    from fastapi import FastAPI
    from src.api.routes.chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router)

    return TestClient(app)
