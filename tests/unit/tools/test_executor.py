"""
Test Suite for ToolExecutor - WBS 2.4.2.1 Executor Implementation

TDD RED Phase: Tests written before implementation.

Reference Documents:
- ARCHITECTURE.md Line 49: executor.py "Tool execution orchestration"
- ARCHITECTURE.md Lines 211-212: "Executes tools (local or proxied to other microservices)"
- GUIDELINES pp. 1489: Command pattern for tool invocation
- GUIDELINES pp. 466: Fail-fast error handling with retry logic at orchestration level
- GUIDELINES pp. 1004: Circuit breakers and timeouts

Test Categories:
1. TestToolExecutorClass - Basic instantiation and DI (2.4.2.1.1-3)
2. TestToolExecutorExecute - Single tool execution (2.4.2.1.4-9)
3. TestToolExecutorValidation - Argument validation (2.4.2.1.6)
4. TestToolExecutorTimeout - Timeout handling (2.4.2.1.10)
5. TestToolExecutorErrors - Error handling (2.4.2.1.9)
6. TestToolExecutorBatch - Batch execution (2.4.2.2.1-4)
7. TestToolExecutorImports - Import verification
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.domain import ToolCall, ToolDefinition, ToolResult, RegisteredTool
from src.tools.registry import ToolRegistry


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def registry() -> ToolRegistry:
    """Create a fresh ToolRegistry for each test."""
    return ToolRegistry()


@pytest.fixture
def sample_definition() -> ToolDefinition:
    """Create a sample tool definition."""
    return ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        },
    )


@pytest.fixture
def sample_tool(sample_definition: ToolDefinition) -> RegisteredTool:
    """Create a sample registered tool with async handler."""

    async def handler(args: dict) -> str:
        return f"Result for: {args.get('query', 'unknown')}"

    return RegisteredTool(definition=sample_definition, handler=handler)


@pytest.fixture
def sync_tool(sample_definition: ToolDefinition) -> RegisteredTool:
    """Create a sample registered tool with sync handler."""

    def handler(args: dict) -> str:
        return f"Sync result for: {args.get('query', 'unknown')}"

    return RegisteredTool(definition=sample_definition, handler=handler)


@pytest.fixture
def slow_tool() -> RegisteredTool:
    """Create a tool that takes too long to execute."""
    definition = ToolDefinition(
        name="slow_tool",
        description="A slow tool for timeout testing",
        parameters={"type": "object", "properties": {}},
    )

    async def handler(args: dict) -> str:
        await asyncio.sleep(10)  # 10 seconds - will timeout
        return "Slow result"

    return RegisteredTool(definition=definition, handler=handler)


@pytest.fixture
def error_tool() -> RegisteredTool:
    """Create a tool that raises an exception."""
    definition = ToolDefinition(
        name="error_tool",
        description="A tool that always fails",
        parameters={"type": "object", "properties": {}},
    )

    async def handler(args: dict) -> str:
        raise ValueError("Tool execution failed")

    return RegisteredTool(definition=definition, handler=handler)


@pytest.fixture
def sample_tool_call() -> ToolCall:
    """Create a sample tool call."""
    return ToolCall(
        id="call_abc123",
        name="test_tool",
        arguments={"query": "test query"},
    )


# =============================================================================
# WBS 2.4.2.1.1-3: TestToolExecutorClass - Basic instantiation and DI
# =============================================================================


class TestToolExecutorClass:
    """Tests for ToolExecutor class instantiation and setup."""

    def test_tool_executor_can_be_instantiated(self, registry: ToolRegistry) -> None:
        """WBS 2.4.2.1.2: ToolExecutor class can be instantiated."""
        from src.tools.executor import ToolExecutor

        executor = ToolExecutor(registry=registry)
        assert executor is not None

    def test_tool_executor_requires_registry(self) -> None:
        """WBS 2.4.2.1.3: ToolExecutor requires ToolRegistry dependency injection."""
        from src.tools.executor import ToolExecutor

        # Should work with registry
        registry = ToolRegistry()
        executor = ToolExecutor(registry=registry)
        assert executor.registry is registry

    def test_tool_executor_has_default_timeout(self, registry: ToolRegistry) -> None:
        """WBS 2.4.2.1.10: ToolExecutor has a default timeout."""
        from src.tools.executor import ToolExecutor

        executor = ToolExecutor(registry=registry)
        assert hasattr(executor, "timeout")
        assert executor.timeout > 0

    def test_tool_executor_accepts_custom_timeout(self, registry: ToolRegistry) -> None:
        """WBS 2.4.2.1.10: ToolExecutor accepts custom timeout."""
        from src.tools.executor import ToolExecutor

        executor = ToolExecutor(registry=registry, timeout=5.0)
        assert executor.timeout == 5.0


# =============================================================================
# WBS 2.4.2.1.4-8: TestToolExecutorExecute - Single tool execution
# =============================================================================


class TestToolExecutorExecute:
    """Tests for single tool execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result(
        self, registry: ToolRegistry, sample_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.4,8: execute() returns ToolResult."""
        from src.tools.executor import ToolExecutor

        registry.register("test_tool", sample_tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(
            id="call_123", name="test_tool", arguments={"query": "test"}
        )
        result = await executor.execute(tool_call)

        assert isinstance(result, ToolResult)

    @pytest.mark.asyncio
    async def test_execute_valid_tool_returns_content(
        self, registry: ToolRegistry, sample_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.11: Execute valid tool returns result."""
        from src.tools.executor import ToolExecutor

        registry.register("test_tool", sample_tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(
            id="call_123", name="test_tool", arguments={"query": "my query"}
        )
        result = await executor.execute(tool_call)

        assert result.tool_call_id == "call_123"
        assert "my query" in result.content
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_execute_invokes_tool_handler(
        self, registry: ToolRegistry, sample_definition: ToolDefinition
    ) -> None:
        """WBS 2.4.2.1.7: execute() invokes the tool handler."""
        from src.tools.executor import ToolExecutor

        mock_handler = AsyncMock(return_value="mock result")
        tool = RegisteredTool(definition=sample_definition, handler=mock_handler)

        registry.register("test_tool", tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(
            id="call_123", name="test_tool", arguments={"query": "test"}
        )
        await executor.execute(tool_call)

        mock_handler.assert_called_once_with({"query": "test"})

    @pytest.mark.asyncio
    async def test_execute_handles_sync_handler(
        self, registry: ToolRegistry, sync_tool: RegisteredTool
    ) -> None:
        """Execute handles synchronous handlers by wrapping in run_in_executor."""
        from src.tools.executor import ToolExecutor

        registry.register("test_tool", sync_tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(
            id="call_123", name="test_tool", arguments={"query": "sync test"}
        )
        result = await executor.execute(tool_call)

        assert result.is_error is False
        assert "sync test" in result.content.lower() or "sync result" in result.content.lower()


# =============================================================================
# WBS 2.4.2.1.5-6: TestToolExecutorValidation - Validation
# =============================================================================


class TestToolExecutorValidation:
    """Tests for tool and argument validation."""

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool_raises_error(
        self, registry: ToolRegistry
    ) -> None:
        """WBS 2.4.2.1.5: Execute with non-existent tool raises error."""
        from src.tools.executor import ToolExecutor, ToolExecutionError

        executor = ToolExecutor(registry=registry)
        tool_call = ToolCall(
            id="call_123", name="nonexistent_tool", arguments={}
        )

        with pytest.raises(ToolExecutionError) as exc_info:
            await executor.execute(tool_call)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_missing_required_args_raises_error(
        self, registry: ToolRegistry, sample_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.6,12: Execute with missing required args raises error."""
        from src.tools.executor import ToolExecutor, ToolValidationError

        registry.register("test_tool", sample_tool)
        executor = ToolExecutor(registry=registry)

        # Missing required "query" argument
        tool_call = ToolCall(id="call_123", name="test_tool", arguments={})

        with pytest.raises(ToolValidationError) as exc_info:
            await executor.execute(tool_call)

        assert "query" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_wrong_type_args_raises_error(
        self, registry: ToolRegistry, sample_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.6,12: Execute with wrong type args raises error."""
        from src.tools.executor import ToolExecutor, ToolValidationError

        registry.register("test_tool", sample_tool)
        executor = ToolExecutor(registry=registry)

        # "limit" should be integer, not string
        tool_call = ToolCall(
            id="call_123",
            name="test_tool",
            arguments={"query": "test", "limit": "not an integer"},
        )

        with pytest.raises(ToolValidationError) as exc_info:
            await executor.execute(tool_call)

        assert "limit" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower()


# =============================================================================
# WBS 2.4.2.1.9: TestToolExecutorErrors - Error handling
# =============================================================================


class TestToolExecutorErrors:
    """Tests for error handling during tool execution."""

    @pytest.mark.asyncio
    async def test_execute_handler_exception_returns_error_result(
        self, registry: ToolRegistry, error_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.9: Handler exceptions are wrapped in ToolResult with is_error=True."""
        from src.tools.executor import ToolExecutor

        registry.register("error_tool", error_tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(id="call_123", name="error_tool", arguments={})
        result = await executor.execute(tool_call)

        assert result.is_error is True
        assert result.tool_call_id == "call_123"
        assert "failed" in result.content.lower() or "error" in result.content.lower()

    @pytest.mark.asyncio
    async def test_execute_preserves_error_message(
        self, registry: ToolRegistry, sample_definition: ToolDefinition
    ) -> None:
        """Error message from handler is preserved in result content."""
        from src.tools.executor import ToolExecutor

        async def handler(args: dict) -> str:
            raise RuntimeError("Specific error message 12345")

        tool = RegisteredTool(definition=sample_definition, handler=handler)
        registry.register("test_tool", tool)
        executor = ToolExecutor(registry=registry)

        tool_call = ToolCall(id="call_123", name="test_tool", arguments={"query": "x"})
        result = await executor.execute(tool_call)

        assert result.is_error is True
        assert "12345" in result.content or "Specific error" in result.content


# =============================================================================
# WBS 2.4.2.1.10,13: TestToolExecutorTimeout - Timeout handling
# =============================================================================


class TestToolExecutorTimeout:
    """Tests for execution timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_error_result(
        self, registry: ToolRegistry, slow_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.1.10,13: Execution timeout returns error result."""
        from src.tools.executor import ToolExecutor

        registry.register("slow_tool", slow_tool)
        executor = ToolExecutor(registry=registry, timeout=0.1)  # 100ms timeout

        tool_call = ToolCall(id="call_123", name="slow_tool", arguments={})
        result = await executor.execute(tool_call)

        assert result.is_error is True
        assert result.tool_call_id == "call_123"
        assert "timeout" in result.content.lower()

    @pytest.mark.asyncio
    async def test_execute_timeout_does_not_block(
        self, registry: ToolRegistry, slow_tool: RegisteredTool
    ) -> None:
        """Timeout prevents blocking on slow tools."""
        from src.tools.executor import ToolExecutor
        import time

        registry.register("slow_tool", slow_tool)
        executor = ToolExecutor(registry=registry, timeout=0.1)

        tool_call = ToolCall(id="call_123", name="slow_tool", arguments={})

        start = time.time()
        await executor.execute(tool_call)
        elapsed = time.time() - start

        # Should return much faster than the 10-second sleep
        assert elapsed < 1.0


# =============================================================================
# WBS 2.4.2.2.1-4: TestToolExecutorBatch - Batch execution
# =============================================================================


class TestToolExecutorBatch:
    """Tests for batch tool execution."""

    @pytest.mark.asyncio
    async def test_execute_batch_returns_list_of_results(
        self, registry: ToolRegistry, sample_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.2.1: execute_batch returns list of ToolResults."""
        from src.tools.executor import ToolExecutor

        registry.register("test_tool", sample_tool)
        executor = ToolExecutor(registry=registry)

        tool_calls = [
            ToolCall(id="call_1", name="test_tool", arguments={"query": "q1"}),
            ToolCall(id="call_2", name="test_tool", arguments={"query": "q2"}),
        ]
        results = await executor.execute_batch(tool_calls)

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, ToolResult) for r in results)

    @pytest.mark.asyncio
    async def test_execute_batch_preserves_order(
        self, registry: ToolRegistry, sample_definition: ToolDefinition
    ) -> None:
        """WBS 2.4.2.2.3: Results preserve order of input tool calls."""
        from src.tools.executor import ToolExecutor

        async def handler(args: dict) -> str:
            return args.get("query", "")

        tool = RegisteredTool(definition=sample_definition, handler=handler)
        registry.register("test_tool", tool)
        executor = ToolExecutor(registry=registry)

        tool_calls = [
            ToolCall(id="call_1", name="test_tool", arguments={"query": "first"}),
            ToolCall(id="call_2", name="test_tool", arguments={"query": "second"}),
            ToolCall(id="call_3", name="test_tool", arguments={"query": "third"}),
        ]
        results = await executor.execute_batch(tool_calls)

        assert results[0].tool_call_id == "call_1"
        assert results[1].tool_call_id == "call_2"
        assert results[2].tool_call_id == "call_3"
        assert "first" in results[0].content
        assert "second" in results[1].content
        assert "third" in results[2].content

    @pytest.mark.asyncio
    async def test_execute_batch_concurrent(
        self, registry: ToolRegistry, sample_definition: ToolDefinition
    ) -> None:
        """WBS 2.4.2.2.2,5: Batch execution is concurrent with asyncio.gather."""
        from src.tools.executor import ToolExecutor
        import time

        execution_times: list[float] = []

        async def slow_handler(args: dict) -> str:
            start = time.time()
            await asyncio.sleep(0.1)  # 100ms each
            execution_times.append(time.time() - start)
            return f"Done: {args.get('query')}"

        definition = ToolDefinition(
            name="slow_test",
            description="Slow for testing",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        tool = RegisteredTool(definition=definition, handler=slow_handler)
        registry.register("slow_test", tool)
        executor = ToolExecutor(registry=registry)

        tool_calls = [
            ToolCall(id=f"call_{i}", name="slow_test", arguments={"query": f"q{i}"})
            for i in range(5)
        ]

        start = time.time()
        results = await executor.execute_batch(tool_calls)
        total_elapsed = time.time() - start

        assert len(results) == 5
        # If sequential: 5 * 0.1 = 0.5s
        # If concurrent: ~0.1s (all run in parallel)
        # Allow some overhead
        assert total_elapsed < 0.3, f"Batch should be concurrent, took {total_elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_execute_batch_handles_partial_failure(
        self, registry: ToolRegistry, sample_tool: RegisteredTool, error_tool: RegisteredTool
    ) -> None:
        """WBS 2.4.2.2.4,6: Batch handles partial failures gracefully."""
        from src.tools.executor import ToolExecutor

        registry.register("test_tool", sample_tool)
        registry.register("error_tool", error_tool)
        executor = ToolExecutor(registry=registry)

        tool_calls = [
            ToolCall(id="call_1", name="test_tool", arguments={"query": "ok"}),
            ToolCall(id="call_2", name="error_tool", arguments={}),  # Will fail
            ToolCall(id="call_3", name="test_tool", arguments={"query": "also ok"}),
        ]
        results = await executor.execute_batch(tool_calls)

        # All results returned despite failure
        assert len(results) == 3

        # First and third should succeed
        assert results[0].is_error is False
        assert results[2].is_error is False

        # Second should be an error
        assert results[1].is_error is True
        assert results[1].tool_call_id == "call_2"

    @pytest.mark.asyncio
    async def test_execute_batch_empty_list(
        self, registry: ToolRegistry
    ) -> None:
        """Batch execution with empty list returns empty list."""
        from src.tools.executor import ToolExecutor

        executor = ToolExecutor(registry=registry)
        results = await executor.execute_batch([])

        assert results == []


# =============================================================================
# TestToolExecutorImports - Import verification
# =============================================================================


class TestToolExecutorImports:
    """Tests to verify ToolExecutor is importable from expected locations."""

    def test_executor_importable_from_tools(self) -> None:
        """ToolExecutor is importable from src.tools."""
        from src.tools import ToolExecutor

        assert ToolExecutor is not None

    def test_errors_importable_from_tools(self) -> None:
        """Executor errors are importable from src.tools."""
        from src.tools import ToolExecutionError, ToolValidationError

        assert ToolExecutionError is not None
        assert ToolValidationError is not None

    def test_get_tool_executor_importable(self) -> None:
        """get_tool_executor singleton getter is importable."""
        from src.tools import get_tool_executor

        assert callable(get_tool_executor)
