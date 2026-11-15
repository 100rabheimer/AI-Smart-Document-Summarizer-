"""
Bounded ReAct Agent Loop — Phase 6, Layer 2

Implements the Reason + Act loop:
  1. Formats prompt with tool definitions and running scratchpad.
  2. Queries LLM for Thought + Action or Thought + Final Answer.
  3. Parses action, executes registered tool with tenant user_id.
  4. Appends observation to scratchpad.
  5. Repeats until Final Answer or max_steps limit is reached.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.services.agent.tools import ToolRegistry
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Regular expressions for parsing ReAct format
THOUGHT_PATTERN = re.compile(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)", re.DOTALL | re.IGNORECASE)
ACTION_PATTERN = re.compile(r"Action:\s*([a-zA-Z0-9_-]+)", re.IGNORECASE)
ACTION_INPUT_PATTERN = re.compile(r"Action Input:\s*(.*?)(?=\nObservation:|\nThought:|$)", re.DOTALL | re.IGNORECASE)
FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.*)", re.DOTALL | re.IGNORECASE)


@dataclass
class AgentStep:
    """Represents a single step in the agent's reasoning process."""
    step_number: int
    thought: str
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None


@dataclass
class AgentResult:
    """The final outcome of the ReAct agent execution."""
    final_answer: str
    steps: list[AgentStep] = field(default_factory=list)
    hit_max_steps: bool = False


REACT_SYSTEM_PROMPT = """You are DocMind's AI Assistant with access to tools.
Solve the user's request step-by-step using the following tools:

{tools_description}

Use the following format strictly:

Thought: Explain what you need to do next.
Action: the action to take, exactly one of [{tool_names}]
Action Input: the input parameters as a valid JSON object (or string if single parameter)
Observation: the result of the action (provided to you)

... (this Thought/Action/Action Input/Observation can repeat up to {max_steps} times)

Thought: I now know the final answer.
Final Answer: the complete and clear answer to the user's original question.

Rules:
1. Always start with "Thought:".
2. If you can answer immediately without tools, output "Thought: <reasoning>" followed by "Final Answer: <answer>".
3. When using a tool, you MUST stop after "Action Input: ...", do NOT invent an Observation.
4. Only call tools that are listed in the available tools.
5. Base answers on factual observations from tools whenever possible.
"""


class ReActAgent:
    """
    Bounded ReAct Agent that executes reasoning steps up to a configured limit.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        max_steps: int = 5,
        step_timeout_seconds: float = 30.0,
    ) -> None:
        self.llm = llm_provider
        self.tools = tool_registry
        self.max_steps = max(1, min(max_steps, 10))  # clamp between 1 and 10
        self.step_timeout = step_timeout_seconds

    def _format_tools_description(self) -> tuple[str, str]:
        """Formats the list of available tools and tool names for the prompt."""
        descriptions: list[str] = []
        names: list[str] = []
        for tool in self.tools.all_tools():
            names.append(tool.name)
            params = json.dumps(tool.parameters.get("properties", {}), indent=2)
            descriptions.append(f"- **{tool.name}**: {tool.description}\n  Parameters: {params}")
        return "\n\n".join(descriptions), ", ".join(names)

    def _parse_action_input(self, input_str: str) -> dict[str, Any]:
        """Parses the Action Input string into a dictionary of kwargs."""
        cleaned = input_str.strip()
        # If it's wrapped in markdown json fences, strip them
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Try parsing as JSON dictionary
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # If it's a plain string, check if single parameter tool
        return {"query": cleaned, "expression": cleaned}

    async def run(
        self,
        user_id: UUID,
        user_question: str,
        conversation_context: str | None = None,
    ) -> AgentResult:
        """
        Executes the ReAct loop until completion or max_steps.
        """
        tools_desc, tool_names = self._format_tools_description()
        system_instruction = REACT_SYSTEM_PROMPT.format(
            tools_description=tools_desc,
            tool_names=tool_names,
            max_steps=self.max_steps,
        )

        scratchpad = ""
        if conversation_context:
            scratchpad += f"Previous conversation context:\n{conversation_context}\n\n"

        scratchpad += f"User Question: {user_question}\n"

        steps: list[AgentStep] = []

        for step_idx in range(1, self.max_steps + 1):
            prompt = f"{system_instruction}\n\nConversation so far:\n{scratchpad}"

            try:
                # Step timeout guard
                llm_output = await asyncio.wait_for(
                    self.llm.generate(prompt=prompt, system_prompt=system_instruction),
                    timeout=self.step_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"ReAct agent step {step_idx} timed out.")
                return AgentResult(
                    final_answer="I apologize, but processing your request timed out. Please try again with a simpler question.",
                    steps=steps,
                    hit_max_steps=True,
                )
            except Exception as exc:
                logger.error(f"Error during LLM generation in step {step_idx}: {exc}")
                return AgentResult(
                    final_answer=f"An error occurred while generating a response: {exc}",
                    steps=steps,
                    hit_max_steps=False,
                )

            # Check for Final Answer
            final_match = FINAL_ANSWER_PATTERN.search(llm_output)
            thought_match = THOUGHT_PATTERN.search(llm_output)
            thought_text = thought_match.group(1).strip() if thought_match else ""

            if final_match:
                final_answer = final_match.group(1).strip()
                steps.append(AgentStep(step_number=step_idx, thought=thought_text))
                return AgentResult(final_answer=final_answer, steps=steps, hit_max_steps=False)

            # Parse Action and Action Input
            action_match = ACTION_PATTERN.search(llm_output)
            action_input_match = ACTION_INPUT_PATTERN.search(llm_output)

            if not action_match:
                # Model provided neither a recognizable action nor final answer; treat output as final answer
                steps.append(AgentStep(step_number=step_idx, thought=thought_text or llm_output))
                return AgentResult(
                    final_answer=llm_output.strip(),
                    steps=steps,
                    hit_max_steps=False,
                )

            action_name = action_match.group(1).strip()
            raw_action_input = action_input_match.group(1).strip() if action_input_match else "{}"

            # Execute tool
            tool = self.tools.get(action_name)
            if not tool:
                observation = f"Error: Tool '{action_name}' does not exist. Available tools: {tool_names}"
            else:
                kwargs = self._parse_action_input(raw_action_input)
                try:
                    observation = await tool.run(user_id=user_id, **kwargs)
                except Exception as exc:
                    observation = f"Error executing tool '{action_name}': {exc}"

            # Record step
            step_record = AgentStep(
                step_number=step_idx,
                thought=thought_text,
                action=action_name,
                action_input=raw_action_input,
                observation=observation,
            )
            steps.append(step_record)

            # Update scratchpad for next iteration
            scratchpad += (
                f"\nThought: {thought_text}\n"
                f"Action: {action_name}\n"
                f"Action Input: {raw_action_input}\n"
                f"Observation: {observation}\n"
            )

        # Hit max steps without Final Answer: synthesize graceful response from scratchpad
        fallback_prompt = (
            f"You reached the maximum step limit ({self.max_steps}). "
            f"Based on the observations collected below, provide the best possible final answer to the user's question.\n\n"
            f"{scratchpad}\n\nFinal Answer:"
        )
        try:
            fallback_answer = await self.llm.generate(prompt=fallback_prompt)
            clean_answer = fallback_answer.replace("Final Answer:", "").strip()
        except Exception:
            clean_answer = "I was unable to complete the reasoning process within the step limit. Please narrow your query."

        return AgentResult(
            final_answer=clean_answer,
            steps=steps,
            hit_max_steps=True,
        )
