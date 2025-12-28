"""
LlamaCpp Provider - Local GGUF Model Inference with Metal GPU Acceleration

This module implements the LLMProvider interface for local GGUF models using
llama-cpp-python with Metal (Apple Silicon) GPU acceleration.

Reference Documents:
- ARCHITECTURE.md: providers/*.py pattern
- GUIDELINES pp. 2309: Timeout configuration and resource management
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Design Patterns:
- Ports and Adapters: LlamaCppProvider implements LLMProvider interface
- Model Manager: Handles loading/unloading of multiple models for memory efficiency
- Factory Pattern: Model loading with configurable parameters

Use Cases:
- Kitchen Brigade Scenario #2: Multi-model orchestration (debate/consensus)
- Local inference without external API calls
- Flash drive model storage for portability

Hardware Target:
- Apple M1 Pro 16GB RAM
- Metal GPU acceleration via llama-cpp-python
- Models stored on external flash drive
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional
import asyncio
import logging

from src.models.requests import ChatCompletionRequest
from src.models.responses import (
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    ChunkDelta,
    Usage,
)
from src.providers.base import LLMProvider


logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exception Classes
# NOTE: Named with LlamaCpp prefix to avoid shadowing Python builtins
# =============================================================================


class LlamaCppProviderError(Exception):
    """Base exception for LlamaCpp provider errors."""
    pass


class LlamaCppModelNotFoundError(LlamaCppProviderError):
    """Exception raised when model file not found."""
    pass


class LlamaCppModelLoadError(LlamaCppProviderError):
    """Exception raised when model fails to load."""
    pass


class LlamaCppInferenceError(LlamaCppProviderError):
    """Exception raised during inference."""
    pass


# =============================================================================
# Model Configuration
# =============================================================================


# Default model configurations for Kitchen Brigade Scenario #2
# These map model aliases to their GGUF files on the flash drive
DEFAULT_MODEL_CONFIGS = {
    # Primary models for 16GB RAM combos
    "phi-4": {
        "file": "phi-4-Q4_K_S.gguf",
        "context_length": 16384,
        "description": "Microsoft Phi-4 14B - General reasoning",
    },
    "deepseek-r1-7b": {
        "file": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
        "context_length": 32768,
        "description": "DeepSeek R1 Distill 7B - Chain-of-thought reasoning",
    },
    "qwen2.5-7b": {
        "file": "qwen2.5-7b-instruct-q4_k_m.gguf",
        "context_length": 32768,
        "description": "Qwen 2.5 7B Instruct - Code & general tasks",
    },
    # Smaller models for constrained scenarios
    "llama-3.2-3b": {
        "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "context_length": 8192,
        "description": "Llama 3.2 3B - Fast lightweight inference",
    },
    "phi-3-medium-128k": {
        "file": "Phi-3-medium-128k-instruct-Q4_K_M.gguf",
        "context_length": 131072,
        "description": "Phi-3 Medium 14B - Long context (128K)",
    },
}


# =============================================================================
# LlamaCpp Provider Implementation
# =============================================================================


class LlamaCppProvider(LLMProvider):
    """
    Local GGUF model provider using llama-cpp-python with Metal acceleration.
    
    This provider enables running local LLMs without external API dependencies.
    It supports dynamic model loading/unloading for memory-efficient multi-model
    orchestration on 16GB RAM systems.
    
    Pattern: Ports and Adapters (Hexagonal Architecture)
    Pattern: Resource management with explicit load/unload
    
    Args:
        models_dir: Directory containing GGUF model files
        n_gpu_layers: Number of layers to offload to GPU (-1 = all)
        default_context_length: Default context length if not in config
        model_configs: Custom model configurations (overrides defaults)
        
    Example:
        >>> provider = LlamaCppProvider(
        ...     models_dir="/Volumes/NO NAME/LLMs/models"
        ... )
        >>> await provider.load_model("phi-4")
        >>> response = await provider.complete(request)
        >>> await provider.unload_model("phi-4")
    """
    
    DEFAULT_MODELS_DIR = "/Volumes/NO NAME/LLMs/models"
    DEFAULT_CONTEXT_LENGTH = 4096
    DEFAULT_GPU_LAYERS = -1  # -1 = use all available (Metal)
    
    def __init__(
        self,
        models_dir: Optional[str] = None,
        n_gpu_layers: int = DEFAULT_GPU_LAYERS,
        default_context_length: int = DEFAULT_CONTEXT_LENGTH,
        model_configs: Optional[dict[str, dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize LlamaCpp provider.
        
        Args:
            models_dir: Path to directory containing model subdirectories
            n_gpu_layers: GPU layers to offload (-1 = all for Metal)
            default_context_length: Default n_ctx if not specified
            model_configs: Override default model configurations
        """
        self._models_dir = Path(models_dir or self.DEFAULT_MODELS_DIR)
        self._n_gpu_layers = n_gpu_layers
        self._default_context_length = default_context_length
        self._model_configs = model_configs or DEFAULT_MODEL_CONFIGS
        
        # Loaded models cache: model_alias -> Llama instance
        self._loaded_models: dict[str, Any] = {}
        
        # Track available models (discovered on init)
        self._available_models: list[str] = []
        self._discover_models()
        
        logger.info(
            f"LlamaCpp provider initialized. "
            f"Models dir: {self._models_dir}, "
            f"Available models: {self._available_models}"
        )
    
    def _discover_models(self) -> None:
        """Discover available models in the models directory."""
        self._available_models = []
        
        if not self._models_dir.exists():
            logger.warning(f"Models directory not found: {self._models_dir}")
            return
        
        for model_alias, config in self._model_configs.items():
            model_path = self._get_model_path(model_alias)
            if model_path and model_path.exists():
                self._available_models.append(model_alias)
                logger.debug(f"Discovered model: {model_alias} at {model_path}")
    
    def _get_model_path(self, model_alias: str) -> Optional[Path]:
        """
        Get the full path to a model's GGUF file.
        
        Args:
            model_alias: Model alias (e.g., "phi-4", "deepseek-r1-7b")
            
        Returns:
            Path to GGUF file, or None if not configured
        """
        config = self._model_configs.get(model_alias)
        if not config:
            return None
        
        # Models are stored in subdirectories: models/{alias}/{file}.gguf
        model_dir = self._models_dir / model_alias
        model_file = config.get("file")
        
        if not model_file:
            return None
        
        return model_dir / model_file
    
    async def load_model(
        self,
        model_alias: str,
        n_ctx: Optional[int] = None,
        force_reload: bool = False,
    ) -> bool:
        """
        Load a model into memory.
        
        This method loads a GGUF model using llama-cpp-python with Metal
        GPU acceleration. Models are cached for reuse.
        
        Args:
            model_alias: Model to load (e.g., "phi-4")
            n_ctx: Context length (overrides config default)
            force_reload: Force reload even if already loaded
            
        Returns:
            True if model loaded successfully
            
        Raises:
            LlamaCppModelNotFoundError: If model file not found
            LlamaCppModelLoadError: If model fails to load
        """
        if model_alias in self._loaded_models and not force_reload:
            logger.debug(f"Model {model_alias} already loaded")
            return True
        
        model_path = self._get_model_path(model_alias)
        if not model_path or not model_path.exists():
            raise LlamaCppModelNotFoundError(
                f"Model '{model_alias}' not found at {model_path}"
            )
        
        # Get context length from config or use default
        config = self._model_configs.get(model_alias, {})
        context_length = n_ctx or config.get("context_length", self._default_context_length)
        
        logger.info(f"Loading model {model_alias} from {model_path} (n_ctx={context_length})")
        
        try:
            # Import here to avoid startup cost if provider not used
            from llama_cpp import Llama
            
            # Run in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            llm = await loop.run_in_executor(
                None,
                lambda: Llama(
                    model_path=str(model_path),
                    n_ctx=context_length,
                    n_gpu_layers=self._n_gpu_layers,
                    verbose=False,
                )
            )
            
            self._loaded_models[model_alias] = llm
            logger.info(f"✅ Model {model_alias} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_alias}: {e}")
            raise LlamaCppModelLoadError(f"Failed to load {model_alias}: {e}") from e
    
    async def unload_model(self, model_alias: str) -> bool:
        """
        Unload a model from memory.
        
        Frees GPU/RAM resources for the specified model.
        
        Args:
            model_alias: Model to unload
            
        Returns:
            True if model was unloaded, False if not loaded
        """
        if model_alias in self._loaded_models:
            del self._loaded_models[model_alias]
            logger.info(f"✅ Model {model_alias} unloaded")
            return True
        return False
    
    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded models."""
        return list(self._loaded_models.keys())
    
    # =========================================================================
    # LLMProvider Interface Implementation
    # =========================================================================
    
    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).
        
        Implements LLMProvider.complete() for local GGUF models.
        
        Args:
            request: Chat completion request
            
        Returns:
            ChatCompletionResponse with generated text
            
        Raises:
            LlamaCppModelNotFoundError: If requested model not available
            LlamaCppInferenceError: If inference fails
        """
        model_alias = self._resolve_model_alias(request.model)
        
        # Auto-load model if not loaded
        if model_alias not in self._loaded_models:
            await self.load_model(model_alias)
        
        llm = self._loaded_models[model_alias]
        
        # Build messages for chat completion
        messages = self._build_messages(request)
        
        try:
            # Run inference in thread pool
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(
                None,
                lambda: llm.create_chat_completion(
                    messages=messages,
                    max_tokens=request.max_tokens or 512,
                    temperature=request.temperature or 0.7,
                    top_p=request.top_p or 0.95,
                    stop=request.stop if isinstance(request.stop, list) else (
                        [request.stop] if request.stop else None
                    ),
                )
            )
            
            return self._transform_response(output, request.model)
            
        except Exception as e:
            logger.error(f"Inference error with {model_alias}: {e}")
            raise LlamaCppInferenceError(f"Inference failed: {e}") from e
    
    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.
        
        Implements LLMProvider.stream() for local GGUF models.
        
        Args:
            request: Chat completion request
            
        Yields:
            ChatCompletionChunk objects as they are generated
        """
        model_alias = self._resolve_model_alias(request.model)
        
        # Auto-load model if not loaded
        if model_alias not in self._loaded_models:
            await self.load_model(model_alias)
        
        llm = self._loaded_models[model_alias]
        messages = self._build_messages(request)
        
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        
        try:
            # Create streaming generator
            stream_gen = llm.create_chat_completion(
                messages=messages,
                max_tokens=request.max_tokens or 512,
                temperature=request.temperature or 0.7,
                top_p=request.top_p or 0.95,
                stop=request.stop if isinstance(request.stop, list) else (
                    [request.stop] if request.stop else None
                ),
                stream=True,
            )
            
            for chunk_data in stream_gen:
                chunk = self._transform_chunk(
                    chunk_data, request.model, response_id, created
                )
                yield chunk
                # Yield control to event loop
                await asyncio.sleep(0)
                
        except Exception as e:
            logger.error(f"Streaming error with {model_alias}: {e}")
            raise LlamaCppInferenceError(f"Streaming failed: {e}") from e
    
    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.
        
        Args:
            model: Model identifier
            
        Returns:
            True if model is available (on disk)
        """
        model_alias = self._resolve_model_alias(model)
        return model_alias in self._available_models
    
    def get_supported_models(self) -> list[str]:
        """
        Get list of available models.
        
        Returns:
            List of model aliases that have GGUF files available
        """
        return self._available_models.copy()
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _resolve_model_alias(self, model: str) -> str:
        """
        Resolve model identifier to alias.
        
        Handles cases like:
        - "phi-4" -> "phi-4"
        - "local/phi-4" -> "phi-4"
        - "llamacpp:phi-4" -> "phi-4"
        """
        # Strip common prefixes
        for prefix in ["local/", "llamacpp:", "llamacpp/", "gguf/"]:
            if model.lower().startswith(prefix):
                model = model[len(prefix):]
        
        return model.lower()
    
    def _build_messages(
        self, request: ChatCompletionRequest
    ) -> list[dict[str, str]]:
        """Convert request messages to llama-cpp format."""
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content or "",
            })
        return messages
    
    def _transform_response(
        self, output: dict[str, Any], model: str
    ) -> ChatCompletionResponse:
        """Transform llama-cpp output to ChatCompletionResponse."""
        choice_data = output.get("choices", [{}])[0]
        message_data = choice_data.get("message", {})
        usage_data = output.get("usage", {})
        
        choice = Choice(
            index=0,
            message=ChoiceMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", ""),
                tool_calls=None,
            ),
            finish_reason=choice_data.get("finish_reason", "stop"),
            logprobs=None,
        )
        
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        
        return ChatCompletionResponse(
            id=output.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
            object="chat.completion",
            created=output.get("created", int(time.time())),
            model=model,
            choices=[choice],
            usage=usage,
            system_fingerprint=None,
        )
    
    def _transform_chunk(
        self,
        chunk_data: dict[str, Any],
        model: str,
        response_id: str,
        created: int,
    ) -> ChatCompletionChunk:
        """Transform llama-cpp stream chunk to ChatCompletionChunk."""
        choice_data = chunk_data.get("choices", [{}])[0]
        delta_data = choice_data.get("delta", {})
        
        delta = ChunkDelta(
            role=delta_data.get("role"),
            content=delta_data.get("content"),
            tool_calls=None,
        )
        
        chunk_choice = ChunkChoice(
            index=0,
            delta=delta,
            finish_reason=choice_data.get("finish_reason"),
            logprobs=None,
        )
        
        return ChatCompletionChunk(
            id=response_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[chunk_choice],
            system_fingerprint=None,
        )
