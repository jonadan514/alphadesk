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
