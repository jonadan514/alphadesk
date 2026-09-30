"""분기 뉴스 비율을 테마별로 계산해 보고한다 (분기 재설계 docs/REDESIGN_SPEC.md 6-3).

**읽기 전용이다.** 아무것도 쓰지 않는다. 4칸 분류를 붙이기 전에 두 가지를 눈으로 보려고 만들었다.

1. **분기 이력이 실제로 다 채워졌는지.** 백필을 세 번 나눠 돌렸으므로 테마마다 빠진 주가
   없는지 확인해야 한다. 코드가 "데이터부족"이라고 말하는 이유를 그대로 보여준다.
2. **지금 기준값(config/quarterly.yaml)이 이 분포에서도 맞는지.** 기준값은 시장마다 다르다
   (2026-09-22 실측에서 한국과 미국의 분포가 크게 달랐다). 기준값 후보마다 몇 개 테마가
   걸리는지 함께 보여준다. 기준값을 코드에서 추측으로 바꾸지 않는다(원칙 3) - 이 분포를
   보고 사람이 config/quarterly.yaml에서 정한다.

Usage:
  python scripts/report_quarterly_news.py                    # 직전 분기
  python scripts/report_quarterly_news.py --quarter 2026Q3
  python scripts/report_quarterly_news.py --market KR
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.analyzers import quarterly_thresholds as qt
from src.analyzers.theme_news_quarterly import (MIN_WEEK_COVERAGE, aggregate_quarters, news_ratio,
                                                prior_quarters, quarter_of)
from src.db.data_store import get_db
from src.db.theme_signals import get_weekly_news_counts

THEMES_YAML = ROOT / "config" / "themes.yaml"
KEYWORD_FIELD = {"US": "keywords_en", "KR": "keywords_ko"}
HIGH_CANDIDATES = (1.2, 1.3, 1.5, 1.8, 2.0)   # 기준값 후보 - 각각 몇 개 테마가 걸리는지 센다


def _log(msg: str) -> None:
    print(msg, flush=True)


def parse_quarter(text: str) -> tuple[int, int]:
    y, q = text.upper().split("Q")
    return int(y), int(q)


def previous_quarter(today: date) -> tuple[int, int]:
    return prior_quarters(*quarter_of(today), n=1)[0]


def week_monday(day: date) -> date:
    from datetime import timedelta
    return day - timedelta(days=day.weekday())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarter", default=None, help="예: 2026Q3 (비우면 직전 분기)")
    ap.add_argument("--market", default=None, choices=["KR", "US"])
    args = ap.parse_args()

    target = parse_quarter(args.quarter) if args.quarter else previous_quarter(date.today())
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    themes = [t for t in data["themes"] if t.get("status") == "active"]

    conn = get_db()
    config = qt.load()
    markets = [args.market] if args.market else ["KR", "US"]
    _log(f"대상 분기 {target[0]}Q{target[1]} / 직전 4분기 "
         f"{', '.join(f'{y}Q{q}' for y, q in prior_quarters(*target))}")
    _log(f"분기 채택 기준: 그 분기 월요일 수의 {MIN_WEEK_COVERAGE:.0%} 이상 수집")
    _log("뉴스 '많음' 기준(config/quarterly.yaml): "
         + ", ".join(f"{m} {qt.news_high_threshold(m, config):.2f}배" for m in ["KR", "US"]) + "\n")

    all_ratios: list[float] = []
    for market in markets:
        rows = []
        for theme in themes:
            if market not in theme.get("markets", []) or not theme.get(KEYWORD_FIELD[market]):
                continue
            kw_changed = theme.get("keywords_changed_at")
            since = None
            if kw_changed:
                kc = kw_changed if isinstance(kw_changed, date) else date.fromisoformat(str(kw_changed))
                since = week_monday(kc).isoformat()

            weekly = get_weekly_news_counts(conn, theme["id"], market, since=since)
            quarters = aggregate_quarters(weekly)
            got = news_ratio(quarters, target)
            cur = quarters.get(target)
            rows.append({
                "id": theme["id"],
                "weeks": f"{cur['weeks']}/{cur['expected_weeks']}" if cur else "0/-",
                "articles": got["this_quarter"],
                "per_week": cur["per_week"] if cur else None,
                "baseline": got["baseline"],
                "ratio": got["ratio"],
                "reason": got["reason"],
                "kw_changed": bool(kw_changed),
            })

        ok = [r for r in rows if r["ratio"] is not None]
        all_ratios += [r["ratio"] for r in ok]
        high = [r for r in ok if qt.is_news_high(r["ratio"], market, config)]
        _log(f"=== {market} - 테마 {len(rows)}개 중 비율 계산 {len(ok)}개, "
             f"데이터부족 {len(rows) - len(ok)}개 ===")
        _log(f"기준 {qt.news_high_threshold(market, config):.2f}배 -> 뉴스 많음 {len(high)}개"
             f"{f' ({len(high) / len(ok):.0%})' if ok else ''}")
        _log(f"{'테마':<24}{'주':>7}{'기사':>8}{'주당':>8}{'기준선':>8}{'비율':>7}  비고")
        for r in sorted(rows, key=lambda x: (x["ratio"] is None, -(x["ratio"] or 0))):
            per_week = f"{r['per_week']:.1f}" if r["per_week"] is not None else "-"
            base = f"{r['baseline']:.1f}" if r["baseline"] is not None else "-"
            ratio = f"{r['ratio']:.2f}" if r["ratio"] is not None else "-"
            note = r["reason"] or ""
            if qt.is_news_high(r["ratio"], market, config):
                note = ("많음 " + note).strip()
            if r["kw_changed"]:
                note = (note + " / 키워드 변경 이력 있음").strip(" /")
            _log(f"{r['id']:<24}{r['weeks']:>7}{str(r['articles'] or '-'):>8}"
                 f"{per_week:>8}{base:>8}{ratio:>7}  {note}")
        _log("")

    if not all_ratios:
        _log("비율을 낸 테마가 없다 - 이력이 더 필요하다.")
        return 0

    all_ratios.sort()
    n = len(all_ratios)
    def pct(p):
        return all_ratios[min(n - 1, int(n * p))]
    _log(f"=== 비율 분포 (테마 {n}개) ===")
    _log(f"최소 {all_ratios[0]:.2f} / 25% {pct(0.25):.2f} / 중앙 {pct(0.5):.2f} / "
         f"75% {pct(0.75):.2f} / 최대 {all_ratios[-1]:.2f}")
    _log("\n기준값 후보별로 '뉴스 많음'이 되는 테마 수 (두 시장 합쳐서)")
    for c in HIGH_CANDIDATES:
        hit = sum(1 for r in all_ratios if r >= c)
        _log(f"  {c:.1f}배 이상: {hit}개 ({hit / n:.0%})")
    _log("\n기준값은 이 분포를 보고 사람이 config/quarterly.yaml에서 정한다. 코드는 바꾸지 않는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
