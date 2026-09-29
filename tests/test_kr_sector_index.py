"""한국 섹터 분석 - KRX 공식 지수 경로 (docs/SPEC_kr_sector_index.md 4장).

scripts/fetch_krx_sector_index.py는 격리 venv(pykrx)에서 돌아 네트워크·KRX
로그인이 필요하므로 여기서 실행하지 않는다(작업지시서 22장 - 테스트는 네트워크를
타지 않는다). 대신 그 스크립트가 쓰는 JSON 포맷을 흉내 낸 파일을 만들어
kr_sector_analyzer._load_krx_index_series()의 읽기·폴백 규칙만 검증한다.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

import src.analyzers.kr_sector_analyzer as ksa
from scripts.fetch_krx_sector_index import BENCHMARK_KEY, SECTOR_TICKERS


def _write_json(path, series: dict) -> str:
    payload = {
        "fetched_at": "2026-09-29T00:00:00",
        "base_date": "20260928",
        "source": "krx",
        "pykrx_version": "1.2.8",
        "series": series,
    }
    p = path / "krx_sector_index.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _entry(dates: list[str], closes: list[float]) -> dict:
    return {"ticker": "9999", "dates": dates, "closes": closes}


FULL_SERIES = {
    "KOSPI":      _entry(["2026-09-01", "2026-09-02", "2026-09-03"], [3000.0, 3010.0, 2990.0]),
    "Technology": _entry(["2026-09-01", "2026-09-02", "2026-09-03"], [100.0, 102.0, 99.0]),
}


# ── 섹터 키 일치 (제일 조용하게 깨질 수 있는 자리) ──────────────────────────

def test_fetch_스크립트의_섹터_키가_SECTOR_ANCHORS와_정확히_일치한다():
    """하나라도 어긋나면 그 섹터가 CYCLE_SECTORS 판정에서 조용히 빠진다.
    fetch_krx_sector_index.SECTOR_TICKERS는 KRX 지수 매핑, kr_sector_analyzer.
    SECTOR_ANCHORS는 폴백 앵커 매핑 - 서로 다른 값을 쓰지만 키 집합(섹터 이름)은
    같아야 analyze()가 어느 경로든 CYCLE_SECTORS를 채울 수 있다."""
    assert set(SECTOR_TICKERS.keys()) == set(ksa.SECTOR_ANCHORS.keys())


def test_CYCLE_SECTORS가_참조하는_섹터가_전부_존재한다():
    """CYCLE_SECTORS 안의 섹터 이름에 오타가 있으면 rs_1m.get(s, 0)이 조용히
    0을 채워 사이클 점수가 항상 0으로 나온다 - 오타를 여기서 잡는다."""
    all_sectors = set(ksa.SECTOR_ANCHORS.keys())
    for cycle, sectors in ksa.CYCLE_SECTORS.items():
        for s in sectors:
            assert s in all_sectors, f"CYCLE_SECTORS['{cycle}']의 '{s}'가 SECTOR_ANCHORS에 없다"


# ── JSON -> pd.Series 변환 ──────────────────────────────────────────────

def test_JSON을_날짜순_시리즈로_읽는다(tmp_path, monkeypatch):
    path = _write_json(tmp_path, FULL_SERIES)
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", path)

    series = ksa._load_krx_index_series()

    assert set(series.keys()) == {"KOSPI", "Technology"}
    kospi = series["KOSPI"]
    assert isinstance(kospi, pd.Series)
    assert list(kospi.index) == sorted(kospi.index)   # 날짜 순
    assert kospi.iloc[0] == 3000.0
    assert kospi.iloc[-1] == 2990.0


def test_뒤섞인_날짜_순서도_정렬해서_읽는다(tmp_path, monkeypatch):
    # dates/closes가 최신 -> 과거 순으로 온 경우(pykrx 응답 순서가 뒤집힐 수 있음)
    scrambled = {
        BENCHMARK_KEY: _entry(["2026-09-03", "2026-09-01", "2026-09-02"], [2990.0, 3000.0, 3010.0]),
    }
    path = _write_json(tmp_path, scrambled)
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", path)

    series = ksa._load_krx_index_series()

    s = series[BENCHMARK_KEY]
    assert list(s.index) == sorted(s.index)
    assert s.iloc[0] == 3000.0   # 09-01 값이 맨 앞으로 와야 한다


# ── 일부 섹터만 있어도 그대로 쓴다 ──────────────────────────────────────────

def test_일부_섹터만_있는_JSON도_있는_것만으로_동작한다(tmp_path, monkeypatch):
    partial = {
        "KOSPI":         _entry(["2026-09-01", "2026-09-02"], [3000.0, 3010.0]),
        "Energy":        _entry(["2026-09-01", "2026-09-02"], [50.0, 51.0]),
        # 나머지 8개 섹터는 fetch 스크립트가 실패해 아예 빠졌다고 가정
    }
    path = _write_json(tmp_path, partial)
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", path)

    series = ksa._load_krx_index_series()

    assert set(series.keys()) == {"KOSPI", "Energy"}


def test_한_지수의_길이_불일치는_그_지수만_건너뛴다(tmp_path, monkeypatch):
    broken = {
        "KOSPI":      _entry(["2026-09-01", "2026-09-02"], [3000.0, 3010.0]),
        "Technology": {"ticker": "1155", "dates": ["2026-09-01", "2026-09-02"], "closes": [100.0]},  # 길이 안 맞음
    }
    path = _write_json(tmp_path, broken)
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", path)

    series = ksa._load_krx_index_series()

    assert set(series.keys()) == {"KOSPI"}   # Technology만 빠지고 KOSPI는 살아있다


# ── 폴백 (미설정 / 파일 없음 / 깨진 JSON) ────────────────────────────────

def test_환경변수_미설정이면_빈_dict(monkeypatch):
    monkeypatch.delenv("KRX_SECTOR_INDEX_JSON", raising=False)
    assert ksa._load_krx_index_series() == {}


def test_파일이_없으면_빈_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", str(tmp_path / "없는파일.json"))
    assert ksa._load_krx_index_series() == {}


def test_깨진_JSON이면_빈_dict(tmp_path, monkeypatch):
    p = tmp_path / "broken.json"
    p.write_text("{이건 JSON이 아니다", encoding="utf-8")
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", str(p))
    assert ksa._load_krx_index_series() == {}


def test_KRX_경로가_비면_fetch_sector_data가_앵커로_폴백한다(monkeypatch):
    """_fetch_sector_data()는 반환 타입(dict[str, pd.Series])을 유지하며,
    KRX 경로가 비면 조용히 yfinance 앵커 경로를 타야 한다."""
    monkeypatch.delenv("KRX_SECTOR_INDEX_JSON", raising=False)
    called = {"yfinance": False}

    def fake_yfinance(period="4mo"):
        called["yfinance"] = True
        return {"KOSPI": pd.Series([1.0, 2.0])}

    monkeypatch.setattr(ksa, "_fetch_sector_data_yfinance", fake_yfinance)

    series, source = ksa._fetch_sector_data_with_source("4mo")

    assert called["yfinance"] is True
    assert source == "anchors"
    assert "KOSPI" in series


def test_KRX_경로가_있으면_그쪽을_쓰고_앵커는_호출하지_않는다(tmp_path, monkeypatch):
    path = _write_json(tmp_path, FULL_SERIES)
    monkeypatch.setenv("KRX_SECTOR_INDEX_JSON", path)

    def fail_if_called(period="4mo"):
        raise AssertionError("KRX 지수가 있는데 yfinance 폴백을 호출했다")

    monkeypatch.setattr(ksa, "_fetch_sector_data_yfinance", fail_if_called)

    series, source = ksa._fetch_sector_data_with_source("4mo")

    assert source == "krx"
    assert set(series.keys()) == {"KOSPI", "Technology"}


# ── analyze()가 sector_source를 payload에 남긴다 ────────────────────────

def test_analyze_결과에_sector_source가_들어간다(monkeypatch):
    """화면에서 KRX 지수로 계산됐는지 앵커 폴백인지 구분할 수 있어야 한다
    (docs/SPEC_kr_sector_index.md 4-2)."""
    monkeypatch.setattr(ksa, "_fetch_sector_data_with_source",
                        lambda period="4mo": ({"KOSPI": pd.Series([1.0, 1.01, 1.02])}, "krx"))
    monkeypatch.setattr(ksa, "_get_sector_stocks", lambda: {})
    monkeypatch.setattr(ksa, "_save", lambda data: None)   # DB 쓰기 없이 계산만 검증

    result = ksa.analyze()

    assert result["sector_source"] == "krx"
