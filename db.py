import sqlite3
import config


def get_connection(db_path: str = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            url          TEXT    NOT NULL,
            category     TEXT    NOT NULL CHECK(category IN ('person','place')),
            raw_html     TEXT    NOT NULL,
            cleaned_text TEXT    NOT NULL,
            is_embedded  INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(title, category)
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text        TEXT    NOT NULL,
            word_count  INTEGER NOT NULL,
            UNIQUE(article_id, chunk_index)
        );

        CREATE INDEX IF NOT EXISTS idx_articles_category    ON articles(category);
        CREATE INDEX IF NOT EXISTS idx_articles_is_embedded ON articles(is_embedded);
        CREATE INDEX IF NOT EXISTS idx_chunks_article_id    ON chunks(article_id);
    """)
    conn.commit()


def insert_article(
    conn: sqlite3.Connection,
    title: str,
    url: str,
    category: str,
    raw_html: str,
    cleaned_text: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO articles (title, url, category, raw_html, cleaned_text)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(title, category) DO UPDATE SET
            url          = excluded.url,
            raw_html     = excluded.raw_html,
            cleaned_text = excluded.cleaned_text,
            is_embedded  = 0,
            created_at   = datetime('now')
        """,
        (title, url, category, raw_html, cleaned_text),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM articles WHERE title=? AND category=?", (title, category)
    ).fetchone()
    return row["id"]


def get_article_by_id(conn: sqlite3.Connection, article_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM articles WHERE id=?", (article_id,)
    ).fetchone()
    return dict(row) if row else None


def article_exists(conn: sqlite3.Connection, title: str, category: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM articles WHERE title=? AND category=?", (title, category)
    ).fetchone()
    return row["id"] if row else None


def get_all_articles(
    conn: sqlite3.Connection, category: str | None = None
) -> list[dict]:
    if category:
        rows = conn.execute(
            "SELECT * FROM articles WHERE category=?", (category,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM articles").fetchall()
    return [dict(r) for r in rows]


def get_unembedded_articles(
    conn: sqlite3.Connection, category: str | None = None
) -> list[dict]:
    if category:
        rows = conn.execute(
            "SELECT * FROM articles WHERE is_embedded=0 AND category=?", (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles WHERE is_embedded=0"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_article_embedded(conn: sqlite3.Connection, article_id: int) -> None:
    conn.execute(
        "UPDATE articles SET is_embedded=1 WHERE id=?", (article_id,)
    )
    conn.commit()


def get_entity_names(conn: sqlite3.Connection, category: str) -> list[str]:
    rows = conn.execute(
        "SELECT title FROM articles WHERE category=?", (category,)
    ).fetchall()
    return [r["title"] for r in rows]


def insert_chunk(
    conn: sqlite3.Connection,
    article_id: int,
    chunk_index: int,
    text: str,
    word_count: int,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO chunks (article_id, chunk_index, text, word_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(article_id, chunk_index) DO UPDATE SET
            text       = excluded.text,
            word_count = excluded.word_count
        """,
        (article_id, chunk_index, text, word_count),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM chunks WHERE article_id=? AND chunk_index=?",
        (article_id, chunk_index),
    ).fetchone()
    return row["id"]


def get_chunks_for_article(
    conn: sqlite3.Connection, article_id: int
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM chunks WHERE article_id=? ORDER BY chunk_index",
        (article_id,),
    ).fetchall()
    return [dict(r) for r in rows]
