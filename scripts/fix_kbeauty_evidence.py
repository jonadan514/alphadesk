"""k_beauty 재매핑(run_id=20260905135756-ce247e)에서 비판 패스가 flagged한
2건의 evidence를 실제 사실관계로 교정한다. LLM이 회사 선택 자체는 맞았지만
브랜드명을 두 번 다 잘못 지어냈던 것을 웹 검색으로 직접 확인 후 수정 -
확인 후 삭제할 1회성 스크립트.

- 090430 아모레G: "유통 자회사"/"이니스프리·미샤 직접 운영" (둘 다 오류) ->
  실제로는 아모레퍼시픽(002790)의 지주회사(모회사). linkage도 partial로 정정.
- 226320 잇츠한불: "더페이스샵·이니스프리"/"이너프·더마리프트" (둘 다 오류,
  전부 다른 회사 브랜드) -> 실제 자사 브랜드는 잇츠스킨·프레스티지·파워10
  (+ 자회사 네오팜의 아토팜·리얼베리어).

Usage:
  python scripts/fix_kbeauty_evidence.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

RUN_ID = "20260905135756-ce247e"

FIXES = [
    {
        "ticker": "090430",
        "evidence": "아모레G(現 아모레퍼시픽홀딩스)는 아모레퍼시픽(002790)의 지주회사로, "
                    "설화수·헤라 등 K-뷰티 브랜드를 보유한 그룹 전체의 모회사다.",
        "linkage": "partial",
    },
    {
        "ticker": "226320",
        "evidence": "잇츠한불은 자체 브랜드 '잇츠스킨'·'프레스티지'·'파워10'과 "
                    "자회사 네오팜의 '아토팜'·'리얼베리어'를 통해 화장품을 제조·판매한다.",
        "linkage": "direct",
    },
]


def _log(msg: str) -> None:
    print(f"[fix] {msg}")


def main() -> None:
    conn = get_db()
    for fix in FIXES:
        row = conn.execute(
            "SELECT evidence FROM theme_members WHERE theme_id = 'k_beauty' AND ticker = ? AND run_id = ?",
            (fix["ticker"], RUN_ID),
        ).fetchone()
        if not row:
            _log(f"{fix['ticker']}: 해당 run_id에서 못 찾음 - 건너뜀")
            continue
        _log(f"{fix['ticker']}: 기존 evidence = {row[0]!r}")
        conn.execute(
            "UPDATE theme_members SET evidence = ?, linkage = ?, flagged = 0 "
            "WHERE theme_id = 'k_beauty' AND ticker = ? AND run_id = ?",
            (fix["evidence"], fix["linkage"], fix["ticker"], RUN_ID),
        )
        _log(f"{fix['ticker']}: 교정 완료 -> {fix['evidence']!r} (linkage={fix['linkage']}, flagged=0)")
    conn.commit()
    conn.close()
    _log("완료")


if __name__ == "__main__":
    main()
