"""
Models Router - WBS 2.2.5 Model Discovery Endpoint

This module implements the OpenAI-compatible models endpoint for discovering
available models from all registered providers.

Reference Documents:
- OpenAI API Reference: GET /v1/models
- GUIDELINES: REST constraints (Buelta pp. 92-93)
"""

import time
from typing import Any

from fastapi import APIRouter, Depends

from src.providers.router import ProviderRouter


# =============================================================================
# Router - WBS 2.2.5
# =============================================================================

router = APIRouter(prefix="/v1", tags=["Models"])


# =============================================================================
# Dependencies
# =============================================================================

def get_provider_router() -> ProviderRouter:
    """Get the provider router instance.
    
    Returns:
        ProviderRouter: The configured provider router.
    """
    from src.api.routes.chat import get_chat_service
    return get_chat_service()._router


# =============================================================================
# Models Endpoint - OpenAI Compatible
# =============================================================================


@router.get("/models")
async def list_models(
    provider_router: ProviderRouter = Depends(get_provider_router),
) -> dict[str, Any]:
    """
    List all available models.
    
    OpenAI-compatible endpoint that returns models from all registered providers.
    
    Returns:
        Dictionary with 'object' and 'data' fields containing model info.
    
    Example Response:
        {
            "object": "list",
            "data": [
                {
                    "id": "gpt-5.2-2025-12-11",
                    "object": "model",
                    "created": 1735257600,
                    "owned_by": "openai"
                },
                ...
            ]
        }
    """
    models_by_provider = provider_router.list_available_models_by_provider()
    
    model_list = []
    created_timestamp = int(time.time())
    
    for provider_name, models in models_by_provider.items():
        for model_id in models:
            model_list.append({
                "id": model_id,
                "object": "model",
                "created": created_timestamp,
                "owned_by": provider_name,
            })
    
    return {
        "object": "list",
        "data": model_list,
    }


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    provider_router: ProviderRouter = Depends(get_provider_router),
) -> dict[str, Any]:
    """
    Get details about a specific model.
    
    Args:
        model_id: The model identifier (e.g., "gpt-5.2-2025-12-11").
    
    Returns:
        Model details dictionary.
    """
    models_by_provider = provider_router.list_available_models_by_provider()
    
    for provider_name, models in models_by_provider.items():
        if model_id in models:
            return {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": provider_name,
            }
    
    return {
        "error": {
            "message": f"Model '{model_id}' not found",
            "type": "invalid_request_error",
        }
    }


@router.get("/providers")
async def list_providers(
    provider_router: ProviderRouter = Depends(get_provider_router),
) -> dict[str, Any]:
    """
    List all registered providers and their models.
    
    Non-standard endpoint for debugging/admin purposes.
    
    Returns:
        Dictionary mapping provider names to their available models.
    """
    return {
        "object": "provider_list",
        "providers": provider_router.list_available_models_by_provider(),
        "provider_names": provider_router.get_provider_names(),
    }
