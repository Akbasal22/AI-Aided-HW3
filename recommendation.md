# Production Deployment Recommendation

## Current State (Local Dev)

The current system is a single-machine prototype:
- SQLite for metadata storage
- ChromaDB (file-based) for vectors
- Ollama for local LLM inference
- sentence-transformers for CPU-based embeddings
- Python CLI

This works well for a single user on a laptop. Moving to production requires addressing scalability, reliability, and latency.

---

## Recommended Production Stack

### 1. Vector Store → Qdrant or Weaviate

Replace ChromaDB with a dedicated vector database server:

- **Qdrant** (recommended): production-grade, supports filtering, horizontal scaling, built-in cosine similarity, Docker-native
- **Weaviate**: good if you need hybrid (keyword + vector) search out of the box

```bash
docker run -p 6333:6333 qdrant/qdrant
```

ChromaDB is excellent for local dev but not designed for concurrent multi-user production workloads.

### 2. Relational Database → PostgreSQL

Replace SQLite with PostgreSQL:
- Handles concurrent reads/writes
- Better for multi-service architectures
- Use `asyncpg` or `psycopg2` for async access
- SQLite's WAL mode handles single-user concurrency fine but breaks under load

### 3. LLM Inference → vLLM or TGI

Replace Ollama with a production inference server:

- **vLLM**: best throughput for batched requests, continuous batching, GPU-optimized
- **TGI (Text Generation Inference)** by Hugging Face: easy Docker deploy, streaming, quantization support
- Both expose OpenAI-compatible APIs — minimal code change needed (just swap `base_url`)

```bash
docker run --gpus all -p 8080:80 ghcr.io/huggingface/text-generation-inference \
  --model-id meta-llama/Llama-3.2-3B-Instruct
```

For cost-effective production without GPUs, use a quantized model (GGUF Q4) via llama.cpp server.

### 4. Embeddings → Dedicated Embedding Service

Run `sentence-transformers` as a separate microservice (e.g., with FastAPI) or use:
- **Infinity** (MIT): production embedding server for sentence-transformers models, batching built-in
- Keeps embedding compute isolated from application logic

### 5. Caching → Redis

Add a Redis cache layer keyed on query hash:
- Cache classifier results (query → category)
- Cache retrieval results (query → chunk IDs)
- Cache full answers for repeated questions
- TTL of 1 hour is reasonable for Wikipedia-sourced data

### 6. API Layer → FastAPI

Replace the CLI with a REST API:
- `POST /query` → returns answer + sources
- `POST /ingest` → triggers ingestion pipeline
- `GET /status` → health check
- Add WebSocket support for streaming responses

### 7. Containerization → Docker Compose

```yaml
services:
  app:        # FastAPI application
  qdrant:     # Vector store
  postgres:   # Metadata store
  redis:      # Cache
  vllm:       # LLM inference
  embedding:  # Embedding service
```

---

## Deployment Architecture

```
User Request
     │
     ▼
API Gateway (nginx / Traefik)
     │
     ▼
FastAPI App (multiple replicas)
     ├── Redis Cache ──────────────► Cache Hit → Return immediately
     │
     ├── Qdrant (vector search)
     ├── PostgreSQL (metadata)
     ├── Embedding Service (Infinity)
     └── vLLM / TGI (LLM inference)
```

---

## Scaling Considerations

| Component | Scaling Strategy |
|-----------|-----------------|
| FastAPI app | Horizontal (multiple instances behind load balancer) |
| Qdrant | Distributed mode with sharding |
| PostgreSQL | Read replicas for query-heavy workload |
| vLLM | GPU vertical scaling; multi-GPU tensor parallelism |
| Embedding | CPU horizontal scaling (embeddings are cheap) |

---

## Monitoring

- **Latency**: instrument each pipeline stage (classify, retrieve, embed, generate)
- **Quality**: log retrieval distances; flag queries where all distances > 0.7 (low confidence)
- **Errors**: track Ollama/vLLM timeout rate
- Use Prometheus + Grafana or a managed observability platform

---

## Security

- No user data should leave the server (fully local is a strength — keep it)
- Rate limit the `/query` endpoint
- Sanitize inputs before passing to the LLM prompt
- If deploying internally, add JWT/OAuth2 authentication to the API layer

---

## Summary

| Concern | Local (Current) | Production |
|---------|----------------|------------|
| Vector DB | ChromaDB (file) | Qdrant |
| Metadata | SQLite | PostgreSQL |
| LLM | Ollama | vLLM / TGI |
| Embeddings | In-process | Infinity service |
| Cache | None | Redis |
| Interface | CLI | FastAPI + WebSocket |
| Deployment | Direct Python | Docker Compose / K8s |
