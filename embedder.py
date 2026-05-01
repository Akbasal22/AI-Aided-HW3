from __future__ import annotations

import sqlite3

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

import config
import db
from chunker import chunk_article

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


def load_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = load_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    return _chroma_client


def get_or_create_collection(
    client: chromadb.PersistentClient, name: str
) -> chromadb.Collection:
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def embed_and_store_article(
    conn: sqlite3.Connection,
    article: dict,
    collection: chromadb.Collection,
) -> None:
    chunks = chunk_article(article)
    if not chunks:
        return

    for chunk in chunks:
        db.insert_chunk(
            conn,
            chunk["article_id"],
            chunk["chunk_index"],
            chunk["text"],
            chunk["word_count"],
        )

    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)

    ids = [f"{article['id']}_{c['chunk_index']}" for c in chunks]
    metadatas = [
        {
            "article_id": article["id"],
            "chunk_index": c["chunk_index"],
            "title": article["title"],
            "category": article["category"],
            "url": article["url"],
        }
        for c in chunks
    ]

    collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
    db.mark_article_embedded(conn, article["id"])


def run_embedding_pipeline(conn: sqlite3.Connection) -> None:
    client = get_chroma_client()

    for category, collection_name in [
        ("person", config.PEOPLE_COLLECTION),
        ("place", config.PLACES_COLLECTION),
    ]:
        collection = get_or_create_collection(client, collection_name)
        articles = db.get_unembedded_articles(conn, category)
        if not articles:
            print(f"No unembedded {category} articles found.")
            continue
        for article in tqdm(articles, desc=f"Embedding {category}s", unit="article"):
            embed_and_store_article(conn, article, collection)


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
