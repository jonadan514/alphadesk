"""미국 유니버스 S&P 500 + 400 합치기 (src/collectors/watchlist_collector.py).

미국 테마 32개 중 20개가 소속 기업 5개 미만이었고(중앙값 3개), 원인이 매핑이
아니라 유니버스라는 게 실측으로 확인돼 중형주를 넣었다
(docs/SPEC_us_universe_sp400.md).

여기서 지키는 것 두 가지.
  - universe_source 태그가 반드시 붙는다. 나중에 소급해서 넣을 수 없는 값이라
    (원칙 3) 이게 빠지면 "중형주 편입이 도움이 됐나"를 영원히 못 묻는다.
  - sp400_list.csv가 없어도 sp500만으로 동작한다(점진 배포 안전).

네트워크를 타지 않는다 - 임시 CSV를 만들어 경로만 바꿔 끼운다.
"""
from __future__ import annotations

import pytest

import collectors.watchlist_collector as wc


def _write_csv(path, rows: list[tuple[str, str, str]]) -> None:
    lines = ["Symbol,Security,GICS Sector"]
    lines += [f"{s},{n},{sec}" for s, n, sec in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def universe_files(tmp_path, monkeypatch):
    """sp500/sp400 CSV 경로를 임시 파일로 바꿔 끼운다."""
    sp500 = tmp_path / "sp500_list.csv"
    sp400 = tmp_path / "sp400_list.csv"
    monkeypatch.setattr(wc, "SP500_CSV", sp500)
    monkeypatch.setattr(wc, "SP400_CSV", sp400)
    return sp500, sp400


def test_두_지수를_합치고_출처를_붙인다(universe_files):
    sp500, sp400 = universe_files
    _write_csv(sp500, [("AAPL", "Apple", "Information Technology")])
    _write_csv(sp400, [("MP", "MP Materials", "Materials")])

    items = wc.get_us_universe()

    by_symbol = {i["symbol"]: i for i in items}
    assert by_symbol["AAPL"]["universe_source"] == "sp500"
    assert by_symbol["MP"]["universe_source"] == "sp400"
    assert all(i["market"] == "US" for i in items)


def test_sp400_파일이_없으면_sp500만으로_동작한다(universe_files):
    """점진 배포 안전 - 새 파일이 아직 없는 환경에서도 유니버스가 비면 안 된다."""
    sp500, _sp400 = universe_files
    _write_csv(sp500, [("AAPL", "Apple", "Information Technology")])

    items = wc.get_us_universe()

    assert [i["symbol"] for i in items] == ["AAPL"]
    assert items[0]["universe_source"] == "sp500"


def test_중복_종목은_한_번만_들어간다(universe_files):
    """두 지수에 동시에 있을 수는 없지만, 들어가면 스크리닝이 같은 종목을 두 번 센다."""
    sp500, sp400 = universe_files
    _write_csv(sp500, [("AAPL", "Apple", "Information Technology")])
    _write_csv(sp400, [("AAPL", "Apple", "Information Technology"), ("MP", "MP Materials", "Materials")])

    items = wc.get_us_universe()

    assert [i["symbol"] for i in items] == ["AAPL", "MP"]
    # 먼저 읽은 sp500 쪽 출처가 유지된다
    assert items[0]["universe_source"] == "sp500"


def test_점표기_티커를_야후_표기로_바꾼다(universe_files):
    """BRK.B -> BRK-B. sp500 쪽과 같은 규칙이어야 가격 조회가 된다."""
    sp500, sp400 = universe_files
    _write_csv(sp500, [("BRK.B", "Berkshire Hathaway", "Financials")])
    _write_csv(sp400, [("AA", "Alcoa", "Materials")])

    items = wc.get_us_universe()

    assert items[0]["symbol"] == "BRK-B"
    assert items[0]["yf_symbol"] == "BRK-B"


def test_매핑용_이름에_sp400이_빠지지_않는다():
    """유니버스에는 중형주가 들어오는데 이름이 없으면 LLM이 티커만 보고 판단한다
    ("MP"가 MP Materials인지 알 수 없다). 중형주를 넣은 이유가 얇은 테마를
    채우는 것이므로, 이름이 빠지면 편입 효과가 통째로 사라진다."""
    from scripts.map_theme_companies import build_universe_and_names

    universe, names = build_universe_and_names()
    us_symbols = [i["symbol"] for i in universe if i["market"] == "US"]
    missing = [s for s in us_symbols if s not in names]
    assert not missing, f"이름이 없는 미국 종목 {len(missing)}개: {missing[:10]}"
    assert names.get("MP") == "MP Materials"


def test_실제_저장된_sp400_파일이_기대한_모양이다():
    """저장소에 커밋된 data/sp400_list.csv 자체를 확인한다 - 구조가 바뀌면
    유니버스가 조용히 sp500만으로 줄어든다."""
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "sp400_list.csv"
    assert path.exists(), "sp400_list.csv가 없다"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) > 300, f"종목 수가 너무 적다({len(rows)})"
    assert set(rows[0]) >= {"Symbol", "Security", "GICS Sector"}
    # 얇았던 테마의 순수 플레이가 실제로 들어왔는지 (SPEC 1장 근거)
    symbols = {r["Symbol"] for r in rows}
    for expected in ("MP", "BWXT"):
        assert expected in symbols, f"{expected}가 S&P 400에 없다 - 지수 구성이 바뀌었는지 확인"


def test_미국_유니버스_거의_전부에_사업정보가_있다():
    """매핑 프롬프트는 후보 옆에 산업분류·사업요약을 붙인다. 중형주 400개를 유니버스에
    넣고도 프로필을 안 받으면 이름만 보고 판단돼 BWXT·NXT·ORA 같은 순수 플레이가
    후보에서 빠진다(2026-10-01 파일럿: 커버리지 500/903에서 실제로 빠졌다)."""
    import csv
    import json
    from pathlib import Path

    data = Path(__file__).resolve().parent.parent / "data"
    profiles = json.loads((data / "us_profiles.json").read_text(encoding="utf-8"))
    symbols = []
    for name in ("sp500_list.csv", "sp400_list.csv"):
        with (data / name).open(encoding="utf-8") as f:
            symbols += [r["Symbol"].replace(".", "-") for r in csv.DictReader(f)]
    covered = sum(1 for s in symbols if (profiles.get(s) or {}).get("industry"))
    assert covered / len(symbols) >= 0.98, f"사업정보 커버리지 {covered}/{len(symbols)}"
    for t in ("MP", "BWXT", "NXT", "ORA"):
        assert profiles.get(t, {}).get("summary_long"), f"{t} 사업요약 없음"
