"""GDELT DOC API로 미국 테마 뉴스 건수를 받을 수 있는지 실측한다(진단용).

2026-09-28부터 구글 뉴스 RSS가 Actions IP를 막아 미국 뉴스가 0건이다. GDELT는 키가 없는
공개 API이고, timelinevolraw 모드가 날짜별 '기사 수'를 직접 준다 - 기사 목록을 넘겨 세는
방식이 아니라서 네이버·구글처럼 100건/1000건 상한에 눌리지 않는다.
확인할 것: (1) Actions에서 응답하는가 (2) 주간 건수가 키워드별로 의미 있는 크기인가
(3) 요율 제한(공식 권고 5초에 1회)에서 테마 32개 x 키워드 5개를 시간 안에 돌 수 있는가.

    python scripts/probe_gdelt_news.py --themes ai_semiconductor nuclear_smr power_grid --weeks 8
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
SLEEP_SEC = 5.5


def weekly_counts(keyword: str, start: date, end: date) -> tuple[dict[str, int], str]:
    q = f'"{keyword}" sourcelang:english sourcecountry:US'
    url = (f"{ENDPOINT}?query={quote(q)}&mode=timelinevolraw&format=json"
           f"&startdatetime={start:%Y%m%d}000000&enddatetime={end:%Y%m%d}000000")
    r = requests.get(url, timeout=60)
    status = f"HTTP {r.status_code}, {len(r.content)}B"
    if r.status_code != 200:
        return {}, status + " " + r.text[:200].replace("\n", " ")
    try:
        data = r.json()
    except ValueError:
        return {}, status + " non-JSON: " + r.text[:200].replace("\n", " ")
    weeks: dict[str, int] = {}
    for series in data.get("timeline", []):
        for pt in series.get("data", []):
            d = date(int(pt["date"][:4]), int(pt["date"][4:6]), int(pt["date"][6:8]))
            monday = d - timedelta(days=d.weekday())
            weeks[monday.isoformat()] = weeks.get(monday.isoformat(), 0) + int(pt.get("value", 0))
    return weeks, status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--themes", nargs="*", default=["ai_semiconductor", "nuclear_smr", "power_grid"])
    ap.add_argument("--weeks", type=int, default=8)
    args = ap.parse_args()
    themes = {t["id"]: t for t in yaml.safe_load(open(ROOT / "config" / "themes.yaml"))["themes"]}
    today = date.today()
    end = today - timedelta(days=today.weekday())          # 이번 주 월요일(배타)
    start = end - timedelta(weeks=args.weeks)
    t0 = time.time(); calls = 0; fails = 0
    for tid in args.themes:
        print(f"== {tid}")
        for kw in themes[tid].get("keywords_en", []):
            w, status = weekly_counts(kw, start, end)
            calls += 1; fails += 0 if w else 1
            print(f"  {kw!r}: {status} {json.dumps(w, ensure_ascii=False)}")
            time.sleep(SLEEP_SEC)
    el = time.time() - t0
    print(f"호출 {calls}회, 실패 {fails}회, {el:.0f}초 (호출당 {el / max(calls, 1):.1f}초)")
    return 0 if fails < calls else 1


if __name__ == "__main__":
    sys.exit(main())
