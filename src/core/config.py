"""
Core configuration module for LLM Gateway.

WBS 2.1.2.1: Settings Class Implementation
WBS 2.1.2.2: Settings Singleton

This module provides centralized configuration management using Pydantic Settings.
All configuration is loaded from environment variables with the LLM_GATEWAY_ prefix.

Reference:
- ARCHITECTURE.md: Settings class structure
- INTEGRATION_MAP.md: Microservice URLs and environment variables
- GUIDELINES: Sinha pp. 193-195 - Pydantic BaseSettings pattern
"""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Valid environment values."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    WBS 2.1.2.1.3: Settings class extending BaseSettings.
    
    All fields use the LLM_GATEWAY_ prefix for environment variables.
    Example: LLM_GATEWAY_PORT=8080
    
    Reference: ARCHITECTURE.md Configuration section
    """

    # =========================================================================
    # WBS 2.1.2.1.4: Service Configuration
    # =========================================================================
    service_name: str = Field(
        default="llm-gateway",
        description="Name of the service for logging and identification",
    )
    port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Port the service listens on",
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )

    # =========================================================================
    # WBS 2.1.2.1.5: Redis Configuration
    # =========================================================================
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for sessions and caching",
    )
    redis_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Size of the Redis connection pool",
    )

    # =========================================================================
    # WBS 2.1.2.1.6: Microservice URLs (per INTEGRATION_MAP.md)
    # =========================================================================
    semantic_search_url: str = Field(
        default="http://localhost:8081",
        description="URL of the semantic-search microservice",
    )
    ai_agents_url: str = Field(
        default="http://localhost:8082",
        description="URL of the ai-agents microservice",
    )
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="URL of the local Ollama instance",
    )
    inference_service_url: str = Field(
        default="http://host.docker.internal:8085",
        description="URL of the inference-service for local GGUF models",
        validation_alias="INFERENCE_SERVICE_URL",
    )

    # =========================================================================
    # WBS 3.2.3.2: Timeout Configuration
    # =========================================================================
    semantic_search_timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Timeout in seconds for semantic search service calls",
    )

    # =========================================================================
    # WBS 3.2.3.1: Circuit Breaker Configuration
    # =========================================================================
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of consecutive failures before circuit opens",
    )
    circuit_breaker_recovery_timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=600.0,
        description="Seconds to wait before attempting circuit recovery",
    )

    # =========================================================================
    # WBS 2.1.2.1.7: Provider API Keys
    # Pattern: SecretStr for sensitive values (GUIDELINES: security validation)
    # SecretStr masks values in logs/repr, use .get_secret_value() to access
    # 
    # Note: validation_alias allows these to be set via standard env var names
    # (OPENAI_API_KEY) or prefixed names (LLM_GATEWAY_OPENAI_API_KEY)
    # =========================================================================
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Anthropic API key for Claude models",
        validation_alias="ANTHROPIC_API_KEY",
    )
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenAI API key for GPT models",
        validation_alias="OPENAI_API_KEY",
    )
    openrouter_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="OpenRouter API key for Qwen and other models (POC for local LLMs)",
        validation_alias="OPENROUTER_API_KEY",
    )
    deepseek_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="DeepSeek API key for Reasoner and other models",
        validation_alias="DEEPSEEK_API_KEY",
    )
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Google Gemini API key for Gemini models",
        validation_alias="GEMINI_API_KEY",
    )

    # =========================================================================
    # LlamaCpp Local Model Configuration
    # For Kitchen Brigade Scenario #2: Multi-model orchestration
    # =========================================================================
    llamacpp_enabled: bool = Field(
        default=False,
        description="Enable LlamaCpp provider for local GGUF models",
    )
    llamacpp_models_dir: str = Field(
        default="/Users/kevintoles/POC/ai-models/models",
        description="Directory containing GGUF model files",
    )
    llamacpp_gpu_layers: int = Field(
        default=-1,
        ge=-1,
        description="GPU layers to offload (-1 = all for Metal)",
    )

    # =========================================================================
    # WBS 2.1.2.1.8: Provider Defaults
    # =========================================================================
    default_provider: str = Field(
        default="anthropic",
        description="Default LLM provider to use",
    )
    default_model: str = Field(
        default="claude-3-sonnet-20240229",
        description="Default model to use for completions",
    )

    # =========================================================================
    # WBS 2.1.2.1.9: Rate Limiting Configuration
    # =========================================================================
    rate_limit_requests_per_minute: int = Field(
        default=60,
        ge=1,
        description="Maximum requests per minute per client",
    )
    rate_limit_burst: int = Field(
        default=10,
        ge=1,
        description="Burst limit for rate limiting",
    )

    # =========================================================================
    # WBS 2.1.2.1.10: Session Configuration
    # =========================================================================
    session_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="Session time-to-live in seconds",
    )

    # =========================================================================
    # WBS-PS5: Memory and Backpressure Configuration
    # =========================================================================
    memory_threshold_mb: int = Field(
        default=1024,
        ge=256,
        description="Memory threshold in MB - requests rejected above this",
    )
    memory_soft_limit_percent: float = Field(
        default=0.8,
        ge=0.5,
        le=1.0,
        description="Soft limit as percentage of threshold - starts load shedding",
    )
    max_concurrent_requests: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum concurrent requests (backpressure semaphore)",
    )
    queue_warning_threshold: int = Field(
        default=30,
        ge=1,
        description="Queue depth that triggers warning logs",
    )

    # =========================================================================
    # WBS 2.1.2.1.11: Environment Prefix Configuration
    # =========================================================================
    model_config = {
        "env_prefix": "LLM_GATEWAY_",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # =========================================================================
    # WBS 2.1.2.1.15: Field Validators
    # =========================================================================
    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "staging", "production"}
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v


# =============================================================================
# WBS 2.1.2.2: Settings Singleton
# =============================================================================


@lru_cache
def get_settings() -> Settings:
    """
    Get the application settings singleton.
    
    WBS 2.1.2.2.1-2: Implement get_settings() function with @lru_cache.
    
    Uses functools.lru_cache to ensure only one Settings instance is created.
    This provides singleton behavior without global state.
    
    Returns:
        Settings: The application settings instance.
    """
    return Settings()
