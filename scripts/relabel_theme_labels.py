"""테마 레이더 라벨 용어를 새 이름으로 일괄 교체(2026-09-02).

"조용히 좋아짐" 등 한국어 라벨을 좀 더 직관적인 영어 2단어 짝(Quiet/Buzz/Full)으로
바꾸기로 함(사용자 요청). 세 축(뉴스·실적·주가) 원 신호값(news_arrow 등)은 전혀
건드리지 않고, 이미 계산된 결과의 표시용 label 문자열만 새 이름으로 맞춘다 -
측정치를 다시 계산하거나 덮어쓰는 게 아니라 같은 분류에 새 이름을 붙이는 것뿐이라
"이력 테이블을 덮어쓰지 않는다" 원칙과 충돌하지 않는다고 판단.

재실행해도 안전(이미 새 이름인 행은 조건에 안 걸려 그대로 둠).

Usage:
  python scripts/relabel_theme_labels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

RENAME = {
    "조용히 좋아짐": "Quiet Strength",
    "바닥 통과 가능": "Quiet Recovery",
    "새로 부상": "Early Buzz",
    "관심 강화": "Full Alignment",
    "과열 경계": "Overheated Buzz",
    "약화": "Full Decline",
}


def _log(msg: str) -> None:
    print(f"[relabel] {msg}")


def main() -> None:
    # get_db()가 로컬에선 sqlite3.Connection, 프로덕션에선 Turso HTTP 래퍼(_TursoConn)를
    # 반환하는데 후자는 cursor.rowcount를 구현 안 해서, UPDATE 전에 대상 건수를
    # 먼저 SELECT COUNT로 세어 두 환경 모두에서 정확한 로그가 남게 한다.
    conn = get_db()
    total = 0
    for old, new in RENAME.items():
        row = conn.execute(
            "SELECT COUNT(*) FROM theme_signals WHERE label = ?", (old,)
        ).fetchone()
        n = int(row[0]) if row and row[0] is not None else 0
        conn.execute("UPDATE theme_signals SET label = ? WHERE label = ?", (new, old))
        total += n
        _log(f"{old!r} -> {new!r}: {n}건")
    conn.commit()
    conn.close()
    _log(f"완료 - 총 {total}건 갱신")


if __name__ == "__main__":
    main()
