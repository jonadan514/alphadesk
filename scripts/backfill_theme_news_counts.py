"""테마별 주간 기사 수를 과거로 채운다 (분기 재설계 docs/REDESIGN_SPEC.md 6장).

분기 뉴스 비율(이번 분기 ÷ 직전 4분기 평균)을 계산하려면 최소 5분기치 이력이 필요한데,
2026-09-17 점검에서 theme_news에는 10주치(2026-07-13부터)만 있었다. 그래서 과거 주를
Google News RSS 날짜 조회로 다시 센다.

설계
  - 기사 원문은 저장하지 않고 **건수만** theme_news_weekly에 남긴다. 분기 비교에 필요한 건
    건수뿐이고, 62주치 원문은 100만 건이 넘는다.
  - 중복 제거(URL·제목 유사도 90%)는 수집하는 순간 한 주 안에서 한다 - 기존 주간 수집과 같다.
  - 키워드 하나가 100건 상한에 닿으면 그 키워드만 하루 단위로 다시 센다(collect_theme_news).
    하루로도 상한인 키워드 수를 saturated_keywords로 남긴다 - 그 주 건수는 실제보다 작다.
  - 조회가 실패한 키워드는 0건과 구별해 failed_keywords로 남긴다.
  - **현재 키워드**로 과거를 센다. 그래서 백필 구간 안에서는 키워드가 일관된다.
  - 이미 센 (테마, 주)는 건너뛴다 - 중간에 끊겨도 다시 돌리면 이어서 한다.

Usage:
  python scripts/backfill_theme_news_counts.py --market KR --start 2025-07-07 --end 2025-12-29
  python scripts/backfill_theme_news_counts.py --market US --start 2026-07-06 --end 2026-09-07 --force
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db
from src.db.theme_signals import ensure_schema, get_collected_news_weeks, upsert_news_weekly
import collectors.theme_news_collector as news

THEMES_YAML = ROOT / "config" / "themes.yaml"
KEYWORD_FIELD = {"US": "keywords_en", "KR": "keywords_ko"}


def _log(msg: str) -> None:
    print(f"[news-backfill] {msg}", flush=True)


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", required=True, choices=["US", "KR"])
    ap.add_argument("--start", required=True, help="첫 주 (그 주 월요일로 맞춘다)")
    ap.add_argument("--end", default=None, help="마지막 주 (비우면 지난주 - 이번 주는 아직 안 끝났다)")
    ap.add_argument("--theme-id", nargs="*", default=None)
    ap.add_argument("--force", action="store_true", help="이미 센 주도 다시 센다")
    ap.add_argument("--sleep", type=float, default=None, help="키워드 요청 사이 대기(초). 기본은 수집기 값")
    args = ap.parse_args()

    if args.sleep is not None:
        news.KEYWORD_SLEEP_SEC = args.sleep

    start = monday(date.fromisoformat(args.start))
    end = monday(date.fromisoformat(args.end)) if args.end else monday(date.today()) - timedelta(days=7)
    weeks = []
    w = start
    while w <= end:
        weeks.append(w)
        w += timedelta(days=7)

    data = yaml.safe_load(THEMES_YAML.read_text(encoding="utf-8"))
    themes = [t for t in data["themes"]
              if t.get("status") == "active" and args.market in t.get("markets", [])
              and t.get(KEYWORD_FIELD[args.market])]
    if args.theme_id:
        themes = [t for t in themes if t["id"] in set(args.theme_id)]

    conn = get_db()
    ensure_schema(conn)
    done = set() if args.force else get_collected_news_weeks(conn, args.market)

    todo = [(wk, t) for wk in weeks for t in themes if (t["id"], wk.isoformat()) not in done]
    _log(f"{args.market}: {len(weeks)}주({weeks[0]} ~ {weeks[-1]}) x 테마 {len(themes)}개 "
         f"= {len(weeks) * len(themes)}건, 이미 센 것 제외 {len(todo)}건")

    t0 = time.time()
    totals = {"saturated": 0, "failed": 0, "expanded": 0}
    for i, (wk, theme) in enumerate(todo, 1):
        keywords = theme[KEYWORD_FIELD[args.market]]
        articles, stats = news.collect_theme_news(keywords, wk, wk + timedelta(days=7), market=args.market)
        sat, exp, fail = (len(stats["saturated_keywords"]), len(stats["expanded_keywords"]),
                          len(stats["failed_keywords"]))
        totals["saturated"] += sat > 0
        totals["expanded"] += exp > 0
        totals["failed"] += fail > 0
        upsert_news_weekly(conn, theme["id"], args.market, wk.isoformat(), len(articles),
                           stats["raw_total"], sat, exp, fail, datetime.utcnow().isoformat())
        conn.commit()

        flags = []
        if exp:
            flags.append(f"하루단위 {exp}")
        if sat:
            flags.append(f"포화 {sat}")
        if fail:
            flags.append(f"실패 {fail} {stats['failed_keywords'][:2]}")
        if i % 35 == 0 or flags:
            elapsed = time.time() - t0
            eta = elapsed / i * (len(todo) - i)
            _log(f"[{i}/{len(todo)}] {wk} {theme['id']}: {len(articles)}건"
                 f"{' (' + ', '.join(flags) + ')' if flags else ''} - 경과 {elapsed/60:.0f}분, 남은 약 {eta/60:.0f}분")

    conn.close()
    _log(f"완료 {len(todo)}건 / {(time.time() - t0)/60:.0f}분 - 하루단위로 다시 센 테마-주 {totals['expanded']}, "
         f"포화 남음 {totals['saturated']}, 조회 실패 포함 {totals['failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
