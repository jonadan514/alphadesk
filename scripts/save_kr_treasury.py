"""fetch_kr_treasury_pykrx.py가 만든 JSON을 kr_rates 표에 저장한다 (2026-10-05).

kr_rates(date, key, value): key는 kr3y / kr10y, value는 %. 같은 날·같은 만기는 최신 값으로 덮는다
(장 마감 뒤 최종호가가 확정되기 전 값을 고치는 것 - 지난 날짜의 확정값은 다시 와도 같은 값).

    python scripts/save_kr_treasury.py --in data/kr_treasury.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

KR_RATES_DDL = """
CREATE TABLE IF NOT EXISTS kr_rates (
  date   TEXT NOT NULL,
  key    TEXT NOT NULL,
  value  REAL,
  PRIMARY KEY (date, key)
)
"""


def save(conn, items: dict[str, list[dict]]) -> int:
    conn.execute(KR_RATES_DDL)
    # 수집 쪽에서 휴장일 반복 값을 뺀 날짜 범위 안에 이미 저장된 반복 행(2026-10-05 첫 실행분)을 지운다 -
    # 이번에 받은 날짜 범위 안에서 이번 결과에 없는 날짜만. 범위 밖 과거 기록은 건드리지 않는다.
    dates = sorted({r["date"] for v in items.values() for r in v})
    if dates:
        keep = ", ".join("?" * len(dates))
        conn.execute(f"DELETE FROM kr_rates WHERE date BETWEEN ? AND ? AND date NOT IN ({keep})",
                     (dates[0], dates[-1], *dates))
    # KRX가 float32 꼴(3.937000036...)로 줘서 소수 셋째 자리로 맞춘다(호가 단위가 0.001%p)
    rows = [(r["date"], key, round(float(r["value"]), 3)) for key, vals in items.items() for r in vals if r.get("value") is not None]
    for i in range(0, len(rows), 100):
        chunk = rows[i:i + 100]
        conn.execute("INSERT OR REPLACE INTO kr_rates (date, key, value) VALUES " + ", ".join(["(?, ?, ?)"] * len(chunk)),
                     tuple(v for r in chunk for v in r))
    conn.commit()
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path", default="data/kr_treasury.json")
    args = ap.parse_args()
    p = Path(args.path)
    if not p.exists():
        print(f"[kr-treasury] {p} 없음 - 수집 단계가 실패했다. 저장 건너뜀", flush=True)
        return 0
    n = save(get_db(), json.loads(p.read_text(encoding="utf-8"))["items"])
    print(f"[kr-treasury] {n}행 저장", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
