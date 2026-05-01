import sqlite3

import requests

import config
import db

_people_names: set[str] = set()
_places_names: set[str] = set()

FEW_SHOT_PROMPT = """\
Classify the question below. Reply with exactly one word: person, place, both, or irrelevant.

Q: What did Marie Curie discover?            A: person
Q: Where is the Eiffel Tower located?        A: place
Q: Who built the Hagia Sophia and when?      A: place
Q: Compare Messi and Ronaldo                 A: both
Q: Tell me about Einstein and the Taj Mahal  A: both
Q: Who is the president of Mars?             A: irrelevant
Q: What is 2 + 2?                            A: irrelevant

Q: {query}
A:"""


def build_keyword_lists(conn: sqlite3.Connection) -> None:
    global _people_names, _places_names
    _people_names = {n.lower() for n in db.get_entity_names(conn, "person")}
    _places_names = {n.lower() for n in db.get_entity_names(conn, "place")}


def keyword_prefilter(query: str) -> str | None:
    q = query.lower()
    matched_person = any(name in q for name in _people_names)
    matched_place = any(name in q for name in _places_names)

    if matched_person and matched_place:
        return "both"
    if matched_person:
        return "person"
    if matched_place:
        return "place"
    return None


def ollama_classify(query: str) -> str:
    prompt = FEW_SHOT_PROMPT.format(query=query)
    try:
        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={"model": config.CLASSIFIER_LLM, "prompt": prompt, "stream": False},
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip().lower()
        first_word = raw.split()[0].strip(".,!?") if raw else ""
        if first_word in ("person", "place", "both"):
            return first_word
        if first_word == "irrelevant":
            return "both"
        return "both"
    except Exception:
        return "both"


def classify_query(query: str) -> str:
    fast = keyword_prefilter(query)
    if fast is not None:
        return fast
    return ollama_classify(query)
