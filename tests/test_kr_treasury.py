"""국고채 수집 - 휴장일 반복 값 제외와 저장 정리 (2026-10-05 리뷰)."""
import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_holiday_repeats_dropped():
    f = _load("fetch_kr_treasury_pykrx")
    data = {"kr3y": [{"date": "2026-09-23", "value": 3.9}, {"date": "2026-09-24", "value": 3.9},
                     {"date": "2026-09-25", "value": 3.9}, {"date": "2026-09-28", "value": 3.95}],
            "kr10y": [{"date": "2026-09-23", "value": 4.3}, {"date": "2026-09-24", "value": 4.3},
                      {"date": "2026-09-25", "value": 4.3}, {"date": "2026-09-28", "value": 4.31}]}
    out = f.drop_holiday_repeats(data)
    assert [r["date"] for r in out["kr3y"]] == ["2026-09-23", "2026-09-28"]
    # 한 만기만 같으면 휴장일이 아니다
    data2 = {"kr3y": [{"date": "d1", "value": 3.9}, {"date": "d2", "value": 3.9}],
             "kr10y": [{"date": "d1", "value": 4.3}, {"date": "d2", "value": 4.31}]}
    assert len(f.drop_holiday_repeats(data2)["kr3y"]) == 2


def test_save_removes_stale_repeats_inside_range_only():
    s = _load("save_kr_treasury")
    conn = sqlite3.connect(":memory:")
    s.save(conn, {"kr3y": [{"date": d, "value": 3.9} for d in ["2026-09-01", "2026-09-23", "2026-09-24", "2026-09-28"]]})
    s.save(conn, {"kr3y": [{"date": "2026-09-23", "value": 3.9}, {"date": "2026-09-28", "value": 3.95}]})
    dates = [r[0] for r in conn.execute("SELECT date FROM kr_rates ORDER BY date")]
    assert dates == ["2026-09-01", "2026-09-23", "2026-09-28"]      # 범위 안 반복(9/24)만 지움, 범위 밖 9/1 유지
