"""성적표 수익률 계산의 한국 종목 티커 변환 (scripts/compute_pick_returns.py).

2026-09-30 발견: 한국 성적표가 처음부터 통째로 비어 있었다(후보 727건이 전부
수익률 NULL). 원인은 '005930' 같은 종목코드를 yfinance에 그대로 넘긴 것 -
yfinance는 '005930.KS'를 요구한다. 가격 조회가 빈 결과를 돌려줘도 upsert는
성공해서(전부 NULL) 로그만 보면 정상으로 보였던 게 발견이 늦은 이유다.

네트워크를 타지 않는다 - 매핑 함수만 검증한다.
"""
from __future__ import annotations

from scripts.compute_pick_returns import _kr_yf_symbol


def test_유니버스에_있으면_그_매핑을_쓴다():
    universe = {"005930": "005930.KS", "247540": "247540.KQ"}
    assert _kr_yf_symbol("005930", universe) == "005930.KS"
    # 코스닥은 .KQ - .KS로 싸잡아 붙이면 조회가 실패한다
    assert _kr_yf_symbol("247540", universe) == "247540.KQ"


def test_유니버스에_없으면_KS로_폴백한다():
    """상장폐지·유니버스 변경으로 매핑이 없어도 조회는 시도한다."""
    assert _kr_yf_symbol("123456", {}) == "123456.KS"


def test_이미_접미사가_있으면_그대로_둔다():
    """두 번 붙어 '005930.KS.KS'가 되면 조회가 조용히 실패한다."""
    assert _kr_yf_symbol("005930.KS", {}) == "005930.KS"
    assert _kr_yf_symbol("247540.KQ", {}) == "247540.KQ"


def test_실제_유니버스_파일로도_동작한다():
    """저장소에 커밋된 data/kr_universe.json이 기대한 모양인지 같이 확인한다 -
    이 파일 구조가 바뀌면 매핑이 조용히 빈 dict가 되고 버그가 재발한다."""
    from scripts.compute_pick_returns import _load_kr_universe

    universe = _load_kr_universe()
    assert len(universe) > 100, "유니버스 매핑이 비었다 - 파일 구조가 바뀌었는지 확인"
    for symbol, yf_symbol in list(universe.items())[:20]:
        assert yf_symbol.startswith(symbol), f"{symbol} -> {yf_symbol}"
        assert yf_symbol.endswith((".KS", ".KQ")), f"{symbol} -> {yf_symbol}"
