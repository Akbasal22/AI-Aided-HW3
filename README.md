# Local Wikipedia RAG Assistant

A fully local ChatGPT-style system that answers questions about famous people and places using Wikipedia as its knowledge base. No external APIs — everything runs on your machine.

---

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running

---

## 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Run the Local Language Model

Install Ollama from https://ollama.com/download, then:

```bash
# Start the Ollama server (runs in background)
ollama serve

# Pull the language model (do this once)
ollama pull llama3.2:3b
```

Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

---

## 3. Start the Application

```bash
python app.py
```

---

## 4. Ingest Wikipedia Data

On first run, ingest all 40 Wikipedia articles (20 people + 20 places):

```
You: /ingest
```

This fetches Wikipedia pages, chunks them, generates embeddings, and stores everything locally. Takes a few minutes on first run.

---

## 5. Ask Questions

```
You: Who was Albert Einstein and what is he known for?
You: Where is the Eiffel Tower located?
You: Compare Lionel Messi and Cristiano Ronaldo
You: Which famous place is located in Turkey?
You: What was the Colosseum used for?
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `/ingest` | Ingest and embed all Wikipedia articles |
| `/sources` | Show sources used for the last answer |
| `/reset` | Clear the screen |
| `/quit` | Exit the application |

---

## System Architecture

```
User Query
    │
    ▼
Query Classifier (BERT zero-shot)
    │ "person" / "place" / "both"
    ▼
ChromaDB Vector Search (cosine similarity)
    ├── people_store  (person queries)
    └── places_store  (place queries)
    │ Top-5 relevant chunks
    ▼
LangChain RAG Chain
    │
    ▼
Ollama LLM (llama3.2:3b) → Answer
```

**Key design decisions:**
- **Two ChromaDB collections** (Option A): clean separation of person vs. place data, eliminates cross-contamination in retrieval
- **BERT zero-shot classifier** with keyword pre-filter: fast path for known entity names, BERT fallback for ambiguous queries
- **2000-word chunks, 200-word overlap**: balances context richness with embedding quality
- **sentence-transformers `all-MiniLM-L6-v2`**: fast, accurate, CPU-friendly embeddings
- **Cosine similarity**: normalized embeddings ensure correct distance metric behavior

---

## Data

All data is stored locally:
- `wiki_rag.db` — SQLite database with raw article text and chunk metadata
- `./chroma_store/` — ChromaDB persistent vector store

---

## Example Failure Cases

The system correctly returns "I don't have enough information..." for:
- `Who is the president of Mars?`
- `Tell me about John Doe`
