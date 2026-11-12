# DocMind - Permanent Agent Instructions (AGENTS.md)

## Core Philosophy & Collaboration Rules
1. **Brick by Brick, Educational Approach**:
   - The user is learning production-grade engineering while building DocMind.
   - **Never dump massive, unexplainable code blocks all at once.**
   - Before implementing any significant feature, explain the **concept and "why"** clearly and concisely.
   - Build iteratively: implement one layer, verify it, test it, and confirm understanding before moving to the next.

2. **Technology Stack Adherence**:
   - **Frontend**: React (Vite + TypeScript + Tailwind CSS). Do NOT use Next.js.
   - **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0 (async), Alembic, Pydantic v2.
   - **Database**: PostgreSQL 16 with `pgvector` extension.
   - **Cache & State**: Redis 7.
   - **Authentication**: OAuth 2.0 (Google OAuth) for authentic email accounts and user session management.
   - **AI**: Gemini API / Ollama behind a custom `LLMProvider` abstraction.

3. **Multi-Tenancy & Data Security**:
   - Never query chunks, documents, or chat history without filtering strictly by `user_id`.
   - Prevent indirect prompt injection by delimiting and isolating user document content from system instructions.

4. **Code Quality & Testing**:
   - Maintain a clean layered architecture: `routers/` $\rightarrow$ `services/` $\rightarrow$ `repositories/` $\rightarrow$ `models/`.
   - Aim for $\ge 80\%$ test coverage on backend business logic using `pytest`.
   - Ensure all database migrations are managed via Alembic.

5. **Context Maintenance**:
   - Whenever completing a major task or milestone, update `DEVELOPMENT_LOG.md`.
   - If an architectural trade-off or pivot is made, document it in `DECISIONS.md`.
   - Always check `PROJECT_CONTEXT.md` and `ARCHITECTURE.md` before making design decisions.
