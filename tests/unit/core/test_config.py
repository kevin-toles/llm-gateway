"""
Unit tests for src/core/config.py - Settings Class and Singleton.

WBS 2.1.2.1: Settings Class Implementation
WBS 2.1.2.2: Settings Singleton

TDD Approach: RED tests - all tests should fail initially.

Reference:
- ARCHITECTURE.md: Settings class structure with env_prefix="LLM_GATEWAY_"
- INTEGRATION_MAP.md: Microservice URLs and environment variables
- GUIDELINES: Sinha pp. 193-195 - Pydantic BaseSettings pattern
"""

import os
from unittest.mock import patch


# =============================================================================
# WBS 2.1.2.1: Settings Class Implementation
# =============================================================================


class TestSettingsClassExists:
    """Tests for WBS 2.1.2.1.2-3: Settings class creation."""

    def test_settings_module_exists(self):
        """
        WBS 2.1.2.1.2: Create src/core/config.py.
        
        Verifies the config module can be imported.
        """
        from src.core import config

        assert config is not None

    def test_settings_class_exists(self):
        """
        WBS 2.1.2.1.3: Implement Settings class extending BaseSettings.
        
        Verifies Settings class is defined.
        """
        from src.core.config import Settings

        assert Settings is not None

    def test_settings_extends_base_settings(self):
        """
        WBS 2.1.2.1.3: Settings extends BaseSettings.
        
        Verifies inheritance from pydantic_settings.BaseSettings.
        """
        from pydantic_settings import BaseSettings

        from src.core.config import Settings

        assert issubclass(Settings, BaseSettings)


class TestSettingsServiceConfiguration:
    """Tests for WBS 2.1.2.1.4: Service configuration."""

    def test_settings_has_service_name(self):
        """
        WBS 2.1.2.1.4: Add service configuration (name).
        
        Per ARCHITECTURE.md: service_name: str = "llm-gateway"
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "service_name")
        assert settings.service_name == "llm-gateway"

    def test_settings_has_port(self):
        """
        WBS 2.1.2.1.4: Add service configuration (port).
        
        Per ARCHITECTURE.md: port: int = 8080
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "port")
        assert settings.port == 8080

    def test_settings_has_environment(self):
        """
        WBS 2.1.2.1.4: Add service configuration (environment).
        
        Environment flag for dev/staging/production.
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "environment")
        assert settings.environment in ("development", "staging", "production")


class TestSettingsRedisConfiguration:
    """Tests for WBS 2.1.2.1.5: Redis configuration."""

    def test_settings_has_redis_url(self):
        """
        WBS 2.1.2.1.5: Add Redis configuration (url).
        
        Per ARCHITECTURE.md: redis_url: str = "redis://localhost:6379"
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "redis_url")
        assert settings.redis_url == "redis://localhost:6379"

    def test_settings_has_redis_pool_size(self):
        """
        WBS 2.1.2.1.5: Add Redis configuration (pool_size).
        
        Connection pool size for Redis.
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "redis_pool_size")
        assert isinstance(settings.redis_pool_size, int)
        assert settings.redis_pool_size > 0


class TestSettingsMicroserviceURLs:
    """Tests for WBS 2.1.2.1.6: Microservice URLs per INTEGRATION_MAP.md."""

    def test_settings_has_semantic_search_url(self):
        """
        WBS 2.1.2.1.6: Add microservice URLs.
        
        Per INTEGRATION_MAP.md: semantic-search at port 8081
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "semantic_search_url")
        assert "8081" in settings.semantic_search_url

    def test_settings_has_ai_agents_url(self):
        """
        WBS 2.1.2.1.6: Add microservice URLs.
        
        Per INTEGRATION_MAP.md: ai-agents at port 8082
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "ai_agents_url")
        assert "8082" in settings.ai_agents_url

    def test_settings_has_ollama_url(self):
        """
        WBS 2.1.2.1.6: Add microservice URLs.
        
        Per INTEGRATION_MAP.md: Ollama local at port 11434
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "ollama_url")
        assert "11434" in settings.ollama_url


class TestSettingsProviderAPIKeys:
    """Tests for WBS 2.1.2.1.7: Provider API keys."""

    def test_settings_has_anthropic_api_key(self):
        """
        WBS 2.1.2.1.7: Add provider API keys (anthropic).
        
        Per ARCHITECTURE.md: anthropic_api_key: str
        """
        from src.core.config import Settings

        # API keys should be configurable via environment
        with patch.dict(os.environ, {"LLM_GATEWAY_ANTHROPIC_API_KEY": "test-key"}):
            settings = Settings()
            assert hasattr(settings, "anthropic_api_key")

    def test_settings_has_openai_api_key(self):
        """
        WBS 2.1.2.1.7: Add provider API keys (openai).
        
        Per ARCHITECTURE.md: openai_api_key: str
        """
        from src.core.config import Settings

        # API keys should be configurable via environment
        with patch.dict(os.environ, {"LLM_GATEWAY_OPENAI_API_KEY": "test-key"}):
            settings = Settings()
            assert hasattr(settings, "openai_api_key")

    def test_api_keys_are_optional_with_defaults(self):
        """
        API keys should have empty string defaults for local dev without providers.
        """
        from src.core.config import Settings

        settings = Settings()
        # Should not raise - keys have defaults
        assert settings.anthropic_api_key is not None
        assert settings.openai_api_key is not None


class TestSettingsProviderDefaults:
    """Tests for WBS 2.1.2.1.8: Provider defaults."""

    def test_settings_has_default_provider(self):
        """
        WBS 2.1.2.1.8: Add provider defaults (default_provider).
        
        Per ARCHITECTURE.md: default_provider: str = "anthropic"
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "default_provider")
        assert settings.default_provider == "anthropic"

    def test_settings_has_default_model(self):
        """
        WBS 2.1.2.1.8: Add provider defaults (default_model).
        
        Per ARCHITECTURE.md: default_model: str = "claude-3-sonnet-20240229"
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "default_model")
        assert "claude" in settings.default_model.lower()


class TestSettingsRateLimiting:
    """Tests for WBS 2.1.2.1.9: Rate limiting configuration."""

    def test_settings_has_rate_limit_requests_per_minute(self):
        """
        WBS 2.1.2.1.9: Add rate limiting configuration.
        
        Per ARCHITECTURE.md: rate_limit_requests_per_minute: int = 60
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "rate_limit_requests_per_minute")
        assert settings.rate_limit_requests_per_minute == 60

    def test_settings_has_rate_limit_burst(self):
        """
        WBS 2.1.2.1.9: Add rate limiting configuration (burst).
        
        Burst limit for rate limiting.
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "rate_limit_burst")
        assert isinstance(settings.rate_limit_burst, int)


class TestSettingsSessionConfiguration:
    """Tests for WBS 2.1.2.1.10: Session configuration."""

    def test_settings_has_session_ttl(self):
        """
        WBS 2.1.2.1.10: Add session configuration (TTL).
        
        Session TTL in seconds.
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "session_ttl_seconds")
        assert isinstance(settings.session_ttl_seconds, int)
        assert settings.session_ttl_seconds > 0


class TestSettingsEnvPrefix:
    """Tests for WBS 2.1.2.1.11: Configure env_prefix."""

    def test_settings_has_env_prefix(self):
        """
        WBS 2.1.2.1.11: Configure env_prefix = "LLM_GATEWAY_".
        
        Per ARCHITECTURE.md: class Config: env_prefix = "LLM_GATEWAY_"
        """
        from src.core.config import Settings

        # Check model_config for pydantic v2
        assert hasattr(Settings, "model_config")
        config = Settings.model_config
        assert config.get("env_prefix") == "LLM_GATEWAY_"

    def test_settings_loads_from_prefixed_env_vars(self):
        """
        WBS 2.1.2.1.12: Settings loads from environment.
        
        Verify env_prefix works correctly.
        """
        with patch.dict(
            os.environ,
            {
                "LLM_GATEWAY_PORT": "9000",
                "LLM_GATEWAY_SERVICE_NAME": "test-gateway",
            },
        ):
            from src.core.config import Settings

            settings = Settings()
            assert settings.port == 9000
            assert settings.service_name == "test-gateway"


class TestSettingsValidation:
    """Tests for WBS 2.1.2.1.13: Settings validates required fields."""

    def test_port_must_be_positive(self):
        """
        WBS 2.1.2.1.13: Settings validates required fields.
        
        Port must be a positive integer.
        """
        import pytest
        from pydantic import ValidationError

        from src.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(port=-1)

    def test_port_must_be_valid_range(self):
        """
        WBS 2.1.2.1.13: Settings validates required fields.
        
        Port must be in valid range (1-65535).
        """
        import pytest
        from pydantic import ValidationError

        from src.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(port=70000)

    def test_redis_url_must_be_valid_url(self):
        """
        WBS 2.1.2.1.13: Settings validates required fields.
        
        Redis URL should be a valid URL format.
        """
        import pytest
        from pydantic import ValidationError

        from src.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(redis_url="not-a-url")

    def test_environment_must_be_valid_value(self):
        """
        WBS 2.1.2.1.13: Settings validates required fields.
        
        Environment must be development, staging, or production.
        """
        import pytest
        from pydantic import ValidationError

        from src.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(environment="invalid")


# =============================================================================
# WBS 2.1.2.2: Settings Singleton
# =============================================================================


class TestSettingsSingleton:
    """Tests for WBS 2.1.2.2: Settings Singleton with get_settings()."""

    def test_get_settings_function_exists(self):
        """
        WBS 2.1.2.2.1: Implement get_settings() function.
        
        Verifies function is defined in config module.
        """
        from src.core.config import get_settings

        assert callable(get_settings)

    def test_get_settings_returns_settings_instance(self):
        """
        WBS 2.1.2.2.1: get_settings returns Settings instance.
        """
        from src.core.config import Settings, get_settings

        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_returns_same_instance(self):
        """
        WBS 2.1.2.2.3: get_settings returns same instance (singleton).
        
        Verifies @lru_cache provides singleton behavior.
        """
        from src.core.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_get_settings_exported_from_core(self):
        """
        WBS 2.1.2.2.5: Export from src/core/__init__.py.
        """
        from src.core import get_settings

        assert callable(get_settings)

    def test_settings_exported_from_core(self):
        """
        WBS 2.1.2.2.5: Export Settings from src/core/__init__.py.
        """
        from src.core import Settings

        assert Settings is not None
