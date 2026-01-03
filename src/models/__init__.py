"""Models Package - WBS 2.2.2.2, WBS 2.2.3.2 Request/Response Models.

This package contains Pydantic models for API request/response validation.

Reference Documents:
- GUIDELINES: FastAPI Pydantic validators (Sinha pp. 193-195)
- ANTI_PATTERN_ANALYSIS: Section 1.1 Optional types with explicit None
"""

from src.models.requests import ChatCompletionRequest, Message, SessionCreateRequest, Tool
from src.models.responses import (
    ChatCompletionChunk,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    ChunkDelta,
    SessionResponse,
    Usage,
)
from src.models.tools import (
    ToolDefinition,
    ToolExecuteRequest,
    ToolExecuteResponse,
)

__all__ = [
    # Requests
    "ChatCompletionRequest",
    "Message",
    "SessionCreateRequest",
    "Tool",
    # Responses
    "ChatCompletionChunk",
    "ChatCompletionResponse",
    "Choice",
    "ChoiceMessage",
    "ChunkChoice",
    "ChunkDelta",
    "SessionResponse",
    "Usage",
    # Tools
    "ToolDefinition",
    "ToolExecuteRequest",
    "ToolExecuteResponse",
]
