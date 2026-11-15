"""
Agent Tool Registry — Phase 6, Layer 1

Each tool is a self-describing, async-callable unit:
  - name        : unique identifier the LLM uses to call it
  - description : plain-English purpose (fed to LLM as context)
  - parameters  : JSON Schema dict describing the expected input
  - run()       : async method that executes the tool and returns a string result

The registry maps tool names → tool instances so the agent loop can
resolve a tool call in O(1) and invoke it safely.
"""

from __future__ import annotations

import ast
import math
import operator
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

# Top-level import so tests can patch `app.services.agent.tools.get_llm_provider`
from app.services.llm.factory import get_llm_provider


# ---------------------------------------------------------------------------
# Base class every tool must inherit
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str
    description: str
    # JSON Schema describing the tool's input object
    parameters: dict[str, Any]

    @abstractmethod
    async def run(self, user_id: UUID, **kwargs: Any) -> str:
        """Execute the tool and return a plain-text result string."""


# ---------------------------------------------------------------------------
# Tool 1: search_documents
# ---------------------------------------------------------------------------

class SearchDocumentsTool(BaseTool):
    """
    Searches the user's uploaded documents using pgvector cosine similarity.
    Returns the top-k most relevant text chunks with source citations.

    Why this tool?
    The agent calls this when it needs factual information from the user's
    own documents to answer a question — the core RAG capability exposed
    as a tool so the agent can decide *when* to use it.
    """

    name = "search_documents"
    description = (
        "Search the user's uploaded documents for information relevant to a query. "
        "Returns the most relevant text chunks along with their source filename, "
        "page number, and chunk index. Use this tool whenever you need to find "
        "facts, details, or context from the user's documents."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural-language search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of chunks to retrieve (default: 5, max: 10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, document_repo: Any) -> None:
        # We inject the repo so the tool stays testable (no global state)
        self._repo = document_repo

    async def run(self, user_id: UUID, query: str, top_k: int = 5) -> str:
        top_k = min(max(top_k, 1), 10)  # clamp to [1, 10]

        query_embedding = await get_llm_provider().embed(query)

        chunks = await self._repo.similarity_search(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not chunks:
            return "No relevant documents found for this query."

        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[{i}] Source: {chunk.document_filename}, "
                f"Page: {chunk.page_number}, Chunk: {chunk.chunk_index}\n"
                f"{chunk.text}"
            )

        return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 2: calculator
# ---------------------------------------------------------------------------

# Safe subset of operators allowed in expressions
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

# Safe math functions exposed to the evaluator
_SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


def _safe_eval(node: ast.AST) -> float:
    """
    Recursively evaluate an AST node using only whitelisted operators.
    Raises ValueError for any disallowed construct — no exec(), no imports,
    no attribute access, no function calls outside the safe list.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            return _SAFE_FUNCTIONS[node.id]  # type: ignore[return-value]
        raise ValueError(f"Unknown name: {node.id!r}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _SAFE_OPERATORS[op_type](left, right)  # type: ignore[operator]

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return _SAFE_OPERATORS[op_type](operand)  # type: ignore[operator]

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed.")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCTIONS:
            raise ValueError(f"Function not allowed: {func_name!r}")
        func = _SAFE_FUNCTIONS[func_name]
        args = [_safe_eval(a) for a in node.args]
        # round(x, ndigits) requires ndigits to be an int in Python
        if func_name == "round" and len(args) == 2:
            args[1] = int(args[1])
        return func(*args)  # type: ignore[operator]

    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


class CalculatorTool(BaseTool):
    """
    Safely evaluates a mathematical expression and returns the numeric result.

    Why safe eval?
    Python's built-in eval() would allow arbitrary code execution — a severe
    security risk. We parse the expression into an AST and only allow a strict
    whitelist of operations, so the agent can do math without any injection risk.
    """

    name = "calculator"
    description = (
        "Evaluate a mathematical expression and return the result. "
        "Supports +, -, *, /, **, %, //, sqrt(), abs(), round(), log(), "
        "log10(), ceil(), floor(), sin(), cos(), tan(), pi, e. "
        "Use this for any arithmetic or scientific calculation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A mathematical expression to evaluate, e.g. 'sqrt(144) + 2 ** 8'.",
            }
        },
        "required": ["expression"],
    }

    async def run(self, user_id: UUID, expression: str) -> str:  # noqa: ARG002
        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)
            # Format nicely: drop ".0" for whole numbers
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(round(result, 10))
        except ZeroDivisionError:
            return "Error: division by zero."
        except (ValueError, TypeError) as exc:
            return f"Error evaluating expression: {exc}"


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Central registry that maps tool names to their instances.

    Usage:
        registry = ToolRegistry(document_repo=repo)
        tool = registry.get("calculator")
        result = await tool.run(user_id=uid, expression="2 + 2")

    Why a registry?
    The agent loop receives a tool name string from the LLM. The registry
    provides O(1) lookup and a single place to add/remove tools without
    changing the agent loop logic.
    """

    def __init__(self, document_repo: Any = None) -> None:
        self._tools: dict[str, BaseTool] = {}

        # Register all available tools
        self._register(CalculatorTool())
        if document_repo is not None:
            self._register(SearchDocumentsTool(document_repo))

    def _register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Return tool by name, or None if not found."""
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        """Return all registered tools (used to build the LLM system prompt)."""
        return list(self._tools.values())

    def schema_for_llm(self) -> list[dict[str, Any]]:
        """
        Return a list of tool schemas in the format the LLM expects.
        Each entry has: name, description, parameters (JSON Schema).
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]
