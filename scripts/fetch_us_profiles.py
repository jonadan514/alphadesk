"""S&P500 종목의 산업분류·사업요약을 yfinance에서 받아 data/us_profiles.json 으로 저장한다.

용도: 근거 감사(audit_mapping_evidence.py)가 미국 매핑도 실제 사업정보와 대조할 수 있게.
2026-09-15 신규 테마 US 감사에서 26건 중 21건이 "사업정보 없음"으로 확인 불가였다 -
사업정보가 한국 종목만 있었기 때문이다. 매핑 프롬프트는 미국 후보에 이 정보를 붙이지
않는다(미국 기업은 모델이 사명으로 이미 안다 - medical_device US 17 / KR 2 실측).

한국 프로필과 같은 형식: {ticker: {industry, sector, summary(140자), summary_long(700자)}}
사용법: python scripts/fetch_us_profiles.py [--only-missing]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "us_profiles.json"
# 감사용 긴 요약 길이(2026-09-16: 700 -> 2500). 700자에서 잘린 뒤쪽에 인용할 문구가 있어
# 감사가 멀쩡한 편입을 "인용 검증 실패"로 뒤집는 일이 잦았다.
LONG_CHARS = 2500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--relengthen", action="store_true",
                     help="예전 상한(700자)에서 잘린 summary_long을 다시 받아 늘린다")
    args = ap.parse_args()

    import yfinance as yf

    df = pd.read_csv(ROOT / "data" / "sp500_list.csv")
    tickers = [str(s).replace(".", "-") for s in df["Symbol"]]
    out: dict[str, dict] = {}
    if args.only_missing and OUT.exists():
        out = json.loads(OUT.read_text(encoding="utf-8"))
        tickers = [t for t in tickers
                   if t not in out
                   or (args.relengthen and len((out[t].get("summary_long") or "")) >= 700)]
    print(f"조회 대상 {len(tickers)}종목", flush=True)

    missing = 0
    for n, t in enumerate(tickers, 1):
        rec = {}
        try:
            info = yf.Ticker(t).info
            if info.get("industry"):
                rec["industry"] = info["industry"]
            if info.get("sector"):
                rec["sector"] = info["sector"]
            s = (info.get("longBusinessSummary") or "").strip()
            if s:
                rec["summary"] = s[:140]
                rec["summary_long"] = s[:LONG_CHARS]
        except Exception:
            pass
        if rec:
            out[t] = rec
        else:
            missing += 1
        if n % 50 == 0:
            print(f"  {n}/{len(tickers)} (정보없음 {missing})", flush=True)
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.15)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장 {OUT}: {len(out)}종목 / 정보없음 {missing}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
