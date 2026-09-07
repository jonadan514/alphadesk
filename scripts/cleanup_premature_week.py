"""아직 오지 않은 주(2026-09-07)에 수동 실행으로 미리 만들어진 theme_signals 행 정리.

B-2~B-4 검증 중 월요일 새벽에 실적/주가 축을 수동 실행하면서, 아직 시작도
안 한 주(뉴스 0건)에 행이 생겼다. 프론트는 MAX(week_start)로 최신 주를
잡으므로 이 빈 주가 데이터가 꽉 찬 지난주(2026-08-31)를 가려버린다.

이 행들은 "이력"이 아니라 시기상조로 만들어진 것이고, 다음 일요일 크론
(22:00~22:45 UTC)이 같은 주를 뉴스까지 포함해 정상적으로 다시 채운다.
삭제 전 무엇을 지우는지 전부 출력한다.

Usage:
  python scripts/cleanup_premature_week.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

TARGET_WEEK = "2026-09-07"


def _log(msg: str) -> None:
    print(f"[cleanup] {msg}")


def main() -> None:
    conn = get_db()

    rows = conn.execute(
        "SELECT market, theme_id, news_count, news_arrow, earn_arrow, price_arrow, label "
        "FROM theme_signals WHERE week_start = ? ORDER BY market, theme_id",
        (TARGET_WEEK,),
    ).fetchall()
    _log(f"{TARGET_WEEK} 행 {len(rows)}개 발견")

    labeled = [r for r in rows if r[6]]
    nonzero_news = [r for r in rows if r[2] not in (None, 0, "0")]
    _log(f"  그중 라벨 있는 행: {len(labeled)}개")
    _log(f"  그중 뉴스 건수 0이 아닌 행: {len(nonzero_news)}개")

    # 안전장치: 실제로 뉴스가 수집된 주였다면 지우면 안 된다.
    if labeled or nonzero_news:
        _log("⚠ 라벨이 있거나 뉴스가 수집된 행이 있음 - 시기상조 행이 아닐 수 있어 중단")
        conn.close()
        sys.exit(1)

    conn.execute("DELETE FROM theme_signals WHERE week_start = ?", (TARGET_WEEK,))
    conn.execute("DELETE FROM theme_news WHERE week_start = ?", (TARGET_WEEK,))
    conn.commit()

    for market in ("US", "KR"):
        latest = conn.execute(
            "SELECT MAX(week_start) FROM theme_signals WHERE market = ?", (market,)
        ).fetchone()[0]
        n = conn.execute(
            "SELECT COUNT(*) FROM theme_signals WHERE market = ? AND week_start = ? AND label IS NOT NULL",
            (market, latest),
        ).fetchone()[0]
        _log(f"  정리 후 {market} 최신 주: {latest} (라벨 {int(n)}개)")

    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
