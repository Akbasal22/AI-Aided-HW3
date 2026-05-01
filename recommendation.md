# Production Deployment Recommendation

## Current State (Local Prototype)

The current system runs entirely on a single machine:
- **SQLite** for article and chunk metadata
- **ChromaDB** (file-based) for vector storage
- **Ollama** for local LLM inference (`llama3.2:3b`)
- **sentence-transformers `all-MiniLM-L6-v2`** for embeddings (384 dimensions)
- **gemma3:1b via Ollama** for query classification
- **Python CLI** as the user interface

This setup is great for a single-user prototype. Scaling it to handle multiple users, larger knowledge bases, and production-grade answer quality requires changes across every layer.

---

## Recommended Production Stack

### 1. Vector Store → Qdrant

Replace ChromaDB with **Qdrant**, a dedicated production vector database.

ChromaDB is designed for local development — it stores vectors as files on disk and has no support for concurrent multi-user access. Under load, multiple simultaneous queries will cause slowdowns or data corruption.

Qdrant addresses all of this:
- Runs as a standalone server (Docker-native), separate from your application
- Supports **filtered search** — e.g., retrieve only person vectors, only place vectors, or both, in a single collection with metadata filters. This simplifies the two-collection design into one collection with a `category` field filter.
- Scales horizontally: you can add more Qdrant nodes and it will shard and replicate data automatically
- Exposes a clean REST and gRPC API, with an official Python client

```bash
docker run -p 6333:6333 qdrant/qdrant
```

```python
from qdrant_client import QdrantClient
client = QdrantClient(host="localhost", port=6333)
```

---

### 2. Relational Database → PostgreSQL

Replace SQLite with **PostgreSQL**.

SQLite is a file-based database that serializes all writes through a single lock. It works for one user but fails under concurrent access — two users triggering ingestion at the same time will cause lock errors.

PostgreSQL is the standard choice for production Python applications:
- Full concurrent read/write support
- Connection pooling via `pgBouncer` for high-traffic scenarios
- Supports `asyncpg` for async FastAPI integration
- Can store large text (raw article HTML, cleaned text) without file-size limits
- Easy to back up, replicate, and monitor

```python
import psycopg2
conn = psycopg2.connect("postgresql://user:password@localhost/wikirag")
```

---

### 3. Embedding Model → Larger, Stronger Model via API

Replace `all-MiniLM-L6-v2` (384 dimensions) with a higher-quality embedding model.

`all-MiniLM-L6-v2` is fast and lightweight but produces relatively low-dimensional vectors (384). This limits how precisely similar chunks are ranked — two chunks can appear close in vector space even when one is much more relevant than the other.

**Recommended upgrade:** Use a model with higher embedding dimensions and stronger semantic understanding:

- **`text-embedding-3-large`** (OpenAI API) — 3072 dimensions, state-of-the-art retrieval quality
- **`embed-v3`** (Cohere API) — 1024 dimensions, excellent multilingual support
- **`nomic-embed-text-v1.5`** (open-source, self-hostable) — 768 dimensions, strong performance, no API cost

Higher dimensions mean the model captures more nuance in meaning, so retrieval precision improves significantly — especially for ambiguous or multi-part questions.

If keeping everything local, `nomic-embed-text-v1.5` via Ollama is the best upgrade path:
```bash
ollama pull nomic-embed-text
```

If an API is acceptable, OpenAI's embedding API gives the best quality:
```python
from openai import OpenAI
client = OpenAI()
response = client.embeddings.create(input=query, model="text-embedding-3-large")
vector = response.data[0].embedding  # 3072 dimensions
```

---

### 4. Language Model → Stronger LLM via API

Replace `llama3.2:3b` with a larger, more capable model accessed through an API.

`llama3.2:3b` has only 3 billion parameters and runs on CPU. It is slow and produces answers that are sometimes incomplete, poorly structured, or miss nuance in the context. A 3B model simply does not have enough capacity to reliably synthesize multi-paragraph Wikipedia excerpts into a high-quality answer.

**Recommended options:**

- **Claude 3.5 Haiku** (Anthropic API) — fast, inexpensive, excellent at following grounding instructions ("only use the provided context")
- **GPT-4o mini** (OpenAI API) — similar quality/cost profile, widely supported
- **Llama 3.1 70B** via Groq or Together AI — open-weight model, API-hosted, much stronger than 3B

Using an API means you pay per token but eliminate local GPU/CPU requirements entirely, get responses in 1–3 seconds instead of 30+, and benefit from continuous model improvements.

```python
from anthropic import Anthropic
client = Anthropic()
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    messages=[{"role": "user", "content": prompt}]
)
answer = response.content[0].text
```

---

### 5. Query Classifier → Fine-tuned BERT

Replace the current gemma3:1b few-shot classifier with a **fine-tuned BERT model**.

The current approach asks a general-purpose LLM to classify queries, which adds ~1–2 seconds of latency per query and is overkill for a 3-label classification task. BERT-family models trained specifically for classification are:

- **Much faster** — inference in milliseconds, not seconds
- **More consistent** — deterministic output, no risk of the model returning an unexpected word
- **Smaller** — a fine-tuned `bert-base-uncased` classifier is ~400 MB vs. 815 MB for gemma3:1b

The approach is to fine-tune `bert-base-uncased` (or `distilbert-base-uncased` for speed) on a small labeled dataset of person/place/both/irrelevant queries. Even 200–300 labeled examples are enough for a 3-label classifier to reach high accuracy.

```python
from transformers import pipeline
classifier = pipeline("text-classification", model="your-org/wikirag-query-classifier")
result = classifier("Who built the Hagia Sophia?")
# → [{"label": "place", "score": 0.97}]
```

Once fine-tuned and uploaded to the Hugging Face Hub, it loads once at startup and classifies in milliseconds with no Ollama dependency.

---

### 6. Interface → FastAPI + WebSocket + Web Frontend

Replace the CLI with a **REST API and web application**.

A CLI is not usable by non-technical users and cannot support multiple simultaneous users. A FastAPI backend with a simple web frontend makes the system accessible from any browser.

**API endpoints:**
- `POST /query` — accepts a question, returns answer + source chunks as JSON
- `POST /ingest` — triggers the ingestion pipeline (admin-only)
- `GET /health` — health check for load balancers

**WebSocket for streaming:** Rather than waiting for the full answer before displaying anything, a WebSocket connection lets the frontend render tokens as they arrive — the same experience as ChatGPT. FastAPI has built-in WebSocket support:

```python
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws/query")
async def query_ws(websocket: WebSocket):
    await websocket.accept()
    query = await websocket.receive_text()
    async for token in llm.astream(query):
        await websocket.send_text(token)
```

**Frontend:** A minimal HTML/JS page with a chat interface is sufficient. For a richer experience, a React or Vue app connects to the WebSocket and renders markdown-formatted answers in real time.

---

## Summary

| Component | Current (Prototype) | Production |
|-----------|-------------------|------------|
| Vector DB | ChromaDB (file) | Qdrant (server) |
| Metadata DB | SQLite | PostgreSQL |
| Embedding model | all-MiniLM-L6-v2 (384d) | nomic-embed-text or text-embedding-3-large (768–3072d) |
| Generation LLM | llama3.2:3b (local, slow) | Claude / GPT-4o / Llama 70B via API |
| Query classifier | gemma3:1b few-shot (slow) | Fine-tuned BERT (milliseconds) |
| Interface | Python CLI | FastAPI + WebSocket + Web UI |

Each of these changes can be made independently — you do not need to upgrade everything at once. The highest-impact first steps are upgrading the LLM (biggest answer quality gain) and adding the FastAPI layer (enables multi-user access).
