# DocMind - Technical Decisions Log (ADR)

## ADR-001: Frontend Framework - React (Vite + TypeScript) instead of Next.js
* **Date**: 2026-11-12
* **Status**: Accepted
* **Context**: The original PRD suggested Next.js. However, the user is building this as an in-depth learning journey.
* **Decision**: Use **React (Vite + TypeScript + Tailwind CSS)** for the frontend client.
* **Rationale**:
  - Eliminates server-side framework magic and black-box abstractions.
  - Exposes the pure mechanics of client-side routing, token/cookie storage, Server-Sent Events (SSE) streaming consumption, and modular state management.
  - Ultra-fast developer feedback loop via Vite.

---

## ADR-002: Authentication Strategy - OAuth 2.0 (Google OAuth) instead of custom Email/Password JWT
* **Date**: 2026-11-12
* **Status**: Accepted
* **Context**: The PRD outlined bcrypt hashing and custom email/password registration with JWT refresh token rotation.
* **Decision**: Adopt **OAuth 2.0 (Google Login)** with verified real email accounts, backed by secure session/token management in PostgreSQL.
* **Rationale**:
  - Real-world production relevance: modern SaaS applications predominantly use OAuth/SSO rather than storing raw password hashes.
  - Guarantees authentic email addresses without having to build and maintain email-verification SMTP infrastructure.
  - Teaches the exact mechanics of OAuth 2.0 (authorization code exchange, identity token verification, user provisioning, and state/PKCE security).

---

## ADR-003: Vector Database - PostgreSQL + `pgvector`
* **Date**: 2026-11-12
* **Status**: Accepted
* **Context**: Need a scalable vector storage solution with strong metadata filtering and multi-tenancy.
* **Decision**: Use `pgvector` inside the primary PostgreSQL database rather than a standalone vector database (e.g. Pinecone, Chroma).
* **Rationale**:
  - Transactional consistency (ACID): Document metadata, chunks, and vector embeddings reside in the exact same database. Deleting a document removes chunks and embeddings in a single atomic transaction.
  - Zero extra infrastructure overhead: One database service hosts users, sessions, documents, and vector search.
  - Native tenant filtering: Simple SQL `WHERE user_id = :uid` avoids complex vector namespace or collection routing.

---

## ADR-004: Cache Invalidation Strategy - Version Counter Pattern
* **Date**: 2026-11-12
* **Status**: Accepted
* **Context**: Caching RAG responses is critical for latency and cost savings, but answers must invalidate immediately when documents are added or removed.
* **Decision**: Maintain a `docs_version` integer in Redis per user. Cache keys incorporate `docs_version`.
* **Rationale**:
  - Scanning and pattern-deleting thousands of Redis keys on every document upload is slow and causes Redis latency spikes ($O(N)$ operations).
  - Bumping an integer counter is an instantaneous $O(1)$ operation. Stale query caches are immediately disconnected and left to expire automatically via TTL.

---

## ADR-005: LLM Abstraction Layer
* **Date**: 2026-11-12
* **Status**: Accepted
* **Context**: System should support cloud LLMs (Gemini API) and local options (Ollama) interchangeably.
* **Decision**: Create an explicit `LLMProvider` protocol/interface. The embedding model and its dimensions ($N$) are fixed at configuration time, while chat/generation models can be toggled without re-indexing.
* **Rationale**:
  - Decouples business logic from external SDKs.
  - Vectors across different embedding models are mathematically incompatible; fixing the embedding model prevents runtime index corruption.
