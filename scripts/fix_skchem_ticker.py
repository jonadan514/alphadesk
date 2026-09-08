"""theme_members의 죽은 티커 003600(SK케미칼)을 285130으로 교체 - 확인 후 삭제.

003600은 yfinance에서 시총·섹터·가격이 전부 None이고 종목명조차 내부 ID로
오는 죽은 코드다. 실제 SK케미칼은 285130. 같은 회사이므로 "이 회사가 이
테마에 속한다"는 매핑 판단 자체는 유효해서, 재매핑 대신 티커만 교체한다
(evidence·linkage·approved는 그대로 유지).

교체 전후를 전부 출력하고, 대상이 없으면 아무것도 하지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

OLD, NEW = "003600", "285130"


def _log(msg: str) -> None:
    print(f"[skchem] {msg}")


def main() -> None:
    conn = get_db()

    rows = conn.execute(
        "SELECT theme_id, market, run_id, approved, linkage, evidence "
        "FROM theme_members WHERE ticker = ?", (OLD,)
    ).fetchall()
    _log(f"{OLD} 행 {len(rows)}개")
    for theme_id, market, run_id, approved, linkage, evidence in rows:
        _log(f"  {theme_id}({market}) run={run_id} approved={approved} linkage={linkage}")
        _log(f"     근거: {evidence}")

    if not rows:
        _log("대상 없음 - 종료")
        conn.close()
        return

    # 같은 (theme_id, ticker, run_id)가 이미 있으면 UNIQUE 충돌하므로 먼저 확인
    conflicts = conn.execute(
        "SELECT theme_id, run_id FROM theme_members WHERE ticker = ?", (NEW,)
    ).fetchall()
    if conflicts:
        _log(f"⚠ {NEW}가 이미 존재하는 (theme_id, run_id): {conflicts}")
        _log("  충돌 가능성이 있어 중단 - 수동 확인 필요")
        conn.close()
        sys.exit(1)

    conn.execute("UPDATE theme_members SET ticker = ? WHERE ticker = ?", (NEW, OLD))
    conn.commit()

    after = conn.execute(
        "SELECT theme_id, market, approved FROM theme_members WHERE ticker = ?", (NEW,)
    ).fetchall()
    _log(f"교체 완료 - {NEW} 행 {len(after)}개: {after}")

    left = conn.execute("SELECT COUNT(*) FROM theme_members WHERE ticker = ?", (OLD,)).fetchone()[0]
    _log(f"남은 {OLD} 행: {int(left)}")
    conn.close()


if __name__ == "__main__":
    main()
