# Product Requirements Document
## Local Wikipedia RAG Assistant
### BLG483E — Project 3

---

## 1. Product Overview

A fully local, ChatGPT-style Retrieval-Augmented Generation (RAG) system that answers natural language questions about famous people and places using Wikipedia as its knowledge source. Every component — ingestion, embedding, vector storage, language model inference, and the chat interface — runs on localhost with no external API calls.

---

## 2. Goals

- Ingest and index Wikipedia articles for at least 20 people and 20 places.
- Classify incoming user queries as being about a person, a place, or both using a local BERT classifier.
- Retrieve the most relevant document chunks from the appropriate vector store using cosine similarity.
- Generate grounded, hallucination-resistant answers using a local LLM via Ollama and LangChain.
- Provide a clean CLI interface for interactive Q&A.
- Persist raw document metadata in SQLite.

---

## 3. Architecture Overview

```
User Query (CLI)
      │
      ▼
┌─────────────────────┐
│  Query Classifier   │  ◄── Small BERT model (local)
│  (person/place/both)│
└────────┬────────────┘
         │
    ┌────┴────┐
    ▼         ▼
[People     [Places
 ChromaDB]   ChromaDB]
    │         │
    └────┬────┘
         │  Top-k chunks (cosine similarity)
         ▼
┌─────────────────────┐
│   LangChain RAG     │
│   Chain + Prompt    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Local LLM via     │
│   Ollama            │
└────────┬────────────┘
         │
         ▼
    Answer (CLI)
```

---

## 4. Data Requirements

### 4.1 Required Entities

**People (minimum 10, target 20+)**

| # | Name |
|---|------|
| 1 | Albert Einstein |
| 2 | Marie Curie |
| 3 | Leonardo da Vinci |
| 4 | William Shakespeare |
| 5 | Ada Lovelace |
| 6 | Nikola Tesla |
| 7 | Lionel Messi |
| 8 | Cristiano Ronaldo |
| 9 | Taylor Swift |
| 10 | Frida Kahlo |
| 11 | Isaac Newton |
| 12 | Charles Darwin |
| 13 | Cleopatra |
| 14 | Napoleon Bonaparte |
| 15 | Mahatma Gandhi |
| 16 | Nelson Mandela |
| 17 | Stephen Hawking |
| 18 | Elon Musk |
| 19 | Aristotle |
| 20 | Wolfgang Amadeus Mozart |

**Places (minimum 10, target 20+)**

| # | Name |
|---|------|
| 1 | Eiffel Tower |
| 2 | Great Wall of China |
| 3 | Taj Mahal |
| 4 | Grand Canyon |
| 5 | Machu Picchu |
| 6 | Colosseum |
| 7 | Hagia Sophia |
| 8 | Statue of Liberty |
| 9 | Pyramids of Giza |
| 10 | Mount Everest |
| 11 | Stonehenge |
| 12 | Acropolis of Athens |
| 13 | Angkor Wat |
| 14 | Chichen Itza |
| 15 | Petra |
| 16 | Sagrada Familia |
| 17 | Big Ben |
| 18 | Sydney Opera House |
| 19 | Amazon Rainforest |
| 20 | Niagara Falls |

### 4.2 Data Source
Wikipedia REST API — `https://en.wikipedia.org/api/rest_v1/page/summary/{title}` for summaries and `https://en.wikipedia.org/wiki/{title}` with HTML parsing for full article text. Raw text is stored in SQLite before chunking.

---

## 5. Technical Specifications

### 5.1 Ingestion

- Fetch Wikipedia article full text for each entity using `requests` + `BeautifulSoup`.
- Strip markup, references, and non-prose sections (infoboxes, navboxes).
- Store raw text in SQLite with fields: `id`, `title`, `type` (person|place), `url`, `raw_text`, `ingested_at`.
- Ingestion is idempotent — skip if already stored.

### 5.2 Chunking

- **Strategy:** Sliding window over word tokens.
- **Chunk size:** 2000 words.
- **Overlap:** 200 words.
- **Implementation:** Native Python — no chunking library. Split on whitespace, construct chunks manually using a sliding index.
- Each chunk carries metadata: `source_title`, `type`, `chunk_index`, `total_chunks`.
- Design assumption: documents can be arbitrarily large; the chunker streams through text without loading it all into memory at once.

### 5.3 Embedding

- **Model:** TBD — either `nomic-embed-text` served via Ollama or a `sentence-transformers` model (e.g., `all-MiniLM-L6-v2`).
- Embeddings generated locally, no external API.
- LangChain's `OllamaEmbeddings` or `HuggingFaceEmbeddings` wrapper used depending on model choice.

### 5.4 Vector Storage (Option A — Two Collections)

- **Tool:** ChromaDB (persistent, on-disk).
- **Collection 1:** `people_store` — chunks from person articles.
- **Collection 2:** `places_store` — chunks from place articles.
- **Distance metric:** Cosine similarity.
- **Design rationale for Option A:** Two separate collections allow completely isolated retrieval paths. When the classifier is confident the query is about a person, only `people_store` is queried — eliminating cross-contamination noise from place documents and vice versa. For mixed queries, both stores are queried and results are merged. This is a simple, transparent, and debuggable design that maps cleanly to the classification output.

### 5.5 Query Classification

- **Model:** Small BERT-family model (e.g., `prajjwal1/bert-tiny` or `bert-base-uncased` fine-tuned on intent classification), loaded locally via `transformers`.
- **Labels:** `person`, `place`, `both`.
- **Fallback:** If confidence is below a threshold (e.g., 0.6), classify as `both` and query both stores.
- **Implementation note:** A lightweight keyword-based pre-filter runs first (name matching against known entity lists). The BERT model handles ambiguous cases.

### 5.6 Retrieval

- **Method:** Cosine similarity vector search via ChromaDB's `.query()`.
- **Top-k:** Retrieve top 5 chunks per store.
- **For `both` queries:** Retrieve top 5 from each store, merge, deduplicate, re-rank by score, take top 5 overall.
- LangChain `Chroma` retriever wraps the collection for integration into the RAG chain.

### 5.7 Generation

- **Runtime:** Ollama (local HTTP server at `localhost:11434`).
- **Model:** TBD — candidates are `llama3.2:3b`, `phi3`, `mistral`. Final choice determined after benchmarking on the required example questions.
- **Framework:** LangChain `RetrievalQA` or `ConversationalRetrievalChain`.
- **Prompt template:**
  ```
  You are a helpful assistant. Answer the question using ONLY the provided context.
  If the answer is not in the context, respond with "I don't know."
  Do not make up information.

  Context:
  {context}

  Question: {question}
  Answer:
  ```
- Source chunks optionally displayed after the answer.

### 5.8 SQLite Database Schema

```sql
CREATE TABLE documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('person', 'place')),
    url         TEXT,
    raw_text    TEXT NOT NULL,
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER REFERENCES documents(id),
    chunk_index  INTEGER NOT NULL,
    chunk_text   TEXT NOT NULL,
    embedded     BOOLEAN DEFAULT FALSE
);
```

### 5.9 CLI Interface

Commands available at the prompt:

| Command | Action |
|---------|--------|
| `<question>` | Ask a question and receive an answer |
| `/sources` | Toggle display of source chunks |
| `/reset` | Clear conversation history |
| `/ingest` | Re-run ingestion pipeline |
| `/quit` or `exit` | Exit the application |

---

## 6. Multi-Agent Development Workflow

The system is built using a multi-agent workflow where each agent has a distinct role and responsibility. Agents collaborate sequentially with defined handoffs.

### 6.1 Agent Roster

#### Agent 1: Architect
**Responsibility:** System design and technical decision-making.
- Defines overall pipeline (ingest → chunk → embed → store → retrieve → generate).
- Selects technology stack and justifies choices.
- Designs ChromaDB collection schema, SQLite schema, and LangChain chain structure.
- Produces architecture diagrams and component interface contracts.
- Makes final call on model selection (embedding model, LLM) after reviewing benchmarks from the Tester.
- **Inputs:** PRD, assignment constraints.
- **Outputs:** Architecture document, interface specs, technology decisions.

#### Agent 2: Data Engineer
**Responsibility:** Wikipedia ingestion pipeline and data quality.
- Implements the Wikipedia fetcher, HTML parser, and text cleaner.
- Implements the SQLite persistence layer.
- Implements the chunker (2000-word sliding window, 200-word overlap).
- Ensures ingestion is idempotent and handles network errors gracefully.
- **Inputs:** Architecture document, entity list.
- **Outputs:** `ingest.py`, `chunker.py`, populated SQLite database.
- **Why this role exists:** Ingestion is non-trivial — Wikipedia HTML is messy, article sizes vary enormously, and the chunking strategy directly impacts retrieval quality. Separating this concern from the main application engineer prevents context overload and keeps the pipeline independently testable.

#### Agent 3: Software Engineer
**Responsibility:** Core RAG application implementation.
- Implements the BERT query classifier.
- Implements the ChromaDB embedding and storage pipeline.
- Implements the LangChain retrieval chain (retriever, prompt, LLM binding).
- Implements the CLI interface.
- Integrates all components into a runnable application.
- **Inputs:** Architecture document, outputs from Data Engineer.
- **Outputs:** `classifier.py`, `embedder.py`, `retriever.py`, `generator.py`, `app.py`.

#### Agent 4: Prompt Engineer
**Responsibility:** LLM prompt design and optimization.
- Designs the generation prompt template to minimize hallucination and enforce grounding.
- Designs the system prompt and context formatting for the LLM.
- Iterates on prompt wording to improve answer quality on the required example questions.
- Documents prompt design rationale.
- **Inputs:** Example questions from the assignment, retrieved chunk format.
- **Outputs:** Final prompt templates, prompt design notes.
- **Why this role exists:** Prompt quality is the single biggest lever on RAG answer quality given a fixed retrieval setup. A dedicated agent iterating on prompts independently is more effective than having the Software Engineer handle it alongside implementation work.

#### Agent 5: Code Reviewer
**Responsibility:** Code quality, correctness, and security.
- Reviews all code produced by the Software Engineer and Data Engineer.
- Checks for correctness against the architecture spec.
- Flags security issues (e.g., SQL injection, unsafe subprocess calls).
- Flags violations of the assignment constraint (no external APIs, use native language functionality where possible).
- Ensures error handling covers real failure modes (Ollama not running, ChromaDB corruption, Wikipedia fetch failure).
- **Inputs:** All source files.
- **Outputs:** Review comments, required changes list, approved code.

#### Agent 6: Tester
**Responsibility:** Verification and benchmarking.
- Writes and runs tests for each component (chunker, classifier, retriever, generator).
- Runs the full required question set from the assignment and validates answers.
- Tests failure cases ("Who is the president of Mars", "Tell me about John Doe").
- Benchmarks latency per query end-to-end.
- Tests across model options (llama3.2:3b, phi3, mistral) and reports quality/speed tradeoffs to the Architect.
- **Inputs:** Running application, required question list.
- **Outputs:** Test report, model comparison table, confirmed pass/fail for all required queries.

#### Agent 7: Documenter
**Responsibility:** All written deliverables.
- Writes `README.md` (setup, install, run, example queries).
- Writes `recommendation.md` (production deployment strategy).
- Writes inline docstrings for public functions (one-line, non-obvious only).
- Ensures the repository is organized and the README is self-sufficient for the instructor.
- **Inputs:** Final codebase, Tester's report, Architect's decisions.
- **Outputs:** `README.md`, `recommendation.md`, organized repo structure.

### 6.2 Agent Interaction Flow

```
PRD
 │
 ▼
Architect ──────────────────────────────────────┐
 │ architecture doc + interface specs            │
 ├──────────────────────┐                       │
 ▼                      ▼                       │
Data Engineer      Prompt Engineer               │
 │ ingest + chunks   │ prompt templates          │
 ▼                   ▼                           │
Software Engineer ◄─────────────────────────────┘
 │ full codebase
 ▼
Code Reviewer
 │ approved code + change requests
 ▼
Software Engineer (revisions)
 │
 ▼
Tester ──────────────────────────────────────► Architect
 │ test results + model benchmarks              (model selection finalized)
 ▼
Documenter
 │
 ▼
Final deliverable
```

---

## 7. File Structure

```
wiki-rag/
├── app.py                  # CLI entry point
├── ingest.py               # Wikipedia fetch + SQLite persistence
├── chunker.py              # Sliding window text splitter
├── embedder.py             # Embedding + ChromaDB population
├── classifier.py           # BERT query classifier (person/place/both)
├── retriever.py            # ChromaDB retrieval logic
├── generator.py            # LangChain RAG chain + Ollama LLM
├── prompts.py              # Prompt templates
├── db/
│   └── wiki.db             # SQLite database
├── chroma/
│   ├── people_store/       # ChromaDB people collection
│   └── places_store/       # ChromaDB places collection
├── requirements.txt
├── README.md
├── product_prd.md
└── recommendation.md
```

---

## 8. Success Criteria

| Criterion | Target |
|-----------|--------|
| All required people ingested | 10/10 |
| All required places ingested | 10/10 |
| Total entities | ≥ 40 (20 people + 20 places) |
| Required example questions answered correctly | ≥ 90% |
| Failure cases return "I don't know" | 100% |
| System runs fully on localhost | Yes |
| No external API calls | Verified |
| CLI functional | Yes |
| Query latency (end-to-end) | < 30s on CPU |

---

## 9. Constraints

- No external LLM or embedding APIs (OpenAI, Cohere, Hugging Face Inference API, etc.).
- All models run via Ollama or loaded locally via `transformers`/`sentence-transformers`.
- Core logic (chunking, retrieval routing, query classification) must use language-native implementations, not high-level wrappers that abstract away the exercise.
- LangChain is permitted for RAG chain orchestration only.
- System must be reproducible by the instructor following README instructions alone.

---

## 10. Optional Extensions (Post-Core)

- Streaming LLM responses via Ollama streaming API.
- Source chunk display with highlighting in CLI.
- Conversation memory (multi-turn context).
- Response caching (SQLite cache keyed on query hash).
- Side-by-side model comparison (two Ollama models, one query).
- Latency instrumentation and display per pipeline stage.
- Improved retrieval ranking (score threshold filtering, MMR reranking).
- Comparison query support ("Compare X and Y") with multi-entity retrieval.
