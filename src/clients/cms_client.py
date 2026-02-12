"""
CMS Client - WBS-CMS11.6: CMSClient Implementation

This module provides the client for communicating with the Context Management Service.

Reference Documents:
- WBS_CONTEXT_MANAGEMENT_SERVICE.md: CMS11 Acceptance Criteria
- Context_Management_Service_Architecture.md: API Contract

Acceptance Criteria Covered:
- AC-11.1: Gateway routes Tier 2+ requests to CMS
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel


logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class CMSProcessResult(BaseModel):
    """Result from CMS /v1/context/process endpoint.
    
    Field names match the CMS ProcessResponse schema:
    - final_tokens (not optimized_tokens) — token count after processing
    - optimized_text is Optional — CMS returns None when chunking
    """
    
    optimized_text: Optional[str] = None
    original_tokens: int
    final_tokens: int
    compression_ratio: float
    was_chunked: bool = False
    strategies_applied: list[str] = []
    processing_time_ms: float = 0.0
    glossary_version: int = 0
    chunks: Optional[list["CMSChunk"]] = None
    fidelity_validated: bool = False
    fidelity_passed: Optional[bool] = None
    rolled_back: bool = False


class CMSValidateResult(BaseModel):
    """Result from CMS token validation."""
    
    token_count: int
    context_limit: int
    utilization: float


class CMSChunk(BaseModel):
    """A chunk from CMS chunking."""
    
    chunk_id: str
    sequence: int
    content: str
    token_count: int
    start_offset: int = 0
    end_offset: int = 0
    overlap_with_previous: int = 0
    overlap_with_next: int = 0


class CMSError(Exception):
    """Exception raised when CMS call fails."""
    
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# =============================================================================
# CMSClient
# =============================================================================


class CMSClient:
    """
    Client for Context Management Service.
    
    Provides methods for:
    - Health checking
    - Token validation (count only)
    - Full processing (optimize + optional chunking)
    - Chunking large texts
    
    Usage:
        async with CMSClient("http://localhost:8086") as client:
            result = await client.process("long text...", model="qwen3-8b")
    """
    
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
    ):
        """
        Initialize CMS client.
        
        Args:
            base_url: Base URL of CMS (e.g., "http://localhost:8086")
            timeout_seconds: Request timeout in seconds (default: 5.0)
        """
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "CMSClient":
        """Enter async context - create HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - close HTTP client."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client
    
    async def health_check(self) -> bool:
        """
        Check if CMS is healthy.
        
        Returns:
            True if CMS is healthy, False otherwise
        """
        try:
            client = self._ensure_client()
            response = await client.get("/health")
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"CMS health check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"CMS health check error: {e}")
            return False
    
    async def process(
        self,
        text: str,
        model: str,
        conversation_id: Optional[str] = None,
        optimization_config: Optional[dict] = None,
        validate_fidelity: bool = False,
        fidelity_anchors: Optional[list[str]] = None,
    ) -> CMSProcessResult:
        """
        Process text through CMS (optimize, optionally chunk).
        
        Args:
            text: The text to process
            model: Target model (e.g., "qwen3-8b")
            conversation_id: Optional conversation ID for glossary
            optimization_config: Optional optimization configuration
            validate_fidelity: Whether to validate semantic fidelity
            fidelity_anchors: Optional anchors to validate
            
        Returns:
            CMSProcessResult with optimized text and metrics
            
        Raises:
            CMSError: If CMS call fails
        """
        client = self._ensure_client()
        
        payload = {
            "text": text,
            "model": model,
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        if optimization_config:
            payload["optimization_config"] = optimization_config
        
        if validate_fidelity:
            payload["validate_fidelity"] = validate_fidelity
        
        if fidelity_anchors:
            payload["fidelity_anchors"] = fidelity_anchors
        
        try:
            response = await client.post("/v1/context/process", json=payload)
            
            if response.status_code != 200:
                raise CMSError(
                    message=f"CMS process failed: {response.text}",
                    status_code=response.status_code,
                )
            
            return CMSProcessResult(**response.json())
            
        except httpx.HTTPError as e:
            raise CMSError(message=str(e), status_code=0) from e
    
    async def validate(
        self,
        text: str,
        model: str,
    ) -> CMSValidateResult:
        """
        Validate text (token count only, no optimization).
        
        Args:
            text: The text to validate
            model: Target model for token counting
            
        Returns:
            CMSValidateResult with token metrics
            
        Raises:
            CMSError: If CMS call fails
        """
        client = self._ensure_client()
        
        payload = {
            "text": text,
            "model": model,
        }
        
        try:
            response = await client.post("/v1/context/validate", json=payload)
            
            if response.status_code != 200:
                raise CMSError(
                    message=f"CMS validate failed: {response.text}",
                    status_code=response.status_code,
                )
            
            return CMSValidateResult(**response.json())
            
        except httpx.HTTPError as e:
            raise CMSError(message=str(e), status_code=0) from e
    
    async def chunk(
        self,
        text: str,
        model: str,
        overlap_ratio: float = 0.1,
    ) -> list[CMSChunk]:
        """
        Chunk text into model-sized pieces.
        
        Args:
            text: The text to chunk
            model: Target model for context limits
            overlap_ratio: Overlap between chunks (default: 0.1)
            
        Returns:
            List of CMSChunk objects
            
        Raises:
            CMSError: If CMS call fails
        """
        client = self._ensure_client()
        
        payload = {
            "text": text,
            "model": model,
            "overlap_ratio": overlap_ratio,
        }
        
        try:
            response = await client.post("/v1/context/chunk", json=payload)
            
            if response.status_code != 200:
                raise CMSError(
                    message=f"CMS chunk failed: {response.text}",
                    status_code=response.status_code,
                )
            
            data = response.json()
            return [CMSChunk(**c) for c in data.get("chunks", [])]
            
        except httpx.HTTPError as e:
            raise CMSError(message=str(e), status_code=0) from e


# =============================================================================
# Dependency Injection
# =============================================================================

_cms_client: Optional[CMSClient] = None


def get_cms_client() -> Optional[CMSClient]:
    """
    Get the CMS client singleton.
    
    Returns:
        CMSClient instance or None if not configured
    """
    global _cms_client
    
    if _cms_client is None:
        from src.core.config import get_settings
        settings = get_settings()
        
        if hasattr(settings, "cms_url") and settings.cms_url:
            timeout = getattr(settings, "cms_timeout_seconds", 5.0)
            _cms_client = CMSClient(
                base_url=settings.cms_url,
                timeout_seconds=timeout,
            )
    
    return _cms_client


def set_cms_client(client: Optional[CMSClient]):
    """
    Set the CMS client (for testing).
    
    Args:
        client: CMSClient instance or None
    """
    global _cms_client
    _cms_client = client


def _reset_cms_client():
    """Reset CMS client (for testing)."""
    global _cms_client
    _cms_client = None
