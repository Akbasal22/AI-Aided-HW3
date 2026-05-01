import re
import sqlite3
import time

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

import config
import db

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "WikiRAG/1.0 (BLG483E HW3; educational use)"}


def fetch_wikipedia_page(title: str) -> tuple[str, str]:
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "redirects": True,
    }
    resp = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Wikipedia page not found: {title!r} — {data['error']['info']}")
    page_key = data["parse"]["title"].replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{page_key}"
    raw_html = data["parse"]["text"]["*"]
    return url, raw_html


def clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup.find_all(["script", "style", "table", "sup", "figure", "ul", "ol"]):
        tag.decompose()

    for span in soup.find_all("span", class_=re.compile(r"mw-editsection|reference")):
        span.decompose()

    paragraphs = soup.find_all("p")
    text = "\n\n".join(p.get_text() for p in paragraphs)

    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[note \d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def ingest_entity(
    conn: sqlite3.Connection,
    title: str,
    category: str,
    force: bool = False,
) -> tuple[int, bool]:
    """
    Returns (article_id, was_fetched). was_fetched=False when the article
    already existed and force=False (idempotent skip).
    """
    if not force:
        existing_id = db.article_exists(conn, title, category)
        if existing_id is not None:
            return existing_id, False

    url, raw_html = fetch_wikipedia_page(title)
    cleaned = clean_html(raw_html)
    article_id = db.insert_article(conn, title, url, category, raw_html, cleaned)
    return article_id, True


def ingest_bulk(
    conn: sqlite3.Connection,
    titles: list[str],
    category: str,
    force: bool = False,
) -> list[int]:
    ids = []
    skipped = 0
    fetched = 0
    for title in tqdm(titles, desc=f"Ingesting {category}s", unit="article"):
        try:
            aid, was_fetched = ingest_entity(conn, title, category, force=force)
            ids.append(aid)
            if was_fetched:
                fetched += 1
                time.sleep(2)
            else:
                skipped += 1
        except Exception as exc:
            print(f"  [WARN] Failed to ingest {title!r}: {exc}")
    print(f"  {category}s: {fetched} fetched, {skipped} skipped (already in DB)")
    return ids


def ingest_from_config_lists(
    conn: sqlite3.Connection, force: bool = False
) -> None:
    ingest_bulk(conn, config.PEOPLE_TITLES, "person", force=force)
    ingest_bulk(conn, config.PLACES_TITLES, "place", force=force)


if __name__ == "__main__":
    conn = db.get_connection()
    db.init_db(conn)
    ingest_from_config_lists(conn)
    conn.close()
    print("Ingestion complete.")
