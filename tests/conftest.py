"""테스트 공통 설정.

저장소 루트와 src/를 import 경로에 넣는다 - 운영 스크립트들이
`from src.db...`와 `from collectors...` 두 형태를 모두 쓰기 때문이다.

테스트는 네트워크·DB·LLM을 쓰지 않는다. 외부 호출이 필요한 코드는 가짜 응답을 넣어
계산 규칙만 검증한다(작업지시서 22장: 운영 DB를 건드리는 테스트 금지).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture
def memory_db():
    """메모리 sqlite 연결. 스키마는 각 테스트가 ensure_schema로 만든다."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


class TursoLikeConn:
    """운영 DB(_TursoConn)의 까다로운 성질만 흉내 낸 메모리 sqlite 연결.

    왜 필요한가: 운영은 Turso HTTP인데 테스트는 로컬 sqlite라, 둘의 차이로만 생기는 버그는
    테스트를 전부 통과한다. 실제로 2026-09-01에 뉴스 기준선이 `int + str`로 죽었고,
    2026-09-21 검토에서 분기 재무 조회가 연도를 문자열로 돌려주는 것이 같은 이유로 발견됐다.

    흉내 내는 성질
      - INTEGER 컬럼 값을 **문자열**로 돌려준다 (Hrana가 64비트 정밀도 손실을 막으려고
        정수를 문자열로 싣고, _TursoConn.fetchall()이 변환 없이 넘긴다)
      - execute()가 커서가 아니라 자기 자신을 돌려주고 **rowcount가 없다**
      - commit()이 아무것도 하지 않는다
    """

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._rows: list = []

    def execute(self, sql: str, params=()):
        rows = self._conn.execute(sql, params).fetchall()
        self._rows = [tuple(str(v) if isinstance(v, int) and not isinstance(v, bool) else v
                            for v in row) for row in rows]
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def commit(self):
        pass

    def close(self):
        self._conn.close()


@pytest.fixture
def turso_like_db():
    """운영 DB의 반환 타입을 흉내 내는 연결. 로컬 sqlite 테스트가 놓치는 차이를 잡는다."""
    conn = TursoLikeConn()
    yield conn
    conn.close()
