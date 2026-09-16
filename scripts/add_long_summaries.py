"""data/kr_profiles.json 에 감사용 긴 사업요약(summary_long)을 추가한다.

왜 따로 두는가 (2026-09-15):
매핑 프롬프트는 청크당 200종목이라 요약을 140자로 잘라 쓴다(summary).
그런데 근거 감사(audit_mapping_evidence.py)에서 140자 요약은 지주사·복합기업의
부사업을 담지 못해 오판이 났다 - SK이노베이션을 "석유 정제사"로만 보고 배터리
테마를 모순 처리(실제로는 자회사 SK온이 배터리 대기업), 풍산을 "구리 제품"으로만
보고 방산을 모순 처리(탄약이 주력 사업 중 하나). 감사는 테마당 수십 종목만 보므로
긴 요약을 써도 비용이 작다. 매핑용 summary 필드는 건드리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 2026-09-16: 700 -> 2500. 700자에서 잘린 뒤쪽에 인용하려던 문구가 있어 감사의 "인용 검증
# 실패"가 무더기로 났다(누적 241건 중 77%가 실제로는 정상인 편입). 감사는 테마당 수십 종목만
# 보므로 길어도 비용이 작다 - 프롬프트에 넣을 때 다시 자른다(audit_mapping_evidence.INFO_CHARS).
LONG_CHARS = 2500
PREV_LONG_CHARS = 700  # 이 길이에 딱 맞으면 예전 상한에서 잘린 것으로 본다


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relengthen", action="store_true",
                     help="예전 상한(700자)에서 잘린 요약도 다시 받아 늘린다")
    args = ap.parse_args()

    import yfinance as yf

    path = ROOT / "data" / "kr_profiles.json"
    profiles = json.loads(path.read_text(encoding="utf-8"))
    items = json.loads((ROOT / "data" / "kr_universe.json").read_text(encoding="utf-8"))["items"]
    yf_sym = {i["symbol"]: i["yf_symbol"] for i in items}

    def needs(code: str) -> bool:
        cur = profiles[code].get("summary_long")
        if not cur:
            return True
        return args.relengthen and len(cur) >= PREV_LONG_CHARS

    todo = [c for c in profiles if c in yf_sym and needs(c)]
    print(f"summary_long 추가 대상 {len(todo)}종목", flush=True)
    got = 0
    for n, code in enumerate(todo, 1):
        try:
            s = (yf.Ticker(yf_sym[code]).info.get("longBusinessSummary") or "").strip()
            if s:
                profiles[code]["summary_long"] = s[:LONG_CHARS]
                got += 1
        except Exception:
            pass
        if n % 50 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
            path.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.15)

    path.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료: {got}/{len(todo)}종목에 summary_long 추가", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
