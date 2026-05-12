import json
import os
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = os.getenv("DATA_DB_PATH", "output/data.db")

# --------------------------------------------------------------------------
# DDL
# --------------------------------------------------------------------------

_TIMESERIES_TABLES = {
    "data_daily_reports": """
        CREATE TABLE IF NOT EXISTS data_daily_reports (
            date        TEXT PRIMARY KEY,
            payload     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_risk_alerts": """
        CREATE TABLE IF NOT EXISTS data_risk_alerts (
            date        TEXT PRIMARY KEY,
            payload     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_prediction_history": """
        CREATE TABLE IF NOT EXISTS data_prediction_history (
            date        TEXT PRIMARY KEY,
            payload     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
}

_SNAPSHOT_TABLES = {
    "data_regime": """
        CREATE TABLE IF NOT EXISTS data_regime (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_market_gate": """
        CREATE TABLE IF NOT EXISTS data_market_gate (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_ai_summaries": """
        CREATE TABLE IF NOT EXISTS data_ai_summaries (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_gbm_predictions": """
        CREATE TABLE IF NOT EXISTS data_gbm_predictions (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_index_prediction": """
        CREATE TABLE IF NOT EXISTS data_index_prediction (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_risk": """
        CREATE TABLE IF NOT EXISTS data_risk (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_performance": """
        CREATE TABLE IF NOT EXISTS data_performance (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_costs": """
        CREATE TABLE IF NOT EXISTS data_costs (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            payload     TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
}

# --------------------------------------------------------------------------
# Connection
# --------------------------------------------------------------------------

def get_db(path: str = DB_PATH) -> sqlite3.Connection:
    turso_url   = os.getenv("TURSO_DATA_URL")
    turso_token = os.getenv("TURSO_DATA_TOKEN")
    if turso_url and turso_token:
        try:
            import libsql_experimental as libsql  # type: ignore
            return libsql.connect(turso_url, auth_token=turso_token)
        except ImportError:
            print("[data_store] libsql_experimental 없음 — 로컬 SQLite 사용")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    for ddl in {**_TIMESERIES_TABLES, **_SNAPSHOT_TABLES}.values():
        conn.execute(ddl)
    conn.commit()

# --------------------------------------------------------------------------
# Writes  (Python-side only; frontend reads via SELECT)
# --------------------------------------------------------------------------

def upsert_daily_report(conn: sqlite3.Connection, date: str, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    conn.execute(
        """
        INSERT INTO data_daily_reports (date, payload)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET
            payload    = excluded.payload,
            created_at = datetime('now')
        """,
        (date, payload),
    )
    conn.commit()


def _upsert_snapshot(conn: sqlite3.Connection, table: str, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    conn.execute(
        f"""
        INSERT INTO {table} (id, payload)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            payload    = excluded.payload,
            updated_at = datetime('now')
        """,
        (payload,),
    )
    conn.commit()


def upsert_regime(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_regime", data)


def upsert_market_gate(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_market_gate", data)


def upsert_ai_summaries(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_ai_summaries", data)


def upsert_gbm_predictions(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_gbm_predictions", data)


def upsert_index_prediction(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_index_prediction", data)
    today = date.today().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO data_prediction_history (date, payload)
        VALUES (?, ?)
    """, (today, json.dumps(data, ensure_ascii=False)))


def upsert_kr_index_prediction(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "kr_index_prediction", data)


def upsert_risk(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_risk", data)


def upsert_performance(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_performance", data)


def upsert_costs(conn: sqlite3.Connection, data: dict) -> None:
    _upsert_snapshot(conn, "data_costs", data)


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_latest_report(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT payload FROM data_daily_reports ORDER BY date DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return {}
    payload = row[0] if not hasattr(row, "keys") else row["payload"]
    return json.loads(payload)


def get_snapshot(conn: sqlite3.Connection, table: str) -> dict:
    row = conn.execute(f"SELECT payload FROM {table} WHERE id = 1").fetchone()
    if row is None:
        return {}
    payload = row[0] if not hasattr(row, "keys") else row["payload"]
    return json.loads(payload)
