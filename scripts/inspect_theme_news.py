"""theme_news에 쌓인 기사를 읽기만 해서 현황을 보고한다 (분기 재설계 6-1 점검용).

읽기 전용이다. 수집 코드나 데이터는 건드리지 않는다.

보고 내용
  - 시장별 보관 범위(가장 이른 주 ~ 가장 늦은 주), 주 수, 기사 수
  - 분기별 기사 수 (발행일 기준 / 수집 주 기준을 나란히 - 둘이 다르면 경계 문제가 있다는 뜻)
  - 발행일이 비어 있는 기사 비율
  - 발행일이 수집한 주 범위를 벗어난 기사 수
  - 제목에 시황 단어(급등·급락·특징주 등)가 들어간 기사 비율

Usage:
  python scripts/inspect_theme_news.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

MARKET_WORDS = ["급등", "급락", "주가", "특징주", "상한가", "하한가", "52주 신고가", "신고가", "강세", "약세",
                "surge", "soar", "plunge", "stock jumps", "shares rise", "shares fall"]


def _log(msg: str) -> None:
    print(msg)


def quarter_of(day: str) -> str:
    y, m = int(day[:4]), int(day[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def main() -> int:
    conn = get_db()
    rows = conn.execute(
        "SELECT market, theme_id, week_start, published_at, title FROM theme_news"
    ).fetchall()
    conn.close()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not rows:
        _log("theme_news 비어 있음")
        return 0

    by_market: dict[str, list] = defaultdict(list)
    for market, theme_id, week_start, published_at, title in rows:
        by_market[market].append((theme_id, week_start, published_at or "", title or ""))

    _log(f"전체 기사 {len(rows)}건\n")
    for market in sorted(by_market):
        items = by_market[market]
        weeks = sorted({w for _, w, _, _ in items})
        themes = {t for t, _, _, _ in items}
        _log(f"== {market} ==")
        _log(f"  기사 {len(items)}건 / 테마 {len(themes)}개")
        _log(f"  수집 주 범위: {weeks[0]} ~ {weeks[-1]} ({len(weeks)}주)")

        span_days = (date.fromisoformat(weeks[-1]) - date.fromisoformat(weeks[0])).days + 7
        _log(f"  보관 기간: 약 {span_days}일 ({span_days / 365:.2f}년)")

        no_pub = sum(1 for _, _, p, _ in items if not p)
        _log(f"  발행일 없음: {no_pub}건 ({no_pub * 100 // len(items)}%)")

        # 발행일이 수집한 주(월~일) 밖인 기사 - 분기를 발행일로 나눌 때 경계가 흔들리는지 확인
        outside = 0
        for _, w, p, _ in items:
            if not p:
                continue
            ws = date.fromisoformat(w)
            if not (ws <= date.fromisoformat(p) <= ws + timedelta(days=6)):
                outside += 1
        _log(f"  발행일이 수집 주 범위 밖: {outside}건")

        mw = sum(1 for _, _, _, t in items if any(w.lower() in t.lower() for w in MARKET_WORDS))
        _log(f"  제목에 시황 단어 포함: {mw}건 ({mw * 100 // len(items)}%)")

        q_pub = Counter(quarter_of(p) for _, _, p, _ in items if p)
        q_week = Counter(quarter_of(w) for _, w, _, _ in items)
        allq = sorted(set(q_pub) | set(q_week))
        _log("  분기별 기사 수 (발행일 기준 / 수집 주 기준)")
        for q in allq:
            _log(f"    {q}: {q_pub.get(q, 0):5d} / {q_week.get(q, 0):5d}")
        _log("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
