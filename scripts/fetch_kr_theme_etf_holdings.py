"""국내 테마 ETF의 구성종목을 받아 JSON으로 떨어뜨린다 (시장 인식 소속의 근거 자료).

SPEC_theme_company_mapping.md 11장. 결과는 scripts/report_perception_candidates.py가
읽어 테마별 "시장 인식" 후보를 만든다. 편입은 사람이 검토 파일로 한다.

**이 스크립트는 격리된 가상환경에서 실행된다** (fetch_kr_universe_pykrx.py와 같은 이유 -
pykrx 1.2.8은 pandas<3.0을 요구한다). 저장소의 다른 모듈을 import하지 않고, YAML도
쓰지 않도록 키워드 설정은 호출하는 쪽이 JSON으로 넘긴다.

사용법:
    python scripts/fetch_kr_theme_etf_holdings.py --keywords kw.json --out data/kr_theme_etf_holdings.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

# 국내 주식 테마로 볼 수 없는 ETF. 구성종목이 해외 주식이거나(이름에 지역),
# 지수를 배수로 따라가 비중이 의미 없는 것(레버리지·인버스).
EXCLUDE_NAME_WORDS = ("레버리지", "인버스", "2X", "선물", "채권", "커버드콜",
                      "미국", "글로벌", "차이나", "중국", "일본", "인도", "베트남", "유럽",
                      "S&P", "나스닥", "필라델피아", "대만", "TOP10", "선진국", "신흥국")


def _log(msg: str) -> None:
    print(f"[kr_etf] {msg}", flush=True)


def _prev_business_date(base: datetime | None = None) -> str:
    d = (base or datetime.now()) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def match_themes(etf_name: str, keywords: dict[str, list[str]]) -> list[str]:
    """ETF 이름에 키워드가 들어 있는 테마 id 목록. 제외 단어가 있으면 빈 목록."""
    name = etf_name.replace(" ", "")
    if any(w.replace(" ", "") in name for w in EXCLUDE_NAME_WORDS):
        return []
    return [tid for tid, kws in keywords.items() if any(k.replace(" ", "") in name for k in kws)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", required=True, help="{theme_id: [ETF 이름 키워드]} JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=None, help="YYYYMMDD (기본: 직전 영업일)")
    args = ap.parse_args()

    from pykrx import stock  # 격리 환경에만 있다

    keywords = json.load(open(args.keywords, encoding="utf-8"))
    date = args.date or _prev_business_date()
    tickers = stock.get_etf_ticker_list(date)
    if not tickers:
        _log(f"ETF 목록 0건({date}) - 조회 실패로 본다")
        return 1

    etfs: list[dict] = []
    failed: list[str] = []
    for t in tickers:
        name = stock.get_etf_ticker_name(t)
        themes = match_themes(name, keywords)
        if not themes:
            continue
        try:
            df = stock.get_etf_portfolio_deposit_file(t, date)
        except Exception as e:  # noqa: BLE001 - ETF 하나 실패로 전체를 멈추지 않는다
            failed.append(f"{t} {name}: {type(e).__name__}")
            continue
        weight_col = "비중" if "비중" in df.columns else None
        holdings = []
        for code, row in df.iterrows():
            code = str(code)
            if len(code) != 6:          # 현금·해외 종목 등
                continue
            w = float(row[weight_col]) if weight_col else None
            holdings.append({"ticker": code, "weight": w})
        etfs.append({"etf": t, "name": name, "themes": themes, "holdings": holdings})
        time.sleep(0.3)

    _log(f"{date}: 전체 ETF {len(tickers)}개 중 테마 매칭 {len(etfs) + len(failed)}개, 구성종목 조회 실패 {len(failed)}개")
    for f in failed[:20]:
        _log(f"  실패 {f}")
    if not etfs:
        _log("매칭된 ETF의 구성종목을 하나도 못 받았다 - 조회 실패로 본다")
        return 1
    json.dump({"date": date, "etfs": etfs, "failed": failed},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
