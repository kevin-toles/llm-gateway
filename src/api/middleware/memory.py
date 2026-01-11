"""
Memory Tracking and Backpressure Middleware - WBS-PS5

This module implements OOM prevention through:
1. Memory profiling/monitoring - track current memory usage
2. Backpressure - reject requests when memory exceeds threshold or concurrent requests exceed limit
3. Memory metrics exposed via /health endpoint

Reference: PLATFORM_STABILITY_WBS.md - WBS-PS5: OOM Prevention for llm-gateway

Acceptance Criteria:
- llm-gateway memory usage stays below threshold
- Backpressure prevents request pileup
"""

import asyncio
import gc
import logging
import os
import resource
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


# =============================================================================
# Memory Configuration
# =============================================================================

# Memory threshold (in MB) - reject requests if exceeded
# Default: 1024 MB (1 GB), configurable via LLM_GATEWAY_MEMORY_THRESHOLD_MB
MEMORY_THRESHOLD_MB = int(os.getenv("LLM_GATEWAY_MEMORY_THRESHOLD_MB", "1024"))

# Soft limit threshold (percentage of hard limit) - start shedding load
MEMORY_SOFT_LIMIT_PERCENT = float(os.getenv("LLM_GATEWAY_MEMORY_SOFT_LIMIT_PERCENT", "0.8"))

# Maximum concurrent requests (backpressure)
MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_GATEWAY_MAX_CONCURRENT_REQUESTS", "50"))

# Queue depth warning threshold
QUEUE_WARNING_THRESHOLD = int(os.getenv("LLM_GATEWAY_QUEUE_WARNING_THRESHOLD", "30"))


# =============================================================================
# Memory Metrics Tracking
# =============================================================================

@dataclass
class MemoryMetrics:
    """Current memory usage metrics."""
    
    rss_mb: float = 0.0  # Resident Set Size (actual physical memory)
    vms_mb: float = 0.0  # Virtual Memory Size
    peak_mb: float = 0.0  # Peak memory usage since start
    threshold_mb: float = MEMORY_THRESHOLD_MB
    soft_limit_mb: float = MEMORY_THRESHOLD_MB * MEMORY_SOFT_LIMIT_PERCENT
    usage_percent: float = 0.0
    gc_count: tuple = (0, 0, 0)  # GC collection counts (gen0, gen1, gen2)
    timestamp: str = ""
    
    # Backpressure state
    active_requests: int = 0
    max_concurrent: int = MAX_CONCURRENT_REQUESTS
    queue_utilization: float = 0.0
    
    # Health status
    memory_pressure: str = "normal"  # normal, elevated, critical
    accepting_requests: bool = True


class MemoryTracker:
    """
    Singleton memory tracker for the llm-gateway service.
    
    Provides:
    - Real-time memory usage monitoring
    - Request concurrency tracking (semaphore-based)
    - Memory pressure detection
    - Metrics for /health endpoint
    """
    
    _instance: Optional["MemoryTracker"] = None
    
    def __new__(cls) -> "MemoryTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._initialized = True
        self._peak_mb: float = 0.0
        self._request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._active_requests: int = 0
        self._total_requests: int = 0
        self._rejected_requests: int = 0
        self._lock = asyncio.Lock()
        
        logger.info(
            f"MemoryTracker initialized: threshold={MEMORY_THRESHOLD_MB}MB, "
            f"soft_limit={MEMORY_THRESHOLD_MB * MEMORY_SOFT_LIMIT_PERCENT:.0f}MB, "
            f"max_concurrent={MAX_CONCURRENT_REQUESTS}"
        )
    
    def get_memory_usage(self) -> tuple[float, float]:
        """
        Get current memory usage in MB.
        
        Returns:
            Tuple of (rss_mb, vms_mb)
        """
        try:
            # Use resource module for cross-platform memory info
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            
            # ru_maxrss is in bytes on macOS, kilobytes on Linux
            if sys.platform == "darwin":
                rss_mb = rusage.ru_maxrss / (1024 * 1024)  # bytes to MB
            else:
                rss_mb = rusage.ru_maxrss / 1024  # KB to MB
            
            # Try to get VMS from /proc on Linux
            vms_mb = 0.0
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_mb = int(line.split()[1]) / 1024  # KB to MB
                        elif line.startswith("VmSize:"):
                            vms_mb = int(line.split()[1]) / 1024  # KB to MB
            except FileNotFoundError:
                # Not on Linux, use rough estimate
                vms_mb = rss_mb * 1.5
            
            return rss_mb, vms_mb
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0, 0.0
    
    def get_metrics(self) -> MemoryMetrics:
        """
        Get current memory and backpressure metrics.
        
        Returns:
            MemoryMetrics dataclass with current state
        """
        rss_mb, vms_mb = self.get_memory_usage()
        
        # Update peak
        if rss_mb > self._peak_mb:
            self._peak_mb = rss_mb
        
        # Calculate pressure level
        soft_limit = MEMORY_THRESHOLD_MB * MEMORY_SOFT_LIMIT_PERCENT
        if rss_mb >= MEMORY_THRESHOLD_MB:
            pressure = "critical"
            accepting = False
        elif rss_mb >= soft_limit:
            pressure = "elevated"
            accepting = True  # Still accepting but under pressure
        else:
            pressure = "normal"
            accepting = True
        
        # Queue utilization
        queue_util = self._active_requests / MAX_CONCURRENT_REQUESTS if MAX_CONCURRENT_REQUESTS > 0 else 0.0
        
        return MemoryMetrics(
            rss_mb=round(rss_mb, 2),
            vms_mb=round(vms_mb, 2),
            peak_mb=round(self._peak_mb, 2),
            threshold_mb=MEMORY_THRESHOLD_MB,
            soft_limit_mb=round(soft_limit, 2),
            usage_percent=round((rss_mb / MEMORY_THRESHOLD_MB) * 100, 1) if MEMORY_THRESHOLD_MB > 0 else 0.0,
            gc_count=gc.get_count(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            active_requests=self._active_requests,
            max_concurrent=MAX_CONCURRENT_REQUESTS,
            queue_utilization=round(queue_util * 100, 1),
            memory_pressure=pressure,
            accepting_requests=accepting,
        )
    
    async def acquire_request_slot(self, timeout: float = 5.0) -> bool:
        """
        Acquire a request slot (backpressure mechanism).
        
        Uses semaphore to limit concurrent requests. If memory is critical,
        rejects immediately without waiting.
        
        Args:
            timeout: Maximum seconds to wait for a slot
            
        Returns:
            True if slot acquired, False if rejected (timeout or memory critical)
        """
        # Check memory pressure first
        rss_mb, _ = self.get_memory_usage()
        if rss_mb >= MEMORY_THRESHOLD_MB:
            logger.warning(
                f"Request rejected: memory critical ({rss_mb:.1f}MB >= {MEMORY_THRESHOLD_MB}MB)"
            )
            self._rejected_requests += 1
            return False
        
        # Try to acquire semaphore with timeout
        try:
            acquired = await asyncio.wait_for(
                self._request_semaphore.acquire(),
                timeout=timeout
            )
            if acquired:
                async with self._lock:
                    self._active_requests += 1
                    self._total_requests += 1
                    
                    # Log warning if queue is getting full
                    if self._active_requests >= QUEUE_WARNING_THRESHOLD:
                        logger.warning(
                            f"High request load: {self._active_requests}/{MAX_CONCURRENT_REQUESTS} active"
                        )
                return True
        except asyncio.TimeoutError:
            logger.warning(
                f"Request rejected: timeout waiting for slot "
                f"({self._active_requests}/{MAX_CONCURRENT_REQUESTS} active)"
            )
            self._rejected_requests += 1
            return False
        
        return False
    
    async def release_request_slot(self) -> None:
        """Release a request slot after completion."""
        async with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
        self._request_semaphore.release()
    
    def force_gc(self) -> dict:
        """
        Force garbage collection and return stats.
        
        Returns:
            Dict with before/after memory and objects collected
        """
        before_rss, _ = self.get_memory_usage()
        collected = gc.collect()
        after_rss, _ = self.get_memory_usage()
        
        return {
            "collected_objects": collected,
            "before_mb": round(before_rss, 2),
            "after_mb": round(after_rss, 2),
            "freed_mb": round(before_rss - after_rss, 2),
        }


# Global singleton instance
memory_tracker = MemoryTracker()


# =============================================================================
# Memory Middleware
# =============================================================================

class MemoryMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces memory limits and backpressure.
    
    For each request:
    1. Check memory usage - reject if critical
    2. Acquire request slot (semaphore) - reject if queue full
    3. Process request
    4. Release request slot
    
    Adds X-Memory-* headers to responses for observability.
    """
    
    # Paths that bypass backpressure (health checks, metrics)
    BYPASS_PATHS = {"/health", "/ready", "/live", "/metrics", "/", "/docs", "/redoc", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with memory/backpressure checks."""
        
        # Bypass for health/metrics endpoints
        if request.url.path in self.BYPASS_PATHS:
            return await call_next(request)
        
        # Try to acquire a request slot
        if not await memory_tracker.acquire_request_slot(timeout=10.0):
            metrics = memory_tracker.get_metrics()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "reason": "backpressure",
                    "message": f"Server under memory pressure or at capacity",
                    "memory_mb": metrics.rss_mb,
                    "threshold_mb": metrics.threshold_mb,
                    "active_requests": metrics.active_requests,
                    "max_concurrent": metrics.max_concurrent,
                    "retry_after_seconds": 5,
                },
                headers={
                    "Retry-After": "5",
                    "X-Memory-Pressure": metrics.memory_pressure,
                }
            )
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Add memory headers for observability
            metrics = memory_tracker.get_metrics()
            response.headers["X-Memory-RSS-MB"] = str(metrics.rss_mb)
            response.headers["X-Memory-Pressure"] = metrics.memory_pressure
            response.headers["X-Active-Requests"] = str(metrics.active_requests)
            
            return response
        
        finally:
            # Always release the request slot
            await memory_tracker.release_request_slot()


# =============================================================================
# Health Check Integration
# =============================================================================

def get_memory_health() -> dict:
    """
    Get memory health status for /health endpoint integration.
    
    Returns:
        Dict with memory metrics and health status
    """
    metrics = memory_tracker.get_metrics()
    
    return {
        "memory": {
            "rss_mb": metrics.rss_mb,
            "vms_mb": metrics.vms_mb,
            "peak_mb": metrics.peak_mb,
            "threshold_mb": metrics.threshold_mb,
            "soft_limit_mb": metrics.soft_limit_mb,
            "usage_percent": metrics.usage_percent,
            "pressure": metrics.memory_pressure,
            "gc_count": {
                "gen0": metrics.gc_count[0],
                "gen1": metrics.gc_count[1],
                "gen2": metrics.gc_count[2],
            },
        },
        "backpressure": {
            "active_requests": metrics.active_requests,
            "max_concurrent": metrics.max_concurrent,
            "queue_utilization_percent": metrics.queue_utilization,
            "accepting_requests": metrics.accepting_requests,
        },
        "status": "healthy" if metrics.accepting_requests else "degraded",
    }
