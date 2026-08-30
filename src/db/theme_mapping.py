"""Phase A-2: 테마→기업 매핑 스키마 + 쓰기 함수.

SPEC: docs/radar/SPEC_theme_company_mapping.md §5
"""
from __future__ import annotations

import json

THEME_MEMBERS_DDL = """
CREATE TABLE IF NOT EXISTS theme_members (
  theme_id     TEXT NOT NULL,
  ticker       TEXT NOT NULL,
  market       TEXT NOT NULL,
  stage        TEXT,
  evidence     TEXT,
  linkage      TEXT,
  confidence   TEXT,
  flagged      INTEGER DEFAULT 0,
  approved     INTEGER DEFAULT 0,
  run_id       TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (theme_id, ticker, run_id)
)
"""

MAPPING_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS mapping_runs (
  run_id       TEXT PRIMARY KEY,
  started_at   TEXT,
  finished_at  TEXT,
  model        TEXT,
  prompt_ver   TEXT,
  stats        TEXT
)
"""


def ensure_schema(conn) -> None:
    conn.execute(THEME_MEMBERS_DDL)
    conn.execute(MAPPING_RUNS_DDL)
    conn.commit()


def start_mapping_run(conn, run_id: str, started_at: str, model: str, prompt_ver: str) -> None:
    conn.execute(
        """
        INSERT INTO mapping_runs (run_id, started_at, model, prompt_ver)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(run_id) DO NOTHING
        """,
        (run_id, started_at, model, prompt_ver),
    )
    conn.commit()


def finish_mapping_run(conn, run_id: str, finished_at: str, stats: dict) -> None:
    conn.execute(
        """
        UPDATE mapping_runs SET finished_at = ?, stats = ? WHERE run_id = ?
        """,
        (finished_at, json.dumps(stats, ensure_ascii=False), run_id),
    )
    conn.commit()


def insert_theme_member(conn, theme_id: str, ticker: str, market: str, stage: str | None,
                         evidence: str | None, linkage: str | None, confidence: str,
                         flagged: bool, run_id: str, created_at: str) -> None:
    """같은 (theme_id, ticker, run_id) 조합은 조용히 무시 — 경로 A/B에서 중복으로
    나온 후보를 병합할 때 나중 것이 먼저 것을 지우지 않게 한다(호출부가 먼저
    confidence=high로 병합해서 넘기므로 순서 문제 없음)."""
    conn.execute(
        """
        INSERT OR IGNORE INTO theme_members
          (theme_id, ticker, market, stage, evidence, linkage, confidence, flagged, approved, run_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (theme_id, ticker, market, stage, evidence, linkage, confidence,
         1 if flagged else 0, run_id, created_at),
    )
