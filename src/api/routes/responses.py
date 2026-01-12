"""
Responses Router - OpenAI Responses API Compatibility

This module implements the OpenAI Responses API endpoint for gpt-5.2-pro
and other models that use the newer Responses API format.

The Responses API is OpenAI's most advanced interface for generating model
responses, supporting stateful interactions and built-in tools.

Reference Documents:
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
"""

import logging
import time
import uuid
from typing import Any, AsyncGenerator, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from src.core.exceptions import ProviderError


# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Responses API Request Models
# =============================================================================


class ResponsesRequest(BaseModel):
    """
    OpenAI Responses API request model.
    
    The Responses API uses a different format than Chat Completions:
    - `input` instead of `messages` (can be string or array)
    - `instructions` instead of system message
    - Different response format with `output` array
    """
    
    model: str = Field(..., description="Model identifier")
    input: Union[str, list[dict[str, Any]]] = Field(
        ..., description="Text, image, or file inputs to the model"
    )
    instructions: Optional[str] = Field(
        default=None, description="System (developer) message"
    )
    max_output_tokens: Optional[int] = Field(
        default=None, description="Maximum tokens to generate"
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling"
    )
    stream: Optional[bool] = Field(default=False, description="Enable streaming")
    tools: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Tools available for the model"
    )
    tool_choice: Optional[Union[str, dict[str, Any]]] = Field(
        default=None, description="Tool selection strategy"
    )
    previous_response_id: Optional[str] = Field(
        default=None, description="Previous response ID for multi-turn"
    )
    store: Optional[bool] = Field(
        default=True, description="Whether to store the response"
    )
    metadata: Optional[dict[str, str]] = Field(
        default=None, description="Key-value metadata"
    )
    reasoning: Optional[dict[str, Any]] = Field(
        default=None, description="Reasoning configuration for o-series/gpt-5 models"
    )


# =============================================================================
# Responses API Response Models
# =============================================================================


class OutputTextContent(BaseModel):
    """Text content in output message."""
    type: str = "output_text"
    text: str
    annotations: list[Any] = Field(default_factory=list)


class OutputMessage(BaseModel):
    """Output message in the response."""
    type: str = "message"
    id: str
    status: str = "completed"
    role: str = "assistant"
    content: list[OutputTextContent]


class ResponsesUsage(BaseModel):
    """Token usage for Responses API."""
    input_tokens: int
    input_tokens_details: dict[str, int] = Field(default_factory=lambda: {"cached_tokens": 0})
    output_tokens: int
    output_tokens_details: dict[str, int] = Field(default_factory=lambda: {"reasoning_tokens": 0})
    total_tokens: int


class ReasoningConfig(BaseModel):
    """Reasoning configuration in response."""
    effort: Optional[str] = None
    summary: Optional[str] = None


class TextFormat(BaseModel):
    """Text format configuration."""
    type: str = "text"


class TextConfig(BaseModel):
    """Text configuration in response."""
    format: TextFormat = Field(default_factory=TextFormat)


class ResponsesResponse(BaseModel):
    """
    OpenAI Responses API response model.
    
    This format differs significantly from Chat Completions:
    - Has `output` array instead of `choices`
    - Includes `status`, `completed_at` fields
    - Different structure for usage information
    """
    
    id: str = Field(..., description="Response ID")
    object: str = Field(default="response", description="Object type")
    created_at: int = Field(..., description="Creation timestamp")
    status: str = Field(default="completed", description="Response status")
    completed_at: Optional[int] = Field(default=None, description="Completion timestamp")
    error: Optional[dict[str, Any]] = Field(default=None)
    incomplete_details: Optional[dict[str, Any]] = Field(default=None)
    instructions: Optional[str] = Field(default=None)
    max_output_tokens: Optional[int] = Field(default=None)
    model: str = Field(..., description="Model used")
    output: list[OutputMessage] = Field(..., description="Output messages")
    parallel_tool_calls: bool = Field(default=True)
    previous_response_id: Optional[str] = Field(default=None)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    store: bool = Field(default=True)
    temperature: float = Field(default=1.0)
    text: TextConfig = Field(default_factory=TextConfig)
    tool_choice: str = Field(default="auto")
    tools: list[Any] = Field(default_factory=list)
    top_p: float = Field(default=1.0)
    truncation: str = Field(default="disabled")
    usage: ResponsesUsage
    user: Optional[str] = Field(default=None)
    metadata: dict[str, str] = Field(default_factory=dict)


# =============================================================================
# Responses Service
# =============================================================================


class ResponsesService:
    """Service for handling Responses API requests.
    
    Routes requests to the appropriate provider:
    - OpenAI models (gpt-*) -> OpenAI Responses API
    - Anthropic models (claude-*) -> Anthropic Messages API (transformed)
    - DeepSeek models (deepseek-*) -> DeepSeek Chat API (transformed)
    """
    
    # Models that use the native OpenAI Responses API
    OPENAI_RESPONSES_MODELS = {
        "gpt-5.2-pro",
        "gpt-5.1-pro", 
        "gpt-5-pro",
        "o3",
        "o3-mini",
        "o1",
        "o1-mini",
        "o1-preview",
    }
    
    @classmethod
    def is_responses_api_model(cls, model: str) -> bool:
        """Check if a model uses the native OpenAI Responses API."""
        return model in cls.OPENAI_RESPONSES_MODELS or model.endswith("-pro")
    
    @classmethod
    def get_provider_type(cls, model: str) -> str:
        """Determine which provider to use for a model."""
        model_lower = model.lower()
        if model_lower.startswith("claude") or "claude" in model_lower:
            return "anthropic"
        if model_lower.startswith("deepseek") or "deepseek" in model_lower:
            return "deepseek"
        if model_lower.startswith("gemini"):
            return "google"
        return "openai"
    
    async def create_response(self, request: ResponsesRequest) -> ResponsesResponse:
        """
        Create a response, routing to the appropriate provider.
        """
        provider_type = self.get_provider_type(request.model)
        
        if provider_type == "anthropic":
            return await self._create_anthropic_response(request)
        elif provider_type == "deepseek":
            return await self._create_deepseek_response(request)
        elif provider_type == "google":
            return await self._create_google_response(request)
        else:
            return await self._create_openai_response(request)
    
    async def _create_openai_response(self, request: ResponsesRequest) -> ResponsesResponse:
        """
        Create a response using the OpenAI Responses API.
        
        This method calls the actual OpenAI /v1/responses endpoint.
        """
        from src.core.config import get_settings
        from src.providers.router import ProviderRouter
        import httpx
        
        settings = get_settings()
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        
        if not api_key:
            raise ProviderError("OpenAI API key not configured", provider="openai")
        
        # Resolve model aliases (e.g., "openai" -> "gpt-5.2")
        model = ProviderRouter.PROVIDER_DEFAULTS.get(request.model.lower(), request.model)
        
        # Models that don't support temperature (reasoning models)
        # GPT-5.2-pro and similar reasoning models don't allow temperature adjustment
        REASONING_MODELS = {"gpt-5.2-pro", "gpt-5-pro", "o1", "o1-pro", "o1-preview", "o1-mini"}
        is_reasoning_model = model in REASONING_MODELS or "-pro" in model
        
        # Build the request payload
        payload: dict[str, Any] = {
            "model": model,
            "input": request.input,
        }
        
        # Add optional parameters
        if request.instructions:
            payload["instructions"] = request.instructions
        if request.max_output_tokens:
            payload["max_output_tokens"] = request.max_output_tokens
        # Temperature not supported for reasoning models
        if request.temperature is not None and not is_reasoning_model:
            payload["temperature"] = request.temperature
        if request.top_p is not None and not is_reasoning_model:
            payload["top_p"] = request.top_p
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.previous_response_id:
            payload["previous_response_id"] = request.previous_response_id
        if request.store is not None:
            payload["store"] = request.store
        if request.metadata:
            payload["metadata"] = request.metadata
        if request.reasoning:
            payload["reasoning"] = request.reasoning
        
        # Call OpenAI Responses API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise ProviderError(
                    f"OpenAI Responses API error: {error_msg}",
                    provider="openai",
                    status_code=response.status_code,
                )
            
            data = response.json()
        
        # Transform to our response model
        return self._transform_response(data)
    
    async def _create_anthropic_response(self, request: ResponsesRequest) -> ResponsesResponse:
        """
        Create a response using the Anthropic Messages API.
        
        This method calls Anthropic's /v1/messages endpoint and transforms
        the response to the Responses API format.
        """
        from src.core.config import get_settings
        import httpx
        
        settings = get_settings()
        api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        
        if not api_key:
            raise ProviderError("Anthropic API key not configured", provider="anthropic")
        
        # Model alias mapping
        MODEL_ALIASES = {
            "claude-opus-4-5-20250514": "claude-opus-4-20250514",
            "claude-opus-4.5": "claude-opus-4-20250514",
            "claude-4-opus": "claude-opus-4-20250514",
        }
        model = MODEL_ALIASES.get(request.model, request.model)
        
        # Convert input to Anthropic messages format
        messages = []
        if isinstance(request.input, str):
            messages = [{"role": "user", "content": request.input}]
        elif isinstance(request.input, list):
            for item in request.input:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        # Handle content array format
                        text_parts = []
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "input_text":
                                text_parts.append(c.get("text", ""))
                            elif isinstance(c, str):
                                text_parts.append(c)
                        content = "\n".join(text_parts)
                    messages.append({"role": role, "content": content})
                elif isinstance(item, str):
                    messages.append({"role": "user", "content": item})
        
        # Build the request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_output_tokens or 4096,
        }
        
        # Add system message from instructions
        if request.instructions:
            payload["system"] = request.instructions
        
        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        
        # Call Anthropic Messages API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise ProviderError(
                    f"Anthropic API error: {error_msg}",
                    provider="anthropic",
                    status_code=response.status_code,
                )
            
            data = response.json()
        
        # Transform Anthropic response to Responses API format
        return self._transform_anthropic_response(data, model)
    
    def _transform_anthropic_response(self, data: dict[str, Any], model: str) -> ResponsesResponse:
        """Transform Anthropic Messages response to Responses API format."""
        # Extract text from content blocks
        text_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
        
        # Build output message
        output_messages = [
            OutputMessage(
                type="message",
                id=data.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
                status="completed" if data.get("stop_reason") == "end_turn" else "in_progress",
                role="assistant",
                content=[
                    OutputTextContent(
                        type="output_text",
                        text=text_content,
                        annotations=[],
                    )
                ],
            )
        ]
        
        # Parse usage
        usage_data = data.get("usage", {})
        usage = ResponsesUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            input_tokens_details={"cached_tokens": usage_data.get("cache_read_input_tokens", 0)},
            output_tokens=usage_data.get("output_tokens", 0),
            output_tokens_details={"reasoning_tokens": 0},
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )
        
        return ResponsesResponse(
            id=f"resp_{uuid.uuid4().hex[:24]}",
            object="response",
            created_at=int(time.time()),
            status="completed",
            completed_at=int(time.time()),
            error=None,
            incomplete_details=None,
            instructions=None,
            max_output_tokens=None,
            model=model,
            output=output_messages,
            parallel_tool_calls=True,
            previous_response_id=None,
            reasoning=ReasoningConfig(effort=None, summary=None),
            store=True,
            temperature=1.0,
            tool_choice="auto",
            tools=[],
            top_p=1.0,
            truncation="disabled",
            usage=usage,
            user=None,
            metadata={},
        )
    
    async def _create_deepseek_response(self, request: ResponsesRequest) -> ResponsesResponse:
        """
        Create a response using the DeepSeek Chat API.
        
        This method calls DeepSeek's /chat/completions endpoint and transforms
        the response to the Responses API format.
        """
        from src.core.config import get_settings
        import httpx
        
        settings = get_settings()
        api_key = settings.deepseek_api_key.get_secret_value() if settings.deepseek_api_key else ""
        
        if not api_key:
            raise ProviderError("DeepSeek API key not configured", provider="deepseek")
        
        # Model alias mapping
        MODEL_ALIASES = {
            "deepseek-api/deepseek-chat": "deepseek-chat",
            "deepseek": "deepseek-chat",
        }
        model = MODEL_ALIASES.get(request.model, request.model)
        
        # Convert input to OpenAI-compatible messages format
        messages = []
        
        # Add system message from instructions
        if request.instructions:
            messages.append({"role": "system", "content": request.instructions})
        
        if isinstance(request.input, str):
            messages.append({"role": "user", "content": request.input})
        elif isinstance(request.input, list):
            for item in request.input:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        # Handle content array format
                        text_parts = []
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "input_text":
                                text_parts.append(c.get("text", ""))
                            elif isinstance(c, str):
                                text_parts.append(c)
                        content = "\n".join(text_parts)
                    messages.append({"role": role, "content": content})
                elif isinstance(item, str):
                    messages.append({"role": "user", "content": item})
        
        # Build the request payload
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        
        # Add optional parameters
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        
        # Call DeepSeek Chat API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            
            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                raise ProviderError(
                    f"DeepSeek API error: {error_msg}",
                    provider="deepseek",
                    status_code=response.status_code,
                )
            
            data = response.json()
        
        # Transform DeepSeek response to Responses API format
        return self._transform_deepseek_response(data, model)
    
    def _transform_deepseek_response(self, data: dict[str, Any], model: str) -> ResponsesResponse:
        """Transform DeepSeek Chat Completions response to Responses API format."""
        # Extract message from choices
        text_content = ""
        choices = data.get("choices", [])
        if choices:
            text_content = choices[0].get("message", {}).get("content", "")
        
        # Build output message
        output_messages = [
            OutputMessage(
                type="message",
                id=f"msg_{uuid.uuid4().hex[:24]}",
                status="completed",
                role="assistant",
                content=[
                    OutputTextContent(
                        type="output_text",
                        text=text_content,
                        annotations=[],
                    )
                ],
            )
        ]
        
        # Parse usage
        usage_data = data.get("usage", {})
        usage = ResponsesUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            input_tokens_details={"cached_tokens": usage_data.get("prompt_cache_hit_tokens", 0)},
            output_tokens=usage_data.get("completion_tokens", 0),
            output_tokens_details={"reasoning_tokens": 0},
            total_tokens=usage_data.get("total_tokens", 0),
        )
        
        return ResponsesResponse(
            id=data.get("id", f"resp_{uuid.uuid4().hex[:24]}"),
            object="response",
            created_at=data.get("created", int(time.time())),
            status="completed",
            completed_at=int(time.time()),
            error=None,
            incomplete_details=None,
            instructions=None,
            max_output_tokens=None,
            model=model,
            output=output_messages,
            parallel_tool_calls=True,
            previous_response_id=None,
            reasoning=ReasoningConfig(effort=None, summary=None),
            store=True,
            temperature=1.0,
            tool_choice="auto",
            tools=[],
            top_p=1.0,
            truncation="disabled",
            usage=usage,
            user=None,
            metadata={},
        )
    
    async def _create_google_response(self, request: ResponsesRequest) -> ResponsesResponse:
        """
        Create a response using the Google Gemini API.
        
        This method calls Google's Generative AI API and transforms
        the response to the OpenAI Responses API format.
        """
        from src.core.config import get_settings
        import httpx
        
        settings = get_settings()
        api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
        
        if not api_key:
            raise ProviderError("Google/Gemini API key not configured (set GEMINI_API_KEY)", provider="google")
        
        model = request.model
        
        # Build Gemini-compatible content
        contents = []
        
        # Add system instruction if provided
        system_instruction = None
        if request.instructions:
            system_instruction = {"parts": [{"text": request.instructions}]}
        
        # Convert input to Gemini format
        if isinstance(request.input, str):
            contents.append({
                "role": "user",
                "parts": [{"text": request.input}]
            })
        elif isinstance(request.input, list):
            for item in request.input:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        # Handle content array format
                        text_parts = []
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "input_text":
                                text_parts.append(c.get("text", ""))
                            elif isinstance(c, str):
                                text_parts.append(c)
                        content = "\n".join(text_parts)
                    # Map roles: user->user, assistant->model
                    gemini_role = "model" if role == "assistant" else "user"
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]
                    })
                elif isinstance(item, str):
                    contents.append({
                        "role": "user",
                        "parts": [{"text": item}]
                    })
        
        # Build the request payload
        payload: dict[str, Any] = {
            "contents": contents,
        }
        
        # Add system instruction if present
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        
        # Add generation config
        generation_config: dict[str, Any] = {}
        if request.max_output_tokens:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.top_p is not None:
            generation_config["topP"] = request.top_p
        if generation_config:
            payload["generationConfig"] = generation_config
        
        # Call Google Gemini API
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        logger.info(f"Calling Google Gemini API: model={model}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                api_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
            )
            
            if response.status_code != 200:
                error_body = response.json() if response.content else {}
                error_msg = error_body.get("error", {}).get("message", response.text)
                logger.error(f"Google Gemini API error: {response.status_code} - {error_msg}")
                raise ProviderError(
                    f"Google API error ({response.status_code}): {error_msg}",
                    provider="google"
                )
            
            data = response.json()
        
        # Parse the response
        candidates = data.get("candidates", [])
        text_content = ""
        if candidates:
            first_candidate = candidates[0]
            content_parts = first_candidate.get("content", {}).get("parts", [])
            if content_parts:
                text_content = content_parts[0].get("text", "")
        
        # Build output messages in Responses API format
        output_messages = [
            OutputMessage(
                type="message",
                id=f"msg_{uuid.uuid4().hex[:24]}",
                status="completed",
                role="assistant",
                content=[
                    OutputTextContent(
                        type="output_text",
                        text=text_content,
                        annotations=[],
                    )
                ],
            )
        ]
        
        # Parse usage from metadata
        usage_metadata = data.get("usageMetadata", {})
        usage = ResponsesUsage(
            input_tokens=usage_metadata.get("promptTokenCount", 0),
            input_tokens_details={"cached_tokens": usage_metadata.get("cachedContentTokenCount", 0)},
            output_tokens=usage_metadata.get("candidatesTokenCount", 0),
            output_tokens_details={"reasoning_tokens": 0},
            total_tokens=usage_metadata.get("totalTokenCount", 0),
        )
        
        return ResponsesResponse(
            id=f"resp_{uuid.uuid4().hex[:24]}",
            object="response",
            created_at=int(time.time()),
            status="completed",
            completed_at=int(time.time()),
            error=None,
            incomplete_details=None,
            instructions=None,
            max_output_tokens=None,
            model=model,
            output=output_messages,
            parallel_tool_calls=True,
            previous_response_id=None,
            reasoning=ReasoningConfig(effort=None, summary=None),
            store=True,
            temperature=1.0,
            tool_choice="auto",
            tools=[],
            top_p=1.0,
            truncation="disabled",
            usage=usage,
            user=None,
            metadata={},
        )
    
    def _transform_response(self, data: dict[str, Any]) -> ResponsesResponse:
        """Transform OpenAI response to our model."""
        # Parse output messages
        output_messages = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                content_items = []
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        content_items.append(OutputTextContent(
                            type="output_text",
                            text=c.get("text", ""),
                            annotations=c.get("annotations", []),
                        ))
                output_messages.append(OutputMessage(
                    type="message",
                    id=item.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
                    status=item.get("status", "completed"),
                    role=item.get("role", "assistant"),
                    content=content_items,
                ))
        
        # Parse usage
        usage_data = data.get("usage", {})
        usage = ResponsesUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            input_tokens_details=usage_data.get("input_tokens_details", {"cached_tokens": 0}),
            output_tokens=usage_data.get("output_tokens", 0),
            output_tokens_details=usage_data.get("output_tokens_details", {"reasoning_tokens": 0}),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        
        # Parse reasoning config
        reasoning_data = data.get("reasoning", {})
        reasoning = ReasoningConfig(
            effort=reasoning_data.get("effort"),
            summary=reasoning_data.get("summary"),
        )
        
        return ResponsesResponse(
            id=data.get("id", f"resp_{uuid.uuid4().hex[:24]}"),
            object="response",
            created_at=data.get("created_at", int(time.time())),
            status=data.get("status", "completed"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            incomplete_details=data.get("incomplete_details"),
            instructions=data.get("instructions"),
            max_output_tokens=data.get("max_output_tokens"),
            model=data.get("model", ""),
            output=output_messages,
            parallel_tool_calls=data.get("parallel_tool_calls", True),
            previous_response_id=data.get("previous_response_id"),
            reasoning=reasoning,
            store=data.get("store", True),
            temperature=data.get("temperature", 1.0),
            tool_choice=data.get("tool_choice", "auto"),
            tools=data.get("tools", []),
            top_p=data.get("top_p", 1.0),
            truncation=data.get("truncation", "disabled"),
            usage=usage,
            user=data.get("user"),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# Dependency Injection
# =============================================================================

_responses_service: Optional[ResponsesService] = None


def get_responses_service() -> ResponsesService:
    """Get the responses service instance."""
    global _responses_service
    if _responses_service is None:
        _responses_service = ResponsesService()
    return _responses_service


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/v1", tags=["Responses"])


@router.post("/responses", response_model=None)
async def create_response(
    request: ResponsesRequest,
    service: ResponsesService = Depends(get_responses_service),
) -> ResponsesResponse | JSONResponse:
    """
    Create a model response using the OpenAI Responses API.
    
    This endpoint is for models that use the Responses API format instead
    of Chat Completions, such as gpt-5.2-pro.
    
    The Responses API provides:
    - Stateful interactions with previous_response_id
    - Built-in tools (web search, file search, etc.)
    - Different response format optimized for agents
    
    Args:
        request: Responses API request
        service: Injected responses service
        
    Returns:
        ResponsesResponse: The model response
        JSONResponse: Error response with appropriate status code
    """
    logger.info(f"Responses API request: model={request.model}")
    
    try:
        return await service.create_response(request)
    except ProviderError as e:
        logger.error(f"Provider error: {e.message}")
        return JSONResponse(
            status_code=e.status_code or 502,
            content={
                "error": {
                    "message": e.message,
                    "type": "provider_error",
                    "provider": e.provider,
                }
            },
        )
    except Exception as e:
        logger.exception(f"Unexpected error in Responses API: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                }
            },
        )
