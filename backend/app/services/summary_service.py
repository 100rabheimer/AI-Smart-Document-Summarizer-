import json
import re
from typing import Optional

from app.core.prompts import DOCUMENT_SUMMARY_PROMPT_V1
from app.schemas.document import DocumentSummary
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider


class SummaryService:
    """Service responsible for generating and validating structured document summaries."""

    @staticmethod
    def _clean_json_markdown(text: str) -> str:
        """Strips markdown code fences (```json ... ```) if emitted by the LLM."""
        text = text.strip()
        # Regex to strip ```json and ``` or ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    @classmethod
    async def generate_summary(
        cls,
        document_text: str,
        provider: Optional[LLMProvider] = None,
    ) -> DocumentSummary:
        """
        Submits document text to the LLM and validates the output strictly
        against the DocumentSummary Pydantic model.
        """
        llm = provider or get_llm_provider()

        # Truncate content to token budget if extraordinarily long for initial MVP summary
        trimmed_content = document_text[:12000]

        raw_output = await llm.generate(
            prompt=trimmed_content,
            system_prompt=DOCUMENT_SUMMARY_PROMPT_V1,
            temperature=0.1,  # Low temperature for strict adherence
        )

        cleaned_json = cls._clean_json_markdown(raw_output)

        try:
            summary = DocumentSummary.model_validate_json(cleaned_json)
            return summary
        except Exception as err:
            # Retry once or raise structured parsing error
            raise ValueError(f"LLM produced invalid structured summary JSON: {cleaned_json}") from err
