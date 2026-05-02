# Production Deployment Recommendation

## Current State (Local Prototype)

The current system runs entirely on a single machine:
- **SQLite** for article and chunk metadata
- **ChromaDB** (file-based) for vector storage
- **Ollama** for local LLM inference (`llama3.2:3b`)
- **sentence-transformers `all-MiniLM-L6-v2`** for embeddings (384 dimensions)
- **gemma3:1b via Ollama** for query lassification
- **Python CLI** as the user interface


## Recommended Production Stack

### 1. Vector Store → Qdrant

Replace ChromaDB with **Qdrant**, a dedicated production vector database.

ChromaDB is designed for local development — it stores vectors as files on disk and has no support for concurrent multi-user access. Under load, multiple simultaneous queries will cause slowdowns or data corruption.

Qdrant addresses all of this:
- Runs as a standalone server (Docker-native), separate from your application
- Supports **filtered search** — e.g., retrieve only person vectors, only place vectors, or both, in a single collection with metadata filters. This simplifies the two-collection design into one collection with a `category` field filter.
- Scales horizontally: you can add more Qdrant nodes and it will shard and replicate data automatically
- Exposes a clean REST and gRPC API, with an official Python client

---

### 2. Relational Database → PostgreSQL

Replace SQLite with **PostgreSQL**.

SQLite is a file-based database that serializes all writes through a single lock. It works for one user but fails under concurrent access — two users triggering ingestion at the same time will cause lock errors.

---
### 3. Embedding Model → Larger, Stronger Model via API

**Recommended upgrade:** Use a model with higher embedding dimensions and stronger semantic understanding:
- **`embed-v3`** (Cohere API) — 1024 dimensions, excellent multilingual support

Higher dimensions mean the model captures more nuance in meaning, so retrieval precision improves significantly — especially for ambiguous or multi-part questions.

---

### 4. Language Model → Stronger LLM via API
Replace `llama3.2:3b` with a larger, more capable model accessed through an API.

- **Llama 3.1 70B** via Groq or Together AI — open-weight model, API-hosted, much stronger than 3B
Using an API means you pay per token but eliminate local GPU/CPU requirements entirely, get responses in 1–3 seconds instead of 30+, and benefit from continuous model improvements.

---

### 5. Query Classifier → Fine-tuned BERT

Replace the current gemma3:1b few-shot classifier with a **fine-tuned BERT model**.

The current approach asks a general-purpose LLM to classify queries, which adds ~1–2 seconds of latency per query and is overkill for a 3-label classification task. BERT-family models trained specifically for classification are:

- **Much faster** — inference in milliseconds, not seconds
- **More consistent** — deterministic output, no risk of the model returning an unexpected word
- **Smaller** — a fine-tuned `bert-base-uncased` classifier is ~400 MB vs. 815 MB for gemma3:1b

---

### 6. Interface → FastAPI + WebSocket + Web Frontend

Replace the CLI with a **REST API and web application**.

A CLI is not usable by non-technical users and cannot support multiple simultaneous users. A FastAPI backend with a simple web frontend makes the system accessible from any browser.

**API endpoints:**
- `POST /query` — accepts a question, returns answer + source chunks as JSON
- `POST /ingest` — triggers the ingestion pipeline (admin-only)
- `GET /health` — health check for load balancers

**WebSocket for streaming:** Rather than waiting for the full answer before displaying anything, a WebSocket connection lets the frontend render tokens as they arrive — the same experience as ChatGPT. FastAPI has built-in WebSocket support:

**Frontend:** A minimal HTML/JS page with a chat interface is sufficient. For a richer experience, a React or Vue app connects to the WebSocket and renders markdown-formatted answers in real time.

---

## Summary

| Component | Current (Prototype) | Production |
|-----------|-------------------|------------|
| Vector DB | ChromaDB (file) | Qdrant (server) |
| Metadata DB | SQLite | PostgreSQL |
| Embedding model | all-MiniLM-L6-v2 (384d) | nomic-embed-text or text-embedding-3-arge (768–3072d) |
| Generation LLM | llama3.2:3b (local, slow) | Claude / GPT-4o / Llama 70B via API || Query classifier | gemma3:1b few-shot (slow) | Fine-tuned BERT (milliseconds) |
| Interface | Python CLI | FastAPI + WebSocket + Web UI |
