"""
Response Models - WBS 2.2.2.2, WBS 2.2.3 Request/Response Models

This module contains Pydantic models for API response serialization.

Reference Documents:
- GUIDELINES: FastAPI Pydantic validators (Sinha pp. 193-195)
- GUIDELINES: OpenAI API compatibility patterns
- GUIDELINES p. 2149: Token generation and streaming patterns

Anti-Patterns Avoided:
- §1.1: Optional fields use Optional[T] with explicit None default
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# Usage Model - WBS 2.2.2.2.11
# =============================================================================


class Usage(BaseModel):
    """
    Token usage statistics.

    Attributes:
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
    """

    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens")


# =============================================================================
# Choice Message - Part of Choice model
# =============================================================================


class ChoiceMessage(BaseModel):
    """
    Message within a choice response.

    Attributes:
        role: Message role (always 'assistant' for completions)
        content: Response content (can be None for tool calls)
        tool_calls: Optional list of tool calls
    """

    role: str = Field(default="assistant", description="Message role")
    content: Optional[str] = Field(default=None, description="Response content")
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Tool calls"
    )


# =============================================================================
# Choice Model - WBS 2.2.2.2.10
# =============================================================================


class Choice(BaseModel):
    """
    A single completion choice.

    Pattern: OpenAI API response format

    Attributes:
        index: Index of this choice
        message: The completion message
        finish_reason: Why the completion stopped
        logprobs: Optional log probabilities
    """

    index: int = Field(..., description="Choice index")
    message: ChoiceMessage = Field(..., description="Completion message")
    finish_reason: Optional[str] = Field(
        default=None, description="Completion stop reason"
    )
    logprobs: Optional[dict[str, Any]] = Field(
        default=None, description="Log probabilities"
    )


# =============================================================================
# ChatCompletionResponse - WBS 2.2.2.2.8
# =============================================================================


class ChatCompletionResponse(BaseModel):
    """
    Chat completion response model.

    Pattern: OpenAI API compatibility

    Attributes:
        id: Unique response identifier
        object: Object type (always 'chat.completion')
        created: Unix timestamp of creation
        model: Model used for completion
        choices: List of completion choices
        usage: Token usage statistics
        system_fingerprint: Optional system fingerprint
    """

    id: str = Field(..., description="Response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: list[Choice] = Field(..., description="Completion choices")
    usage: Usage = Field(..., description="Token usage")
    system_fingerprint: Optional[str] = Field(
        default=None, description="System fingerprint"
    )


# =============================================================================
# Streaming Response Models - WBS 2.2.3.1
# Pattern: Token generation and streaming (GUIDELINES p. 2149)
# =============================================================================


class ChunkDelta(BaseModel):
    """
    Delta content within a streaming chunk.

    WBS 2.2.3.1.2: ChunkDelta model for incremental content.

    Pattern: Iterator protocol with yield (GUIDELINES p. 2149)

    Attributes:
        role: Message role (only in first chunk)
        content: Incremental content piece
        tool_calls: Optional incremental tool calls
    """

    role: Optional[str] = Field(default=None, description="Message role")
    content: Optional[str] = Field(default=None, description="Content delta")
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Tool calls delta"
    )


class ChunkChoice(BaseModel):
    """
    A single choice within a streaming chunk.

    WBS 2.2.3.1.3: ChunkChoice model for streaming.

    Attributes:
        index: Choice index
        delta: The incremental content
        finish_reason: Why streaming stopped (only in last chunk)
        logprobs: Optional log probabilities
    """

    index: int = Field(..., description="Choice index")
    delta: ChunkDelta = Field(..., description="Incremental content")
    finish_reason: Optional[str] = Field(
        default=None, description="Completion stop reason"
    )
    logprobs: Optional[dict[str, Any]] = Field(
        default=None, description="Log probabilities"
    )


class ChatCompletionChunk(BaseModel):
    """
    Streaming chunk response model.

    WBS 2.2.3.1.1: ChatCompletionChunk model for SSE streaming.

    Pattern: Observable patterns with async generators (Sinha)

    Attributes:
        id: Unique response identifier (same for all chunks)
        object: Object type (always 'chat.completion.chunk')
        created: Unix timestamp of creation
        model: Model used for completion
        choices: List of chunk choices
        system_fingerprint: Optional system fingerprint
    """

    id: str = Field(..., description="Response ID")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: list[ChunkChoice] = Field(..., description="Chunk choices")
    system_fingerprint: Optional[str] = Field(
        default=None, description="System fingerprint"
    )
