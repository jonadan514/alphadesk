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


def _or_query(keywords: list[str]) -> str:
    """테마 키워드를 OR로 묶어 한 번에 조회 - 요율 제한 때문에 호출 수를 줄인다."""
    terms = " OR ".join(f'"{k}"' for k in keywords)
    return f"({terms}) sourcelang:english sourcecountry:US" if len(keywords) > 1 else f"{terms} sourcelang:english sourcecountry:US"


def weekly_counts(keyword: str | list[str], start: date, end: date, mode: str = "timelinevolraw",
                  retries: int = 4) -> tuple[dict[str, float], str]:
    q = _or_query(keyword if isinstance(keyword, list) else [keyword])
    url = (f"{ENDPOINT}?query={quote(q)}&mode={mode}&format=json"
           f"&startdatetime={start:%Y%m%d}000000&enddatetime={end:%Y%m%d}000000")
    for attempt in range(retries + 1):
        r = requests.get(url, timeout=60)
        if r.status_code != 429:
            break
        time.sleep(15 * (attempt + 1))   # 공유 IP라 429가 잦다 - 점점 길게 기다린다
    status = f"HTTP {r.status_code}, {len(r.content)}B, 시도 {attempt + 1}"
    if r.status_code != 200:
        return {}, status + " " + r.text[:120].replace("\n", " ")
    try:
        data = r.json()
    except ValueError:
        return {}, status + " non-JSON: " + r.text[:200].replace("\n", " ")
    weeks: dict[str, int] = {}
    for series in data.get("timeline", []):
        for pt in series.get("data", []):
            d = date(int(pt["date"][:4]), int(pt["date"][4:6]), int(pt["date"][6:8]))
            monday = d - timedelta(days=d.weekday())
            weeks[monday.isoformat()] = round(weeks.get(monday.isoformat(), 0) + float(pt.get("value", 0)), 4)
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
    # 테마당 키워드 OR 묶음 1회씩, 원건수(raw)와 전체 대비 비중(vol) 두 가지.
    # 비중은 GDELT 자체 수집이 빠진 주(2026-09-14 첫 실측에서 전 키워드 급감)에 덜 흔들리는지 보려는 것.
    for tid in args.themes:
        kws = themes[tid].get("keywords_en", [])
        for mode in ("timelinevolraw", "timelinevol"):
            w, status = weekly_counts(kws, start, end, mode)
            calls += 1; fails += 0 if w else 1
            print(f"[{tid}] {mode}: {status} {json.dumps(w, ensure_ascii=False)}")
            time.sleep(SLEEP_SEC)
    el = time.time() - t0
    print(f"호출 {calls}회, 실패 {fails}회, {el:.0f}초 (호출당 {el / max(calls, 1):.1f}초)")
    return 0 if fails < calls else 1


if __name__ == "__main__":
    sys.exit(main())
