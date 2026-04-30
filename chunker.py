import config


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE_WORDS,
    overlap: int = config.CHUNK_OVERLAP_WORDS,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    step = chunk_size - overlap
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i: i + chunk_size]
        if len(chunk_words) < overlap and chunks:
            break
        chunks.append(" ".join(chunk_words))
        i += step

    return chunks


def chunk_article(
    article: dict,
    chunk_size: int = config.CHUNK_SIZE_WORDS,
    overlap: int = config.CHUNK_OVERLAP_WORDS,
) -> list[dict]:
    texts = chunk_text(article["cleaned_text"], chunk_size, overlap)
    result = []
    for idx, text in enumerate(texts):
        result.append(
            {
                "article_id": article["id"],
                "chunk_index": idx,
                "text": text,
                "word_count": len(text.split()),
            }
        )
    return result
