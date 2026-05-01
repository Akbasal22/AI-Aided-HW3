from langchain_core.documents import Document
from langchain_ollama import OllamaLLM

import config
from prompts import RAG_PROMPT

_llm: OllamaLLM | None = None

MAX_CONTEXT_WORDS = 1500


def load_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM(
            model=config.LLM_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            temperature=0.1,
        )
    return _llm


def format_context(docs: list[Document]) -> str:
    parts = []
    total_words = 0
    for doc in docs:
        words = doc.page_content.split()
        if total_words + len(words) > MAX_CONTEXT_WORDS:
            remaining = MAX_CONTEXT_WORDS - total_words
            if remaining > 50:
                parts.append(" ".join(words[:remaining]))
            break
        parts.append(doc.page_content)
        total_words += len(words)
    return "\n\n---\n\n".join(parts)


def answer(query: str, docs: list[Document]) -> str:

    if not docs:
        return "I don't have enough information to answer that based on the available data."

    context_str = format_context(docs)
    prompt_str = RAG_PROMPT.format(context=context_str, question=query)

    try:
        llm = load_llm()
        response = llm.invoke(prompt_str)
        return str(response).strip()
    except Exception as exc:
        if "connection" in str(exc).lower() or "refused" in str(exc).lower():
            raise ConnectionError(
                f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}. "
                "Make sure Ollama is running: `ollama serve`"
            ) from exc
        raise
