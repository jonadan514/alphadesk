"""Turso DB 용량 점검 (읽기 전용). 2026-10-05 뉴스 저장 중 `SQLite error: disk I/O error`가 나서 만든다.

1) PRAGMA page_count * page_size - DB 파일 전체 크기 (Turso가 막으면 건너뜀)
2) dbstat - 테이블·인덱스별 실제 바이트 (지원 안 되면 건너뜀)
3) 테이블별 행 수 + 열 길이 합(대략 바이트) - 위 두 개가 안 될 때의 추정치
4) theme_news 주별·시장별 행 수 - 주마다 얼마씩 늘어나는지

    python scripts/report_db_size.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

MB = 1024 * 1024


def _try(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception as e:  # Turso가 막는 PRAGMA/가상 테이블
        print(f"  (사용 불가: {sql.split()[0]} {sql.split()[1] if len(sql.split()) > 1 else ''} - {e})")
        return None


def main() -> int:
    conn = get_db()
    print("== 1. DB 파일 크기 ==")
    pc = _try(conn, "PRAGMA page_count")
    ps = _try(conn, "PRAGMA page_size")
    fl = _try(conn, "PRAGMA freelist_count")
    if pc and ps:
        total = int(pc[0][0]) * int(ps[0][0])
        print(f"  page_count={pc[0][0]} page_size={ps[0][0]} -> {total / MB:.1f} MB")
        if fl:
            print(f"  빈 페이지(freelist)={fl[0][0]} -> {int(fl[0][0]) * int(ps[0][0]) / MB:.1f} MB")

    print("== 2. dbstat (테이블·인덱스별) ==")
    st = _try(conn, "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name ORDER BY 2 DESC LIMIT 25")
    if st:
        for name, size in st:
            print(f"  {name:45s} {int(size) / MB:8.2f} MB")

    print("== 3. 테이블별 행 수·대략 크기 ==")
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE '_litestream%' AND name NOT LIKE 'libsql_%' ORDER BY name").fetchall()]
    sizes = []
    for t in tables:
        try:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            if cols and n:
                expr = " + ".join(f'COALESCE(LENGTH("{c}"), 0)' for c in cols)
                b = conn.execute(f'SELECT SUM({expr}) FROM "{t}"').fetchone()[0] or 0
            else:
                b = 0
            sizes.append((t, int(n), int(b)))
        except Exception as e:
            print(f"  {t}: 조회 실패 {e}")
    for t, n, b in sorted(sizes, key=lambda x: -x[2]):
        print(f"  {t:40s} {n:>10,}행 {b / MB:8.2f} MB")
    print(f"  합계(데이터만, 인덱스 제외) {sum(b for *_, b in sizes) / MB:.1f} MB")

    print("== 4. theme_news 주별 증가 ==")
    rows = _try(conn, "SELECT week_start, market, COUNT(*), SUM(LENGTH(COALESCE(title,'')) + "
                      "LENGTH(COALESCE(url,''))) FROM theme_news GROUP BY week_start, market "
                      "ORDER BY week_start DESC, market LIMIT 30")
    if rows:
        for w, m, n, b in rows:
            print(f"  {w} {m}: {int(n):>7,}행 {int(b or 0) / MB:6.2f} MB")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
