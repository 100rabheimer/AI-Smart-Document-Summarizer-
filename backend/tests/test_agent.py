"""
Unit tests for Phase 6, Layer 1: Tool Registry (tools.py)

What we test:
- CalculatorTool: correct results, safe eval, error handling
- SearchDocumentsTool: correct formatting, top_k clamping, empty result
- ToolRegistry: registration, schema generation, get() lookup
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent.tools import (
    CalculatorTool,
    SearchDocumentsTool,
    ToolRegistry,
)
from app.services.agent.agent_loop import ReActAgent, AgentStep, AgentResult
from app.services.agent.memory import MemoryService

USER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# CalculatorTool tests
# ---------------------------------------------------------------------------

class TestCalculatorTool:
    """Tests for the safe math expression evaluator."""

    @pytest.fixture
    def calc(self):
        return CalculatorTool()

    @pytest.mark.asyncio
    async def test_basic_addition(self, calc):
        result = await calc.run(user_id=USER_ID, expression="2 + 3")
        assert result == "5"

    @pytest.mark.asyncio
    async def test_float_result(self, calc):
        result = await calc.run(user_id=USER_ID, expression="7 / 2")
        assert result == "3.5"

    @pytest.mark.asyncio
    async def test_power(self, calc):
        result = await calc.run(user_id=USER_ID, expression="2 ** 10")
        assert result == "1024"

    @pytest.mark.asyncio
    async def test_sqrt(self, calc):
        result = await calc.run(user_id=USER_ID, expression="sqrt(144)")
        assert result == "12"

    @pytest.mark.asyncio
    async def test_complex_expression(self, calc):
        result = await calc.run(user_id=USER_ID, expression="sqrt(144) + 2 ** 8")
        assert result == "268"

    @pytest.mark.asyncio
    async def test_modulo(self, calc):
        result = await calc.run(user_id=USER_ID, expression="17 % 5")
        assert result == "2"

    @pytest.mark.asyncio
    async def test_floor_div(self, calc):
        result = await calc.run(user_id=USER_ID, expression="17 // 5")
        assert result == "3"

    @pytest.mark.asyncio
    async def test_unary_neg(self, calc):
        result = await calc.run(user_id=USER_ID, expression="-5 + 10")
        assert result == "5"

    @pytest.mark.asyncio
    async def test_pi_constant(self, calc):
        result = await calc.run(user_id=USER_ID, expression="round(pi, 4)")
        # round(pi, 4) = 3.1416
        assert "3.1416" in result

    @pytest.mark.asyncio
    async def test_division_by_zero(self, calc):
        result = await calc.run(user_id=USER_ID, expression="1 / 0")
        assert "division by zero" in result.lower()

    @pytest.mark.asyncio
    async def test_disallowed_function_blocked(self, calc):
        # exec/eval/import must be blocked
        result = await calc.run(user_id=USER_ID, expression="__import__('os')")
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_disallowed_attribute_access_blocked(self, calc):
        result = await calc.run(user_id=USER_ID, expression="(1).__class__")
        assert "error" in result.lower()

    def test_tool_metadata(self, calc):
        assert calc.name == "calculator"
        assert "expression" in calc.parameters["properties"]
        assert calc.parameters["required"] == ["expression"]


# ---------------------------------------------------------------------------
# SearchDocumentsTool tests
# ---------------------------------------------------------------------------

class TestSearchDocumentsTool:
    """Tests for the document search tool."""

    def _make_chunk(self, filename: str, page: int, idx: int, text: str):
        chunk = MagicMock()
        chunk.document_filename = filename
        chunk.page_number = page
        chunk.chunk_index = idx
        chunk.text = text
        return chunk

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.similarity_search = AsyncMock()
        return repo

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.embed = AsyncMock(return_value=[0.1] * 768)
        return provider

    @pytest.mark.asyncio
    async def test_returns_formatted_chunks(self, mock_repo, mock_provider):
        mock_repo.similarity_search.return_value = [
            self._make_chunk("report.pdf", 2, 0, "Revenue grew by 20%."),
        ]
        tool = SearchDocumentsTool(mock_repo)
        with patch(
            "app.services.agent.tools.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await tool.run(user_id=USER_ID, query="revenue growth")

        assert "report.pdf" in result
        assert "Page: 2" in result
        assert "Revenue grew by 20%." in result

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_repo, mock_provider):
        mock_repo.similarity_search.return_value = []
        tool = SearchDocumentsTool(mock_repo)
        with patch(
            "app.services.agent.tools.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await tool.run(user_id=USER_ID, query="anything")

        assert "no relevant documents" in result.lower()

    @pytest.mark.asyncio
    async def test_top_k_clamped_to_max(self, mock_repo, mock_provider):
        mock_repo.similarity_search.return_value = []
        tool = SearchDocumentsTool(mock_repo)
        with patch(
            "app.services.agent.tools.get_llm_provider",
            return_value=mock_provider,
        ):
            await tool.run(user_id=USER_ID, query="test", top_k=999)

        # Should have been clamped to 10
        call_args = mock_repo.similarity_search.call_args
        assert call_args.kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_top_k_clamped_to_min(self, mock_repo, mock_provider):
        mock_repo.similarity_search.return_value = []
        tool = SearchDocumentsTool(mock_repo)
        with patch(
            "app.services.agent.tools.get_llm_provider",
            return_value=mock_provider,
        ):
            await tool.run(user_id=USER_ID, query="test", top_k=0)

        call_args = mock_repo.similarity_search.call_args
        assert call_args.kwargs["top_k"] == 1

    def test_tool_metadata(self):
        tool = SearchDocumentsTool(document_repo=MagicMock())
        assert tool.name == "search_documents"
        assert "query" in tool.parameters["properties"]
        assert "query" in tool.parameters["required"]


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------

class TestToolRegistry:
    """Tests for the central tool registry."""

    def test_calculator_always_registered(self):
        registry = ToolRegistry()
        tool = registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"

    def test_search_registered_when_repo_provided(self):
        mock_repo = MagicMock()
        registry = ToolRegistry(document_repo=mock_repo)
        tool = registry.get("search_documents")
        assert tool is not None

    def test_search_not_registered_without_repo(self):
        registry = ToolRegistry()
        tool = registry.get("search_documents")
        assert tool is None

    def test_get_unknown_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent_tool") is None

    def test_all_tools_returns_list(self):
        registry = ToolRegistry(document_repo=MagicMock())
        tools = registry.all_tools()
        assert len(tools) >= 2
        names = {t.name for t in tools}
        assert "calculator" in names
        assert "search_documents" in names

    def test_schema_for_llm_structure(self):
        registry = ToolRegistry()
        schemas = registry.schema_for_llm()
        assert len(schemas) >= 1
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            assert schema["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# ReActAgent loop tests
# ---------------------------------------------------------------------------

class TestReActAgent:
    """Tests for the bounded ReAct reasoning loop."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate = AsyncMock()
        return llm

    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_direct_answer_without_tools(self, mock_llm, registry):
        mock_llm.generate.return_value = (
            "Thought: The capital of France is common knowledge.\n"
            "Final Answer: Paris"
        )
        agent = ReActAgent(llm_provider=mock_llm, tool_registry=registry, max_steps=5)
        result = await agent.run(user_id=USER_ID, user_question="What is the capital of France?")

        assert result.final_answer == "Paris"
        assert len(result.steps) == 1
        assert result.hit_max_steps is False
        assert result.steps[0].thought == "The capital of France is common knowledge."

    @pytest.mark.asyncio
    async def test_tool_call_and_final_answer(self, mock_llm, registry):
        # Step 1: Tool invocation; Step 2: Final answer
        mock_llm.generate.side_effect = [
            (
                "Thought: I need to calculate 25 * 4.\n"
                "Action: calculator\n"
                "Action Input: {\"expression\": \"25 * 4\"}"
            ),
            (
                "Thought: I have the calculation result.\n"
                "Final Answer: 25 multiplied by 4 is 100."
            ),
        ]
        agent = ReActAgent(llm_provider=mock_llm, tool_registry=registry, max_steps=5)
        result = await agent.run(user_id=USER_ID, user_question="Calculate 25 * 4")

        assert result.final_answer == "25 multiplied by 4 is 100."
        assert len(result.steps) == 2
        assert result.steps[0].action == "calculator"
        assert result.steps[0].observation == "100"
        assert result.hit_max_steps is False

    @pytest.mark.asyncio
    async def test_unknown_tool_handling(self, mock_llm, registry):
        mock_llm.generate.side_effect = [
            (
                "Thought: Let me try a magic tool.\n"
                "Action: magical_tool\n"
                "Action Input: {\"query\": \"test\"}"
            ),
            (
                "Thought: That tool does not exist, so I will answer directly.\n"
                "Final Answer: I can answer without that tool."
            ),
        ]
        agent = ReActAgent(llm_provider=mock_llm, tool_registry=registry, max_steps=3)
        result = await agent.run(user_id=USER_ID, user_question="Run magic")

        assert "I can answer without that tool" in result.final_answer
        assert len(result.steps) == 2
        assert "Error: Tool 'magical_tool' does not exist" in result.steps[0].observation

    @pytest.mark.asyncio
    async def test_max_steps_budget_exceeded(self, mock_llm, registry):
        # LLM keeps calling calculator without reaching Final Answer
        mock_llm.generate.side_effect = [
            "Thought: Step 1\nAction: calculator\nAction Input: {\"expression\": \"1 + 1\"}",
            "Thought: Step 2\nAction: calculator\nAction Input: {\"expression\": \"2 + 2\"}",
            # Fallback generation after max steps
            "Final Answer: Reached limit, best answer is 4",
        ]
        agent = ReActAgent(llm_provider=mock_llm, tool_registry=registry, max_steps=2)
        result = await agent.run(user_id=USER_ID, user_question="Infinite loop test")

        assert result.hit_max_steps is True
        assert len(result.steps) == 2
        assert "best answer is 4" in result.final_answer

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_llm, registry):
        import asyncio

        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(0.5)
            return "Final Answer: done"

        mock_llm.generate.side_effect = slow_generate
        agent = ReActAgent(llm_provider=mock_llm, tool_registry=registry, max_steps=3, step_timeout_seconds=0.05)
        result = await agent.run(user_id=USER_ID, user_question="Timeout test")

        assert "timed out" in result.final_answer.lower()
        assert result.hit_max_steps is True


# ---------------------------------------------------------------------------
# MemoryService tests
# ---------------------------------------------------------------------------

class TestMemoryService:
    """Tests for short-term and long-term memory management."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.get_recent_messages = AsyncMock()
        repo.list_memories = AsyncMock()
        repo.upsert_memory = AsyncMock()
        repo.delete_memory = AsyncMock()
        return repo

    @pytest.fixture
    def memory_service(self, mock_repo):
        return MemoryService(repo=mock_repo)

    @pytest.mark.asyncio
    async def test_get_short_term_context(self, memory_service, mock_repo, mock_db):
        msg1 = MagicMock(role="user", content="Hello!")
        msg2 = MagicMock(role="assistant", content="Hi, how can I help you?")
        mock_repo.get_recent_messages.return_value = [msg1, msg2]

        conv_id = uuid.uuid4()
        context = await memory_service.get_short_term_context(
            db=mock_db,
            user_id=USER_ID,
            conversation_id=conv_id,
            limit=5,
        )

        assert "User: Hello!" in context
        assert "Assistant: Hi, how can I help you?" in context

    @pytest.mark.asyncio
    async def test_get_short_term_context_empty(self, memory_service, mock_repo, mock_db):
        mock_repo.get_recent_messages.return_value = []
        conv_id = uuid.uuid4()
        context = await memory_service.get_short_term_context(
            db=mock_db,
            user_id=USER_ID,
            conversation_id=conv_id,
        )
        assert context == ""

    @pytest.mark.asyncio
    async def test_get_long_term_context(self, memory_service, mock_repo, mock_db):
        mem1 = MagicMock(key="tone", value="concise")
        mem2 = MagicMock(key="role", value="developer")
        mock_repo.list_memories.return_value = [mem1, mem2]

        context = await memory_service.get_long_term_context(db=mock_db, user_id=USER_ID)

        assert "<user_preferences>" in context
        assert "- tone: concise" in context
        assert "- role: developer" in context
        assert "</user_preferences>" in context

    @pytest.mark.asyncio
    async def test_get_long_term_context_empty(self, memory_service, mock_repo, mock_db):
        mock_repo.list_memories.return_value = []
        context = await memory_service.get_long_term_context(db=mock_db, user_id=USER_ID)
        assert context == ""

    @pytest.mark.asyncio
    async def test_assemble_agent_context(self, memory_service, mock_repo, mock_db):
        mem = MagicMock(key="language", value="Python")
        msg = MagicMock(role="user", content="Show me code.")
        mock_repo.list_memories.return_value = [mem]
        mock_repo.get_recent_messages.return_value = [msg]

        conv_id = uuid.uuid4()
        unified = await memory_service.assemble_agent_context(
            db=mock_db,
            user_id=USER_ID,
            conversation_id=conv_id,
        )

        assert "<user_preferences>" in unified
        assert "- language: Python" in unified
        assert "<conversation_history>" in unified
        assert "User: Show me code." in unified

    @pytest.mark.asyncio
    async def test_preference_crud(self, memory_service, mock_repo, mock_db):
        mock_repo.upsert_memory.return_value = MagicMock(key="tone", value="formal")
        mock_repo.delete_memory.return_value = True

        saved = await memory_service.set_user_preference(
            db=mock_db,
            user_id=USER_ID,
            key=" Tone ",
            value=" formal ",
        )
        assert saved.key == "tone"
        mock_repo.upsert_memory.assert_awaited_once_with(
            db=mock_db,
            user_id=USER_ID,
            key="tone",
            value="formal",
        )

        deleted = await memory_service.delete_user_preference(
            db=mock_db,
            user_id=USER_ID,
            key=" Tone ",
        )
        assert deleted is True
        mock_repo.delete_memory.assert_awaited_once_with(
            db=mock_db,
            user_id=USER_ID,
            key="tone",
        )


