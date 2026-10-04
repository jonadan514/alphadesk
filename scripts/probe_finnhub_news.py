"""Finnhub 기업 뉴스 API로 미국 테마 뉴스 건수를 만들 수 있는지 실측한다(진단용, DB는 읽기만).

구글 뉴스 RSS(2026-09-28 Actions IP 차단)와 GDELT(요율·공백, 2026-10-04 실측)가 안 돼서 미국 뉴스 축을
"테마 소속 기업들의 기업 뉴스 건수 합"으로 바꾸는 안(사용자 결정 A)을 검토한다.
확인할 것: (1) 키·응답 (2) 종목·주별 건수 크기와 응답 상한에 눌리는지 (3) 무료 등급 요율(분당 60회)로
미국 소속 전체를 시간 안에 도는지 (4) 여러 종목에 같은 기사가 걸리는 중복 비율.

    FINNHUB_API_KEY=... python scripts/probe_finnhub_news.py --themes nuclear_smr power_grid defense --weeks 8
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENDPOINT = "https://finnhub.io/api/v1/company-news"
SLEEP_SEC = 1.1   # 무료 등급 분당 60회


def fetch(symbol: str, start: date, end: date, token: str) -> tuple[list[dict], str]:
    r = requests.get(ENDPOINT, params={"symbol": symbol, "from": start.isoformat(),
                                       "to": (end - timedelta(days=1)).isoformat(), "token": token}, timeout=30)
    status = f"HTTP {r.status_code}"
    if r.status_code != 200:
        return [], status + " " + r.text[:120]
    data = r.json()
    return (data if isinstance(data, list) else []), status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--themes", nargs="*", default=["nuclear_smr", "power_grid", "defense"])
    ap.add_argument("--weeks", type=int, default=8)
    args = ap.parse_args()
    token = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not token:
        print("FINNHUB_API_KEY 없음 - GitHub Secrets에 넣어야 한다")
        return 1

    from src.db.data_store import get_db
    from src.db.theme_signals import get_approved_theme_members
    conn = get_db()

    today = date.today()
    end = today - timedelta(days=today.weekday())
    start = end - timedelta(weeks=args.weeks)
    t0 = time.time(); calls = 0; fails = 0; max_len = 0
    for tid in args.themes:
        members = [m["ticker"] for m in get_approved_theme_members(conn, tid, "US")]
        weeks: Counter = Counter(); ids: Counter = Counter(); per_sym = {}
        for sym in members:
            items, status = fetch(sym, start, end, token)
            calls += 1; fails += 0 if status == "HTTP 200" else 1
            max_len = max(max_len, len(items))
            per_sym[sym] = len(items) if status == "HTTP 200" else status
            for it in items:
                d = datetime.fromtimestamp(it.get("datetime", 0), tz=timezone.utc).date()
                if start <= d < end:
                    weeks[(d - timedelta(days=d.weekday())).isoformat()] += 1
                    ids[it.get("id") or it.get("url")] += 1
            time.sleep(SLEEP_SEC)
        dup = sum(c - 1 for c in ids.values() if c > 1)
        print(f"== {tid}: 소속 {len(members)}종목, 종목별 건수 {per_sym}")
        print(f"   주별(중복 포함) {dict(sorted(weeks.items()))}")
        print(f"   기사 {sum(ids.values())}건 중 여러 종목에 겹친 것 {dup}건")
    el = time.time() - t0
    print(f"호출 {calls}회, 실패 {fails}회, {el:.0f}초, 한 응답 최대 {max_len}건(상한에 눌리는지 확인)")
    return 0 if fails < calls else 1


if __name__ == "__main__":
    sys.exit(main())
