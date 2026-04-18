"""
SQLite-based prediction logger.
"""

import sqlite3

DB_PATH = "database/fraud.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id   TEXT,
    amount           REAL,
    timestamp        TEXT,
    rule_flag        INTEGER,
    model_prediction INTEGER,
    risk_score       REAL,
    decision         TEXT,
    reasons          TEXT,
    analyst_status   TEXT,
    analyst_notes    TEXT,
    reviewed_at      TEXT
)
"""

OPTIONAL_COLUMNS = ["analyst_status", "analyst_notes", "reviewed_at"]


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()

    cur = conn.execute("PRAGMA table_info(predictions)")
    existing = {row[1] for row in cur.fetchall()}

    for col in OPTIONAL_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} TEXT")
    conn.commit()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    return conn


def log_prediction(record: dict) -> None:
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO predictions
            (transaction_id, amount, timestamp, rule_flag, model_prediction, risk_score, decision, reasons)
        VALUES
            (:transaction_id, :amount, :timestamp, :rule_flag, :model_prediction, :risk_score, :decision, :reasons)
        """,
        record,
    )
    conn.commit()
    conn.close()


def get_review_queue() -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute("""
        SELECT id, transaction_id, amount, timestamp, rule_flag,
               model_prediction, risk_score, decision, reasons,
               analyst_status, analyst_notes, reviewed_at
        FROM predictions
        WHERE decision IN ('REVIEW', 'BLOCK')
    """)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_prediction_by_id(prediction_id: int) -> dict | None:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_review(prediction_id: int, analyst_status: str, analyst_notes: str, reviewed_at: str) -> None:
    conn = _get_connection()
    conn.execute(
        """
        UPDATE predictions
        SET analyst_status = ?, analyst_notes = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (analyst_status, analyst_notes, reviewed_at, prediction_id),
    )
    conn.commit()
    conn.close()
