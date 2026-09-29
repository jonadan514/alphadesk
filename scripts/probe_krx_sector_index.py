"""KRX 공식 업종지수를 섹터 분석에 쓸 수 있는지 실측한다. 아무것도 쓰지 않는다.

배경:
kr_sector_analyzer.py는 한국에 섹터 ETF가 없다는 이유로 섹터마다 대표 종목
1-3개를 코드에 박아 두고 그 평균으로 섹터 수익률을 낸다. Utilities는 한국전력
한 종목이라 사실상 "한국전력 주가"를 유틸리티 섹터라고 부르고 있는 셈이다.

KRX는 업종지수를 직접 산출해 공표한다. 그걸 쓸 수 있으면 앵커 종목을 고르는
자의적 판단이 통째로 사라진다. 다만 쓰려면 세 가지가 실제로 돼야 한다.

  1. 지수 목록 조회가 되는가 (KRX 로그인 필요 - pykrx 1.2.8)
  2. 업종지수의 과거 시세를 4개월치 받을 수 있는가 (RS 계산에 필요)
  3. KRX 업종 이름이 앱이 쓰는 섹터 10개에 맞춰 붙는가

3번이 이 조사의 핵심이다. KRX 업종은 상장 구분에 가까워서(전기전자·운수장비·
화학 …) GICS 계열 섹터와 일대일이 아니다. 그래서 매핑을 미리 정해 놓고 검증하는
대신, **실제 목록을 그대로 출력**해서 사람이 보고 판단할 수 있게 한다.

자격증명은 설정 여부와 길이만 보고하고 값은 절대 출력하지 않는다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

# 앱이 쓰는 섹터 이름(kr_sector_analyzer.SECTOR_ANCHORS의 키). 이 목록에 KRX
# 업종을 맞춰 붙일 수 있는지가 판단 기준이라 여기 그대로 적어 둔다.
APP_SECTORS = [
    "Technology", "Consumer Cyclical", "Consumer Defensive", "Financial Services",
    "Industrials", "Healthcare", "Communication Services", "Basic Materials",
    "Energy", "Utilities",
]


def _log(msg: str) -> None:
    print(f"[probe-krx-idx] {msg}", flush=True)


def _recent_business_date() -> str:
    d = datetime.now() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def probe_credentials() -> None:
    for k in ("KRX_ID", "KRX_PW"):
        v = os.getenv(k)
        _log(f"{k}: {'설정됨(길이 ' + str(len(v)) + ')' if v else '미설정'}")


def main() -> int:
    probe_credentials()
    try:
        from pykrx import stock as ps
    except Exception as e:
        _log(f"pykrx import 실패: {type(e).__name__}: {e}")
        return 1

    import pandas as pd
    _log(f"pykrx {getattr(__import__('pykrx'), '__version__', '?')} / pandas {pd.__version__}")

    todate = os.getenv("PROBE_DATE") or _recent_business_date()
    fromdate = (datetime.strptime(todate, "%Y%m%d") - timedelta(days=150)).strftime("%Y%m%d")
    _log(f"조회 구간 {fromdate} - {todate}")

    result: dict = {"todate": todate, "fromdate": fromdate, "markets": {}}

    for market in ("KOSPI", "KOSDAQ"):
        _log("=" * 60)
        _log(f"[{market}] 지수 목록")
        entry: dict = {"tickers": [], "error": None}
        try:
            tickers = ps.get_index_ticker_list(market=market)
        except Exception as e:
            _log(f"  목록 조회 실패: {type(e).__name__}: {e}")
            entry["error"] = f"{type(e).__name__}: {e}"
            result["markets"][market] = entry
            continue

        _log(f"  {len(tickers)}개")
        for t in tickers:
            try:
                name = ps.get_index_ticker_name(t)
            except Exception as e:
                name = f"<이름 실패: {type(e).__name__}>"
            entry["tickers"].append({"ticker": t, "name": name})
            _log(f"    {t}  {name}")
        result["markets"][market] = entry

    # 시세를 실제로 받아본다. 목록만 되고 시세가 안 되면 RS를 못 만든다.
    _log("=" * 60)
    _log("업종지수 시세 조회 시험")
    samples = []
    kospi = result["markets"].get("KOSPI", {})
    for item in (kospi.get("tickers") or [])[:6]:
        t = item["ticker"]
        try:
            df = ps.get_index_ohlcv_by_date(fromdate, todate, t)
            rows = len(df)
            first = str(df.index[0].date()) if rows else "-"
            last = str(df.index[-1].date()) if rows else "-"
            _log(f"  {t} {item['name']}: {rows}행 ({first} - {last})")
            samples.append({"ticker": t, "name": item["name"], "rows": rows})
        except Exception as e:
            _log(f"  {t} {item['name']}: 실패 {type(e).__name__}: {e}")
            samples.append({"ticker": t, "name": item["name"], "rows": 0,
                            "error": f"{type(e).__name__}: {e}"})
    result["ohlcv_samples"] = samples

    _log("=" * 60)
    _log("앱이 쓰는 섹터 이름(이 목록에 위 업종을 맞춰 붙일 수 있어야 한다):")
    for s in APP_SECTORS:
        _log(f"    {s}")

    out = os.getenv("PROBE_OUT") or "/tmp/krx_sector_index.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _log(f"결과 저장: {out}")
    except Exception as e:
        _log(f"결과 저장 실패: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
