"""
Request Models - WBS 2.2.2.2 Request/Response Models

This module contains Pydantic models for API request validation.

Reference Documents:
- GUIDELINES: FastAPI Pydantic validators (Sinha pp. 193-195)
- GUIDELINES: Tool/function calling (AI Engineering pp. 1463-1587)
- ANTI_PATTERN_ANALYSIS: §1.1 Optional types with explicit None

Anti-Patterns Avoided:
- §1.1: Optional fields use Optional[T] with explicit None default
- §3.1: Validation errors have clear context messages
"""

from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Message Models - WBS 2.2.2.2.9
# =============================================================================


class Message(BaseModel):
    """
    Chat message model.

    Pattern: Pydantic model with Literal type (Sinha p. 193)

    Attributes:
        role: Message role (system, user, assistant, tool)
        content: Message content (can be None for tool calls)
        name: Optional name for the message author
        tool_calls: Optional list of tool calls (for assistant messages)
        tool_call_id: Optional tool call ID (for tool messages)
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


# =============================================================================
# Tool Models - WBS 2.2.2.2.3
# Pattern: Tool/function calling (AI Engineering pp. 1463-1587)
# =============================================================================


class FunctionDefinition(BaseModel):
    """Function definition for tool calling."""

    name: str
    description: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None


class Tool(BaseModel):
    """
    Tool definition for function calling.

    Pattern: Tool calling (AI Engineering pp. 1463-1587)
    """

    type: Literal["function"] = "function"
    function: FunctionDefinition


# =============================================================================
# ChatCompletionRequest - WBS 2.2.2.2.7
# =============================================================================


class ChatCompletionRequest(BaseModel):
    """
    Chat completion request model.

    Pattern: Pydantic validation with Field validators (Sinha pp. 193-195)

    Required Fields:
        model: Model identifier
        messages: List of messages in the conversation

    Optional Fields:
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        top_p: Nucleus sampling parameter
        n: Number of completions to generate
        stream: Whether to stream responses
        stop: Stop sequences
        presence_penalty: Presence penalty (-2 to 2)
        frequency_penalty: Frequency penalty (-2 to 2)
        tools: List of tools available for function calling
        tool_choice: Tool selection strategy
        user: End-user identifier
        seed: Random seed for reproducibility
    """

    # Required fields
    model: str = Field(..., description="Model identifier")
    messages: list[Message] = Field(..., description="Conversation messages")

    # Optional fields - Pattern: Optional[T] with None (ANTI_PATTERN §1.1)
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description="Maximum tokens to generate"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling"
    )
    n: Optional[int] = Field(
        default=None, ge=1, le=128, description="Number of completions"
    )
    stream: Optional[bool] = Field(default=False, description="Enable streaming")
    stop: Optional[list[str] | str] = Field(default=None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Presence penalty"
    )
    frequency_penalty: Optional[float] = Field(
        default=None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    tools: Optional[list[Tool]] = Field(
        default=None, description="Tools for function calling"
    )
    tool_choice: Optional[str | dict[str, Any]] = Field(
        default=None, description="Tool selection strategy"
    )
    user: Optional[str] = Field(default=None, description="End-user identifier")
    seed: Optional[int] = Field(default=None, description="Random seed")
    # WBS 2.2.2.2.9: Session ID for conversation continuity
    # Reference: ARCHITECTURE.md - Session Manager stores conversation history
    session_id: Optional[str] = Field(
        default=None, description="Session ID for conversation continuity"
    )

    # ==========================================================================
    # Validators - Pattern: Field validators (Sinha p. 195)
    # ==========================================================================

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, v: list[Message]) -> list[Message]:
        """
        Validate that messages list is not empty.

        WBS 2.2.2.3.7: Messages array must not be empty.
        """
        if not v:
            raise ValueError("messages must not be empty")
        return v


# =============================================================================
# Session Models - WBS 2.2.3.2
# =============================================================================


class SessionCreateRequest(BaseModel):
    """
    Session creation request model.

    WBS 2.2.3.2.1: SessionCreateRequest model for POST /v1/sessions.

    Pattern: Pydantic validation (Sinha pp. 193-195)
    Pattern: Optional[T] with None (ANTI_PATTERN §1.1)

    Attributes:
        ttl_seconds: Optional session TTL in seconds (uses default from settings)
        context: Optional initial context data
    """

    ttl_seconds: Optional[int] = Field(
        default=None,
        ge=60,
        description="Session TTL in seconds (default from settings)",
    )
    context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Initial context data for the session",
    )
