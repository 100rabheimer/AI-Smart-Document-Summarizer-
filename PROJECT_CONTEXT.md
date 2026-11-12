# DocMind - Project Context

## 1. What is DocMind?
DocMind is a production-grade, full-stack AI knowledge assistant web application where users upload documents (PDF, TXT, Markdown) and chat with them using Retrieval-Augmented Generation (RAG). 

Crucially, every answer is grounded in the uploaded files and displays precise citations pointing back to the exact document chunks and page references used to construct the answer.

## 2. Learning & Portfolio Mission
DocMind is built **brick by brick** as an educational and portfolio masterpiece. Every core backend, DevOps, distributed system, and GenAI engineering concept is implemented in a real, working system rather than isolated or toy tutorials.

## 3. Core Objectives
- **Grounded & Cited QA**: Provide trustworthy, hallucination-resistant answers with verifiable source citations.
- **Real-World Authentication**: OAuth 2.0 authentication (e.g., Google OAuth) to support authentic email identity verification and secure multi-tenant isolation.
- **Production Backend Architecture**: Multi-tenant database design, Redis caching, sliding-window rate limiting, request idempotency, structured logging, and comprehensive test coverage (target: $\ge 80\%$).
- **End-to-End GenAI Stack**: Chunking strategies, vector embeddings, similarity search with `pgvector`, prompt versioning, structured Pydantic outputs, tool-calling agents, memory management, and golden-dataset evaluations.
- **Robust DevOps**: Containerized local environment (`docker-compose`), multi-stage Docker builds, automated CI/CD pipeline via GitHub Actions, and AWS cloud deployment.

## 4. In-Scope vs. Out-of-Scope (MVP)

### In-Scope (MVP)
- **Auth**: OAuth 2.0 (Google Login), secure session management, tenant isolation.
- **Documents**: Upload PDF, TXT, Markdown (up to 10 MB); SHA-256 content deduplication; idempotent uploads; background text extraction, chunking, and embedding.
- **RAG & Chat**: Streaming token-by-token responses (SSE); citations with document name, page, and chunk index; strict refusal when answers are not in documents; chat history persistence; query caching in Redis.
- **AI Features**: Pydantic structured document summaries; agent mode with function calling (`search_documents`, `calculator`, `web_search`); short-term conversation sliding window + long-term user memory; golden eval harness.
- **Infrastructure**: FastAPI, React (Vite + TS), PostgreSQL + `pgvector`, Redis, Docker Compose.

### Out-of-Scope (Non-Goals for MVP)
- Model fine-tuning (LoRA / full fine-tuning).
- Document sharing across multiple users / team workspaces.
- Real-time collaborative document editing.
- Native mobile applications.
- Paid billing/subscription gateways.
