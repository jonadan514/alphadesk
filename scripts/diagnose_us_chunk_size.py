"""미국 매핑에서 사업정보를 붙인 뒤에도 명백한 기업이 빠지는 원인을 가린다 (진단용, DB 미기록).

배경(2026-09-15): 프롬프트 v7에서 미국 후보에 사업정보(400자)를 붙였더니 전체 편입은
120 -> 160행으로 늘었지만, Huntington Ingalls(미 해군 조선사, 요약 첫 문장이 "military
ships")가 조선 테마에서 여전히 0건, 의료기기는 19 -> 6행으로 줄었다. 한 청크가 200종목
x 약 110토큰 = 2만 토큰을 넘으면서 gpt-4o-mini가 긴 목록 중간을 놓친다는 가설.

변형 (모두 운영 코드 path_a_universe_constrained를 그대로 호출, 1회 실행):
  200 / 이름만    - v6 방식
  200 / 사업정보  - v7 방식
  100 / 사업정보
   50 / 사업정보

정답: 사람이 확인한 누락(TARGETS) + 판정 원장의 keep. 오답: 판정 원장의 exclude.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.map_theme_companies as mtc  # noqa: E402

# 사업정보로 확인한 v6 누락 (2026-09-15 검토)
TARGETS = {
    "shipbuilding": {"HII", "GD"},
    "infra_construction": {"PWR", "EME", "J"},
    "semi_equipment": {"TER", "Q", "AMAT", "LRCX", "KLAC"},
    "datacenter_power": {"ETN", "VRT"},
    "renewable_energy": {"FSLR"},
    "medical_device": {"JNJ", "ABT", "MDT", "SYK", "BSX", "ISRG"},
    "construction_machinery": {"DE", "CAT"},
}
VARIANTS = [(200, False), (200, True), (100, True), (50, True)]


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY 미설정")
        return 1
    themes = {t["id"]: t for t in mtc.load_themes(list(TARGETS))}
    universe, names = mtc.build_universe_and_names()
    universe = [it for it in universe if it["market"] == "US"]
    valid = {it["symbol"] for it in universe}
    profiles = mtc.load_all_profiles()
    ledger = [r for r in json.loads((ROOT / "data/eval/mapping_decisions.json").read_text(encoding="utf-8"))["decisions"]
              if r["market"] == "US"]

    def run(tid: str, size: int, with_prof: bool) -> tuple[str, int, bool, set[str]]:
        # 청크 크기는 모듈 상수를 읽으므로 스레드마다 바꿀 수 없다 - 크기별로 순차 실행한다.
        raw = mtc.path_a_universe_constrained(themes[tid], universe, names, api_key,
                                              profiles if with_prof else {})
        return tid, size, with_prof, {mtc._norm_ticker(m) for m in raw} & valid

    results = []
    for size in sorted({s for s, _ in VARIANTS}, reverse=True):
        mtc.UNIVERSE_CHUNK_SIZE = size
        jobs = [(tid, s, p) for tid in TARGETS for s, p in VARIANTS if s == size]
        with ThreadPoolExecutor(max_workers=1) as ex:
            results += list(ex.map(lambda j: run(*j), jobs))

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n" + "=" * 70)
    for tid in TARGETS:
        good = TARGETS[tid] | {r["ticker"] for r in ledger if r["theme_id"] == tid and r["decision"] == "keep"}
        bad = {r["ticker"] for r in ledger if r["theme_id"] == tid and r["decision"] == "exclude"}
        print(f"\n[{tid}] 정답 {sorted(good)} / 알려진 오답 {sorted(bad)}")
        for t, size, with_prof, got in sorted(results, key=lambda x: (-x[1], x[2])):
            if t != tid:
                continue
            label = f"{size:3d}/{'사업정보' if with_prof else '이름만  '}"
            print(f"  {label} 편입 {len(got):2d} / 정답 {len(got & good)}/{len(good)} "
                  f"/ 알려진 오답 {len(got & bad)} | 놓침 {sorted(good - got)} | 편입 {sorted(got)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
