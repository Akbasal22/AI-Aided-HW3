import chromadb
from langchain_core.documents import Document

import config
import embedder


def query_collection(
    collection: chromadb.Collection,
    query_embedding: list[float],
    top_k: int = config.TOP_K,
) -> list[dict]:
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        docs.append(
            {
                "text": text,
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "category": meta.get("category", ""),
                "article_id": meta.get("article_id", -1),
                "chunk_index": meta.get("chunk_index", -1),
                "distance": dist,
            }
        )

    docs.sort(key=lambda x: x["distance"])
    return docs


def _get_collection(name: str) -> chromadb.Collection:
    client = embedder.get_chroma_client()
    return client.get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def retrieve(
    query: str,
    category: str,
    top_k: int = config.TOP_K,
) -> list[dict]:
    query_vec = embedder.embed_query(query)

    if category == "person":
        col = _get_collection(config.PEOPLE_COLLECTION)
        if col.count() == 0:
            return []
        return query_collection(col, query_vec, top_k)

    if category == "place":
        col = _get_collection(config.PLACES_COLLECTION)
        if col.count() == 0:
            return []
        return query_collection(col, query_vec, top_k)

    # "both" — query each store, merge, re-rank, take top_k
    people_col = _get_collection(config.PEOPLE_COLLECTION)
    places_col = _get_collection(config.PLACES_COLLECTION)
    results = []
    if people_col.count() > 0:
        results += query_collection(people_col, query_vec, top_k)
    if places_col.count() > 0:
        results += query_collection(places_col, query_vec, top_k)
    results.sort(key=lambda x: x["distance"])
    return results[:top_k]


def results_to_langchain_docs(results: list[dict]) -> list[Document]:
    return [
        Document(
            page_content=r["text"],
            metadata={
                "title": r["title"],
                "url": r["url"],
                "category": r["category"],
                "article_id": r["article_id"],
                "chunk_index": r["chunk_index"],
                "distance": r["distance"],
            },
        )
        for r in results
    ]
