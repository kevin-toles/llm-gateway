"""Bouncer test: if you're not on the list, you're not getting in."""
from unittest.mock import MagicMock
from src.providers.router import ProviderRouter, NoProviderError

# Create mock providers
mock_providers = {}
for name in ['anthropic', 'openai', 'google', 'deepseek', 'openrouter', 'inference']:
    mock = MagicMock()
    mock.name = name
    mock_providers[name] = mock

# Create router — loads from YAML
router = ProviderRouter(providers=mock_providers)

# ===== REGISTERED MODELS (must route) =====
tests = [
    # External owned — exact matches from providers.*.models
    ('deepseek-chat', 'deepseek', 'DeepSeek chat - THE BUG FIX'),
    ('deepseek-reasoner', 'deepseek', 'DeepSeek reasoner'),
    ('claude-opus-4.5', 'anthropic', 'Anthropic'),
    ('claude-sonnet-4.5', 'anthropic', 'Anthropic'),
    ('gpt-5.2', 'openai', 'OpenAI'),
    ('gpt-5-mini', 'openai', 'OpenAI'),
    ('gpt-5-nano', 'openai', 'OpenAI'),
    ('gemini-2.0-flash', 'google', 'Google'),
    ('gemini-1.5-pro', 'google', 'Google'),
    ('gemini-pro', 'google', 'Google'),
    # Local inference — exact matches from providers.inference.models
    ('phi-4', 'inference', 'Local model'),
    ('qwen2.5-7b', 'inference', 'Local model'),
    ('deepseek-r1-7b', 'inference', 'Local model'),
    ('codellama-7b-instruct', 'inference', 'Local model'),
    ('deepseek-coder-v2-lite', 'inference', 'Local model'),
    # Prefixes — aggregators
    ('openrouter/mistral-7b', 'openrouter', 'OpenRouter prefix'),
    ('deepseek-api/deepseek-chat', 'deepseek', 'DeepSeek prefix'),
    # Aliases — resolve to registered model, then lookup
    ('deepseek', 'deepseek', 'Alias: deepseek -> deepseek-chat'),
    ('reasoner', 'deepseek', 'Alias: reasoner -> deepseek-reasoner'),
    ('openai', 'openai', 'Alias: openai -> gpt-5.2'),
    ('claude', 'anthropic', 'Alias: claude'),
    ('gemini', 'google', 'Alias: gemini -> gemini-1.5-pro'),
]

passed = 0
failed = 0
for model, expected, desc in tests:
    try:
        provider = router.get_provider(model)
        actual = provider.name
        if actual == expected:
            print(f'  \u2705 {desc}: {model} -> {actual}')
            passed += 1
        else:
            print(f'  \u274c {desc}: {model} -> {actual} (expected {expected})')
            failed += 1
    except NoProviderError as e:
        print(f'  \u274c {desc}: {model} -> REJECTED (should have routed to {expected})')
        failed += 1

# ===== UNREGISTERED MODELS (must be rejected) =====
print()
unregistered = [
    'gpt-4o',           # Not on the list
    'claude-3.5-sonnet', # Not on the list
    'deepseek-v3',       # Not on the list
    'gemini-ultra',      # Not on the list
    'llama-70b',         # Not on the list
    'mistral-large-2',   # Not on the list
    'some-random-model', # Not on the list
]
for bad_model in unregistered:
    try:
        router.get_provider(bad_model)
        print(f'  \u274c {bad_model} got in but is NOT on the list')
        failed += 1
    except NoProviderError:
        print(f'  \u2705 {bad_model} rejected (not on the list)')
        passed += 1

print(f'\n=== {passed} passed, {failed} failed ===')
