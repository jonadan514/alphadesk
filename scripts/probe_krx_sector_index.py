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

# 1차 조사에서 나온 후보 매핑. 9개는 코스피200 섹터 지수(GICS 계열이라 앱 섹터와
# 이름이 거의 그대로 맞는다), Utilities만 코스피200에 해당 섹터가 없어 업종지수
# 전기·가스를 쓴다. 이 10개가 전부 시세를 주는지가 설계의 전제라 따로 검증한다.
PROPOSED = {
    "Technology":             ("1155", "코스피 200 정보기술"),
    "Consumer Cyclical":      ("1158", "코스피 200 경기소비재"),
    "Consumer Defensive":     ("1157", "코스피 200 생활소비재"),
    "Financial Services":     ("1156", "코스피 200 금융"),
    "Industrials":            ("1159", "코스피 200 산업재"),
    "Healthcare":             ("1160", "코스피 200 헬스케어"),
    "Communication Services": ("1150", "코스피 200 커뮤니케이션서비스"),
    "Basic Materials":        ("1153", "코스피 200 철강/소재"),
    "Energy":                 ("1154", "코스피 200 에너지/화학"),
    "Utilities":              ("1017", "전기·가스"),           # 코스피200에 없음
}
BENCHMARK = ("1001", "코스피")


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

    # 후보 매핑 10개 + 벤치마크가 전부 시세를 주는지 확인한다. 설계가 이것에
    # 통째로 달려 있어서, 목록에 이름이 보이는 것만으로는 충분하지 않다.
    _log("=" * 60)
    _log("후보 매핑 시세 조회 (섹터 10 + 벤치마크)")
    checks: dict = {}
    targets = [("(벤치마크) KOSPI", *BENCHMARK)] + [
        (sector, tk, nm) for sector, (tk, nm) in PROPOSED.items()
    ]
    for sector, tk, expected_name in targets:
        row: dict = {"ticker": tk, "expected_name": expected_name}
        try:
            actual = ps.get_index_ticker_name(tk)
        except Exception as e:
            actual = f"<실패 {type(e).__name__}>"
        row["actual_name"] = actual
        row["name_match"] = (actual == expected_name)
        try:
            df = ps.get_index_ohlcv_by_date(fromdate, todate, tk)
            row["rows"] = len(df)
            row["first"] = str(df.index[0].date()) if len(df) else None
            row["last"] = str(df.index[-1].date()) if len(df) else None
            # 종가가 전부 같으면(산출 중단된 지수) RS가 0으로 굳는다 - 변동 여부 확인
            closes = df["종가"] if "종가" in df.columns else df.iloc[:, 3]
            row["distinct_closes"] = int(closes.nunique())
        except Exception as e:
            row["rows"] = 0
            row["error"] = f"{type(e).__name__}: {e}"
        mark = "OK " if row.get("rows", 0) >= 60 and row.get("distinct_closes", 0) > 5 else "!! "
        namenote = "" if row["name_match"] else f"  [이름 다름: {actual}]"
        _log(f"  {mark}{sector:<24} {tk}  {row.get('rows', 0):>3}행  "
             f"서로 다른 종가 {row.get('distinct_closes', 0):>3}{namenote}"
             + (f"  {row['error']}" if row.get("error") else ""))
        checks[sector] = row
    result["proposed_checks"] = checks

    ok = sum(1 for r in checks.values() if r.get("rows", 0) >= 60 and r.get("distinct_closes", 0) > 5)
    _log(f"  -> {ok}/{len(checks)} 사용 가능")

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
