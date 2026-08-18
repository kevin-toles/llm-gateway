"""RED tests for ENG-3: readonly flag on ToolDefinition + read/write partitioning in execute_batch.

WBS: ENG-3 (Tool Execution Safety)
TDD Phase: RED — tests specify desired behavior; GREEN to follow.

AC-ENG3.1: ToolDefinition has readonly: bool = True field.
AC-ENG3.2: readonly defaults to True (opt-in mutability, max safety).
AC-ENG3.3: Tools registered with readonly=False are marked as write tools.
AC-ENG3.4: execute_batch() runs readonly tools concurrently (asyncio.gather).
AC-ENG3.5: execute_batch() runs non-readonly (write) tools serially (sequential await).
AC-ENG3.6: execute_batch() with mixed tools: reads run first in parallel,
           writes run after in serial.

Paper basis: Engram §2.4 — parallel memory retrieval, serial memory writes.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.domain import ToolCall, ToolDefinition, ToolResult, RegisteredTool
from src.tools.registry import ToolRegistry


# =============================================================================
# Helpers
# =============================================================================


def _make_tool(name: str, readonly: bool = True) -> RegisteredTool:
    """Build a RegisteredTool with a no-op async handler."""
    definition = ToolDefinition(
        name=name,
        description=f"Test tool: {name}",
        parameters={"type": "object", "properties": {}},
        readonly=readonly,
    )

    async def handler(args: dict) -> str:
        return f"{name} result"

    return RegisteredTool(definition=definition, handler=handler)


def _register(registry: ToolRegistry, name: str, handler, readonly: bool = True) -> None:
    """Register a tool with the correct API: register(name: str, tool: RegisteredTool)."""
    definition = ToolDefinition(
        name=name,
        description=f"Test tool: {name}",
        parameters={"type": "object", "properties": {}},
        readonly=readonly,
    )
    registry.register(name, RegisteredTool(definition=definition, handler=handler))


def _make_call(name: str, call_id: str = "call_001") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments={})


# =============================================================================
# AC-ENG3.1–3.3: ToolDefinition.readonly field
# =============================================================================


class TestToolDefinitionReadonly:
    """ToolDefinition.readonly field contract."""

    def test_readonly_defaults_to_true(self) -> None:
        """AC-ENG3.1 + AC-ENG3.2: readonly field exists and defaults to True."""
        tool = ToolDefinition(
            name="search",
            description="Search corpus",
            parameters={"type": "object", "properties": {}},
        )
        assert hasattr(tool, "readonly")
        assert tool.readonly is True

    def test_readonly_can_be_set_false(self) -> None:
        """AC-ENG3.3: readonly=False marks tool as a write operation."""
        tool = ToolDefinition(
            name="write_note",
            description="Write a note to memory",
            parameters={"type": "object", "properties": {}},
            readonly=False,
        )
        assert tool.readonly is False

    def test_readonly_true_explicit_set(self) -> None:
        """AC-ENG3.2: readonly can be set=True explicitly."""
        tool = ToolDefinition(
            name="compute_similarity",
            description="Compute similarity",
            parameters={"type": "object", "properties": {}},
            readonly=True,
        )
        assert tool.readonly is True

    def test_registered_tool_inherits_readonly(self) -> None:
        """AC-ENG3.3: RegisteredTool's definition.readonly is accessible."""
        tool = _make_tool("search_corpus", readonly=True)
        assert tool.definition.readonly is True

        write_tool = _make_tool("write_memory", readonly=False)
        assert write_tool.definition.readonly is False


# =============================================================================
# AC-ENG3.4–3.6: execute_batch() read/write partitioning
# =============================================================================


class TestExecuteBatchPartitioning:
    """execute_batch() partitions readonly vs write tools correctly."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    @pytest.fixture
    def executor(self, registry: ToolRegistry) -> Any:
        from src.tools.executor import ToolExecutor

        return ToolExecutor(registry)

    @pytest.mark.asyncio
    async def test_all_readonly_tools_run_concurrently(
        self, executor: Any, registry: ToolRegistry
    ) -> None:
        """AC-ENG3.4: Multiple readonly tools all start before any finishes."""
        started: list[str] = []
        finished: list[str] = []
        barrier = asyncio.Barrier(2)

        for tool_name in ("read_a", "read_b"):
            name = tool_name  # capture

            async def handler(args: dict, _n: str = name) -> str:
                started.append(_n)
                await barrier.wait()  # forces both to be in-flight simultaneously
                finished.append(_n)
                return f"{_n} ok"

            _register(registry, name, handler, readonly=True)

        calls = [_make_call("read_a", "c1"), _make_call("read_b", "c2")]
        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert all(not r.is_error for r in results)
        # Both must have started before either finished
        assert len(started) == 2
        assert len(finished) == 2

    @pytest.mark.asyncio
    async def test_write_tools_run_serially(
        self, executor: Any, registry: ToolRegistry
    ) -> None:
        """AC-ENG3.5: Write tools run one at a time (serial)."""
        execution_order: list[str] = []
        in_flight: list[int] = [0]  # mutable count

        for tool_name in ("write_a", "write_b"):
            name = tool_name

            async def handler(args: dict, _n: str = name) -> str:
                in_flight[0] += 1
                assert in_flight[0] == 1, (
                    f"Write tool {_n} ran concurrently with another write tool"
                )
                await asyncio.sleep(0)  # yield to event loop
                execution_order.append(_n)
                in_flight[0] -= 1
                return f"{_n} ok"

            _register(registry, name, handler, readonly=False)

        calls = [_make_call("write_a", "c1"), _make_call("write_b", "c2")]
        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert all(not r.is_error for r in results)
        # Serial: write_a fully completes before write_b starts
        assert execution_order == ["write_a", "write_b"]

    @pytest.mark.asyncio
    async def test_mixed_reads_run_before_writes(
        self, executor: Any, registry: ToolRegistry
    ) -> None:
        """AC-ENG3.6: Mixed batch: reads execute (concurrently), then writes (serially)."""
        phase_log: list[str] = []

        async def read_handler(args: dict) -> str:
            phase_log.append("read")
            return "read_result"

        async def write_handler(args: dict) -> str:
            phase_log.append("write")
            return "write_result"

        _register(registry, "read_tool", read_handler, readonly=True)
        _register(registry, "write_tool", write_handler, readonly=False)

        # Order in the call list: write first, then read — but reads should still go first
        calls = [
            _make_call("write_tool", "c1"),
            _make_call("read_tool", "c2"),
        ]
        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert all(not r.is_error for r in results)
        # Read phase must complete before write phase starts
        assert phase_log.index("read") < phase_log.index("write")

    @pytest.mark.asyncio
    async def test_results_order_preserved_mixed(
        self, executor: Any, registry: ToolRegistry
    ) -> None:
        """AC-ENG3.6: Result order matches original call order (write first, read second)."""
        async def read_handler(args: dict) -> str:
            return "read_ok"

        async def write_handler(args: dict) -> str:
            return "write_ok"

        _register(registry, "read_r", read_handler, readonly=True)
        _register(registry, "write_w", write_handler, readonly=False)

        calls = [_make_call("write_w", "c1"), _make_call("read_r", "c2")]
        results = await executor.execute_batch(calls)

        # Results MUST be in the same order as calls (even though execution order differs)
        assert results[0].tool_call_id == "c1"
        assert results[1].tool_call_id == "c2"
        assert "write" in results[0].content
        assert "read" in results[1].content
