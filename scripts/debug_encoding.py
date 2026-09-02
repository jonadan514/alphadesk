"""매크로 스냅샷 한글 라벨 깨짐 원인 추적용 임시 스크립트 - 확인 후 삭제.

1단계(완료) - 나가는 HTTP 요청 바이트는 완벽하게 올바름을 확인.
2단계 - 실제 Turso에 써보고 바로 다시 읽어서, 저장 자체가 깨지는지 확인.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

TEST_LABEL = "미국 10년물 국채금리"

with get_db() as con:
    con.execute("""
        CREATE TABLE IF NOT EXISTS debug_encoding_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            val TEXT NOT NULL
        )
    """)
    con.execute("DELETE FROM debug_encoding_test")
    con.execute("INSERT INTO debug_encoding_test (val) VALUES (?)", (TEST_LABEL,))

    row = con.execute("SELECT val FROM debug_encoding_test").fetchone()
    got = row[0]

print("보낸 값 repr:", repr(TEST_LABEL))
print("받은 값 repr:", repr(got))
print("동일한가:", got == TEST_LABEL)
print("받은 값 utf-8 인코딩 시도:", end=" ")
try:
    print(got.encode("utf-8"))
except UnicodeEncodeError as e:
    print("실패:", e)

# 정리
with get_db() as con:
    con.execute("DROP TABLE IF EXISTS debug_encoding_test")
