# DocMind 🧠

> **AI Knowledge Assistant: Chat with your documents using grounded RAG and precise citations.**

DocMind is a full-stack, production-engineered web application that enables users to upload documents (PDF, TXT, Markdown) and have conversations with them. Every response is grounded in the documents and cites exact pages and chunks.

---

## 🛠️ Tech Stack

* **Frontend**: React (Vite + TypeScript), Tailwind CSS, TanStack Query, Lucide Icons.
* **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0 (async), Alembic, Pydantic v2.
* **Database & Vector Store**: PostgreSQL 16 with `pgvector` (HNSW indexing with cosine distance).
* **Caching & Rate Limiting**: Redis 7.
* **Authentication**: OAuth 2.0 (Google OAuth).
* **AI & LLM**: Google Gemini API / Local Ollama, custom RAG pipeline, and tool-calling agent loop.
* **DevOps**: Docker, Docker Compose, GitHub Actions, AWS.

---

## 🚀 Quickstart (Local Development)

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/) (running)
- [Python 3.11+](https://www.python.org/)
- [Node.js 18+](https://nodejs.org/)

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 3. Start Infrastructure (PostgreSQL + pgvector & Redis)
```bash
docker compose up -d postgres redis
```

### 4. Backend Setup
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 5. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

---

## 📖 Project Documentation Directory
- [PROJECT_CONTEXT.md](file:///c:/Users/shaur/OneDrive/Desktop/DocMind/PROJECT_CONTEXT.md): Vision, target personas, and scope breakdown.
- [ARCHITECTURE.md](file:///c:/Users/shaur/OneDrive/Desktop/DocMind/ARCHITECTURE.md): System diagrams, database schema, and technical layers.
- [DEVELOPMENT_LOG.md](file:///c:/Users/shaur/OneDrive/Desktop/DocMind/DEVELOPMENT_LOG.md): Living progress log and milestone tracker.
- [DECISIONS.md](file:///c:/Users/shaur/OneDrive/Desktop/DocMind/DECISIONS.md): Architectural Decision Records (ADRs).
- [AGENTS.md](file:///c:/Users/shaur/OneDrive/Desktop/DocMind/AGENTS.md): Permanent rules and instructions for Antigravity AI agents.
