"""매크로 스냅샷 한글 라벨 깨짐 원인 추적 3단계 - 확인 후 삭제.

1단계 - 나가는 HTTP 요청 바이트는 완벽하게 올바름을 확인.
2단계 - 단순 문자열 하나는 Turso 왕복이 완벽하게 정상임을 확인.
3단계 - 실제 analyze()가 만드는 것과 동일한(중첩 JSON) 페이로드로 재현 시도.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db.data_store import get_db

# macro_snapshot.py의 실제 items 구조를 그대로 흉내 (야후 호출 없이 고정값으로)
data = {
    "date": "2026-09-02",
    "items": {
        "us10y": {"value": 4.79, "chg_1d": -0.01, "chg_1w": 0.15, "label": "미국 10년물 국채금리", "unit": "%"},
        "us30y": {"value": 5.26, "chg_1d": -0.01, "chg_1w": 0.09, "label": "미국 30년물 국채금리", "unit": "%"},
        "usdkrw": {"value": 1359.0, "chg_1d": -7.0, "chg_1w": -22.0, "label": "원/달러 환율", "unit": "원"},
        "vix": {"value": 16.1, "chg_1d": -0.3, "chg_1w": 0.6, "label": "VIX 변동성지수", "unit": ""},
    },
}
payload_str = json.dumps(data, ensure_ascii=False)
print("=== 보낼 payload 문자열 (ensure_ascii=False) ===")
print(repr(payload_str)[:200])

with get_db() as con:
    con.execute("""
        CREATE TABLE IF NOT EXISTS debug_encoding_test2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL
        )
    """)
    con.execute(
        "INSERT OR REPLACE INTO debug_encoding_test2 (date, payload) VALUES (?, ?)",
        (data["date"], payload_str),
    )
    row = con.execute("SELECT payload FROM debug_encoding_test2 WHERE date = ?", (data["date"],)).fetchone()
    got = row[0]

print()
print("=== Python으로 즉시 다시 읽은 값 ===")
print("동일한가:", got == payload_str)
parsed_back = json.loads(got)
label = parsed_back["items"]["us10y"]["label"]
print("us10y label repr:", repr(label))
try:
    print("utf-8 인코딩:", label.encode("utf-8"))
except UnicodeEncodeError as e:
    print("인코딩 실패:", e)

with get_db() as con:
    con.execute("DROP TABLE IF EXISTS debug_encoding_test2")
