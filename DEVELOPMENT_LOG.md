# DocMind - Development Log

## Status: Phase 5 (Document Ingestion & Core RAG Pipeline) COMPLETED ✅

---

### [2026-11-13] - Milestone: Phase 5 - Document Ingestion, Overlapping Chunking, pgvector & Streaming Citations Completed

#### Completed:
1. **Document Parsing & Chunking Engine**:
   - `backend/app/services/document_parser.py`: Multi-format text extraction (`pypdf` for page-by-page PDF extraction, UTF-8 handler for Markdown/TXT). Implemented recursive character splitting with configurable chunk size and overlap (e.g. 1000 characters, 200 overlap), preserving exact `page` and sequential `chunk_index`.
2. **Multi-Tenant Vector Repository Layer**:
   - `backend/app/repositories/document_repo.py`:
     - Multi-tenant CRUD operations strictly scoped to `user_id`.
     - Fast bulk chunk insertion via `create_chunks_batch`.
     - High-speed vector similarity search using `pgvector`'s `<=>` cosine distance operator against the HNSW index (`WHERE user_id = :uid`).
3. **Background Ingestion & Caching State**:
   - `backend/app/services/document_service.py`: Enforces max file size (10 MB), computes SHA-256 content hashes to detect and prevent duplicate uploads, writes to disk, and runs background text extraction, embedding generation, and DB insertion. Bumps `docs_version` in Redis upon completion for instant $O(1)$ query cache invalidation.
4. **Streaming RAG & Citation Tracking Engine**:
   - `backend/app/services/rag_service.py`:
     - Checks Redis for cached queries under current `docs_version`.
     - Embeds question and executes user-scoped `pgvector` similarity search.
     - Enforces refusal guardrail if no relevant chunks are found.
     - Assembles injection-resistant XML prompt (`<document_context>`).
     - Streams real-time tokens via Server-Sent Events (SSE).
     - Regex-parses verifiable citation markers (`[[doc:filename, page:X, chunk:Y]]`), persists turn to `messages` table in PostgreSQL as `JSONB`, and caches answer in Redis.
5. **REST Endpoints for Documents & Conversations**:
   - `backend/app/routers/documents.py`: `POST /documents` (supports `Idempotency-Key` and rate limiting), `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}`, and `POST /documents/{id}/summary`.
   - `backend/app/routers/chat.py`: `POST /conversations`, `GET /conversations`, `GET /conversations/{id}/messages`, and `POST /conversations/{id}/messages` (streaming SSE).
6. **Automated Testing Suite**:
   - `backend/tests/test_rag_pipeline.py`: Tested text extraction, overlapping chunking, citation parsing, duplicate upload prevention, explicit refusal on missing chunks, and full streaming SSE token delivery with citations.
   - **All 27 backend unit tests passing (100% green)**.

---

### Upcoming Tasks:
- [ ] **Phase 6: AI Agents, Tools & Memory**:
  - ReAct agent loop with max execution steps and timeout bounds.
  - Tool calling support: `search_documents`, `calculator`, `web_search`.
  - Short-term sliding window memory + long-term user preferences in `user_memories`.
