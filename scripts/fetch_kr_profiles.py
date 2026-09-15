"""KR 유니버스 종목의 산업분류·사업요약을 yfinance에서 받아 JSON으로 저장한다.

용도: 테마 매핑 프롬프트에 후보 기업의 사업 내용을 붙이기 위한 것.
LLM은 '214150 (KR) 클래시스'만 보고는 이 회사가 미용 의료기기 업체임을 모른다
(2026-09-14 확인 - 같은 프롬프트로 medical_device는 US 17종목을 잡았는데
KR은 2종목에 그쳤다). industry='Medical Devices'가 붙으면 판단 근거가 생긴다.

주의: 코스닥 일부 종목은 yfinance에 sector/industry/summary가 아예 없다
(티씨케이, GST 등). 그런 종목은 이 경로로는 보완되지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default=str(ROOT / "data" / "kr_universe.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "kr_profiles.json"))
    ap.add_argument("--summary-chars", type=int, default=140)
    ap.add_argument("--only-missing", action="store_true",
                    help="기존 파일에 없는 종목만 조회해 합친다(CI에서 매 실행 전체 재조회 방지)")
    args = ap.parse_args()

    import yfinance as yf

    items = json.loads(Path(args.universe).read_text(encoding="utf-8"))["items"]
    out: dict[str, dict] = {}
    out_path = Path(args.out)
    if args.only_missing and out_path.exists():
        out = json.loads(out_path.read_text(encoding="utf-8"))
        before = len(items)
        items = [it for it in items if it["symbol"] not in out]
        print(f"기존 프로필 {len(out)}종목 보유 - 유니버스 {before}종목 중 {len(items)}종목만 조회", flush=True)
    missing = 0
    for n, it in enumerate(items, 1):
        code, yfs = it["symbol"], it["yf_symbol"]
        rec = {}
        try:
            info = yf.Ticker(yfs).info
            if info.get("industry"):
                rec["industry"] = info["industry"]
            if info.get("sector"):
                rec["sector"] = info["sector"]
            s = (info.get("longBusinessSummary") or "").strip()
            if s:
                rec["summary"] = s[:args.summary_chars]
        except Exception:
            pass
        if rec:
            out[code] = rec
        else:
            missing += 1
        if n % 50 == 0:
            print(f"  {n}/{len(items)} (정보없음 {missing})", flush=True)
        time.sleep(0.15)

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장 {args.out}: {len(out)}종목 / 정보없음 {missing}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
