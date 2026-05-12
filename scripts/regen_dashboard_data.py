"""
DB → frontend/public/data/*.json 변환
Usage: python scripts/regen_dashboard_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db, init_db, get_latest_report, get_snapshot

OUT_DIR = ROOT / "frontend" / "public" / "data"

# (출력 파일명, DB 테이블 or 특수키)
SNAPSHOT_MAP = {
    "regime.json":           "data_regime",
    "market_gate.json":      "data_market_gate",
    "index_prediction.json": "data_index_prediction",
}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    print(f"  wrote  {path.relative_to(ROOT)}")


def main() -> None:
    print("=" * 50)
    print("  Dashboard JSON 재생성")
    print("=" * 50)

    conn = get_db()
    init_db(conn)

    # ── 스냅샷 테이블 → 개별 JSON ──────────────────────────────────
    for filename, table in SNAPSHOT_MAP.items():
        data = get_snapshot(conn, table)
        _write(OUT_DIR / filename, data)

    # ── 최신 일간 리포트 ───────────────────────────────────────────
    latest = get_latest_report(conn)
    _write(OUT_DIR / "latest_report.json", latest)

    # ── top_picks: latest_report의 picks 배열 ──────────────────────
    picks = latest.get("picks", [])
    _write(OUT_DIR / "top_picks.json", {"picks": picks})

    conn.close()
    print("=" * 50)
    print(f"  완료  →  {OUT_DIR.relative_to(ROOT)}/")
    print("=" * 50)


if __name__ == "__main__":
    main()
