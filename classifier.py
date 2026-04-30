import sqlite3

import config
import db

_classifier_pipeline = None
_people_names: set[str] = set()
_places_names: set[str] = set()


def load_classifier():
    global _classifier_pipeline
    if _classifier_pipeline is None:
        from transformers import pipeline
        _classifier_pipeline = pipeline(
            "zero-shot-classification",
            model=config.CLASSIFIER_MODEL,
        )
    return _classifier_pipeline


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


def bert_classify(query: str) -> str:
    clf = load_classifier()
    result = clf(query, candidate_labels=config.CLASSIFIER_LABELS)

    scores = dict(zip(result["labels"], result["scores"]))
    person_score = scores.get("person", 0.0)
    place_score = scores.get("place", 0.0)

    # If the two labels are close, treat as ambiguous → "both"
    if abs(person_score - place_score) < config.CLASSIFIER_MARGIN:
        return "both"
    return result["labels"][0]


def classify_query(query: str) -> str:
    fast = keyword_prefilter(query)
    if fast is not None:
        return fast
    return bert_classify(query)
