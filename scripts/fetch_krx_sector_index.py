"""pykrx로 KRX 공식 섹터 지수(코스피200 섹터지수 9개 + 유틸리티 업종지수)를
받아 JSON으로 떨어뜨린다.

**이 스크립트는 격리된 가상환경에서 실행된다.** pykrx 1.2.8은 pandas<3.0을
요구하는데 본 저장소는 pandas 3.x를 쓴다. 같은 환경에 두면 pip이 에러 대신
pykrx를 1.0.51까지 조용히 낮춰버리고, 그 버전에는 KRX 로그인 기능(auth 모듈)이
아예 없어 모든 조회가 실패한다. fetch_kr_universe_pykrx.py와 같은 사정이라
그 파일과 같은 규칙을 따른다: 저장소의 다른 모듈을 import하지 않는다.
의존성은 pykrx와 표준 라이브러리뿐이며, 결과는 JSON 파일로만 주고받는다.

지수 선택 근거는 docs/SPEC_kr_sector_index.md 2장 참고. 요약:
  - 9개는 코스피200 섹터지수(1150-1160) - GICS 계열이라 앱 섹터 이름과 그대로 맞는다.
  - Utilities만 코스피200에 해당 섹터가 없어 업종지수 전기·가스(1017)를 쓴다
    (다른 지수 계열이 섞이는 것을 알고 있다 - 대안이 "한국전력 한 종목"이라 유지).
  - 벤치마크는 코스피(1001). 코스피200이 9개 섹터엔 더 정확하지만 Utilities가
    전 코스피 기준이라 화면이 말하는 "코스피 대비"와 맞추는 쪽을 택했다.

이 매핑은 scripts/probe_krx_sector_index.py의 PROPOSED/BENCHMARK와 같은 내용이나
그쪽은 조사 기록이고 이 파일이 정본이다 - 운영 경로가 조사 스크립트를 import하지
않도록 값을 복제해 둔다.

사용법:
    python scripts/fetch_krx_sector_index.py --out /tmp/krx_sector_index.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# kr_sector_analyzer.SECTOR_ANCHORS의 키와 정확히 같아야 한다 - 여기서 하나라도
# 어긋나면 분석기가 그 섹터를 아예 못 찾아 사이클 판정이 조용히 빈 값을 먹는다.
# (SECTOR_TICKERS 키 집합 == kr_sector_analyzer.SECTOR_ANCHORS 키 집합은
# tests/test_kr_sector_index.py가 고정한다.)
SECTOR_TICKERS = {
    "Technology":             "1155",   # 코스피 200 정보기술
    "Consumer Cyclical":      "1158",   # 코스피 200 경기소비재
    "Consumer Defensive":     "1157",   # 코스피 200 생활소비재
    "Financial Services":     "1156",   # 코스피 200 금융
    "Industrials":            "1159",   # 코스피 200 산업재
    "Healthcare":             "1160",   # 코스피 200 헬스케어
    "Communication Services": "1150",   # 코스피 200 커뮤니케이션서비스
    "Basic Materials":        "1153",   # 코스피 200 철강/소재
    "Energy":                 "1154",   # 코스피 200 에너지/화학
    "Utilities":              "1017",   # 전기·가스 (업종지수 - 코스피200에 없음)
}
BENCHMARK_TICKER = "1001"   # 코스피
BENCHMARK_KEY = "KOSPI"     # kr_sector_analyzer가 기대하는 벤치마크 키


def _log(msg: str) -> None:
    print(f"[fetch-krx-sector] {msg}", flush=True)


def _recent_business_date() -> str:
    """직전 영업일. 당일을 쓰지 않는 이유: 장 마감 전에는 그날 시세가 아직
    없어 0행이 돌아오고, 그것이 '조회 실패'와 구분되지 않는다."""
    d = datetime.now() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=150, help="조회 구간 일수 (기본 150 - 4개월 수익률 계산에 필요)")
    ap.add_argument("--date", default=None, help="기준일 YYYYMMDD (비우면 직전 영업일)")
    args = ap.parse_args()

    import pykrx
    from pykrx import stock as ps

    ver = getattr(pykrx, "__version__", "unknown")
    _log(f"pykrx 버전 {ver}")
    for k in ("KRX_ID", "KRX_PW"):
        v = os.getenv(k)
        _log(f"{k}: {'설정됨(길이 ' + str(len(v)) + ')' if v else '미설정'}")

    todate = args.date or _recent_business_date()
    fromdate = (datetime.strptime(todate, "%Y%m%d") - timedelta(days=args.days)).strftime("%Y%m%d")
    _log(f"조회 구간 {fromdate} - {todate}")

    targets: dict[str, str] = {BENCHMARK_KEY: BENCHMARK_TICKER, **SECTOR_TICKERS}
    series: dict[str, dict] = {}
    failed: list[str] = []

    for key, ticker in targets.items():
        try:
            df = ps.get_index_ohlcv_by_date(fromdate, todate, ticker)
            if df is None or len(df) == 0:
                _log(f"  {key} ({ticker}): 0행 - 실패로 간주")
                failed.append(key)
                continue
            closes = df["종가"] if "종가" in df.columns else df.iloc[:, 3]
            dates = [d.strftime("%Y-%m-%d") for d in df.index]
            series[key] = {
                "ticker": ticker,
                "dates": dates,
                "closes": [float(c) for c in closes],
            }
            _log(f"  {key} ({ticker}): {len(df)}행 ({dates[0]} - {dates[-1]})")
        except Exception as e:
            _log(f"  {key} ({ticker}): 실패 {type(e).__name__}: {str(e)[:200]}")
            failed.append(key)

    if not series:
        _log("전부 실패 - 파일을 쓰지 않는다(기존 폴백 유지)")
        return 2

    if BENCHMARK_KEY not in series:
        # 벤치마크 없이는 RS(상대강도)를 낼 수 없다 - 섹터만 있어도 쓸모가 없다.
        _log(f"벤치마크({BENCHMARK_KEY}) 조회 실패 - 파일을 쓰지 않는다")
        return 2

    if failed:
        _log(f"일부 실패 - 빠진 채로 저장: {', '.join(failed)}")

    payload = {
        "fetched_at": datetime.now().isoformat(),
        "base_date": todate,
        "source": "krx",
        "pykrx_version": ver,
        "series": series,
    }
    out = args.out
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    _log(f"저장 완료 {out} - {len(series)}/{len(targets)}개 지수")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
