# DocMind - Development Log

## Status: Phase 4 (LLM Provider Abstraction & Prompts) COMPLETED ✅

---

### [2026-11-13] - Milestone: Phase 4 - LLM Providers, Versioned Prompts & Structured Summaries Completed

#### Completed:
1. **Unified LLM Provider Abstraction**:
   - `backend/app/services/llm/base.py`: Abstract Base Class `LLMProvider` defining async `embed()`, `generate()`, and `stream()`.
   - `backend/app/services/llm/gemini.py`: Google Gemini API implementation via async HTTP/SSE requests (supporting `gemini-1.5-flash` generation, streaming SSE, and `text-embedding-004` batch embeddings).
   - `backend/app/services/llm/ollama.py`: Local Ollama provider supporting offline chat and embedding models (`llama3`, `nomic-embed-text`).
   - `backend/app/services/llm/factory.py`: Singleton provider factory honoring `settings.LLM_PROVIDER`.
2. **Versioned Prompt Templates (FR-I4)**:
   - `backend/app/core/prompts.py`:
     - `RAG_SYSTEM_PROMPT_V1`: Factual grounding rules, strict citation requirements (`[[doc:..., page:..., chunk:...]]`), explicit refusal when context is missing, and prompt injection defense.
     - `DOCUMENT_SUMMARY_PROMPT_V1`: Strict JSON schema contract for document intelligence.
     - `format_rag_user_prompt`: Isolates document chunks inside `<document_context>` XML delimiters.
3. **Pydantic Structured Outputs (FR-I1)**:
   - `backend/app/schemas/document.py`: `DocumentSummary` Pydantic model (`title`, `summary`, `key_points`, `topics`).
   - `backend/app/services/summary_service.py`: `SummaryService.generate_summary` with automated markdown fence stripping and Pydantic validation.
4. **Automated Testing**:
   - `backend/tests/test_llm_and_prompts.py`: Tested prompt formatting XML isolation, Gemini generation & embeddings, Ollama generation, and summary parsing (success, code fence stripping, and invalid schema detection).
   - **21/21 tests passed (100% green)** across all backend test suites.

---

### Upcoming Tasks:
- [ ] **Phase 5: Document Ingestion & Core RAG Pipeline**:
  - Text extraction pipeline for PDF (pypdf), TXT, and Markdown files.
  - Overlapping chunking algorithm retaining page and chunk index metadata.
  - Asynchronous background ingestion task (`uploaded` -> `processing` -> `ready` / `failed`).
  - Scoped vector similarity search with `pgvector` (`WHERE user_id = :uid`).
  - Token-by-token streaming RAG answer generation with verifiable citations.
