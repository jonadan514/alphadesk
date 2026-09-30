"""매핑 모델을 바꾸면 결과가 얼마나 좋아지는지 잰다 (진단용, DB 미기록).

배경(2026-09-16): 프롬프트·청크 크기·사업정보 첨부는 모두 실측으로 조정했는데 모델만
한 번도 바꿔보지 않았다(gpt-4o-mini 고정). 분기 1회 매핑 비용이 0.5달러 수준이라
상위 모델로 올려도 몇 달러다 - 효과가 있으면 가장 싼 개선이다.

재는 방법: 운영 코드(path_a_universe_constrained)를 모델만 바꿔 그대로 호출하고,
  정답  = 사업정보로 확인한 누락(TARGETS) + 판정 원장의 keep
  오답  = 판정 원장의 exclude
에 얼마나 맞히는지 본다. 같은 조건에서 모델만 다르게 한다.

Usage:
  python scripts/diagnose_mapping_model.py                    # 사용 가능한 후보 모델 자동 선택
  python scripts/diagnose_mapping_model.py --models gpt-4o-mini gpt-4.1-mini
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.map_theme_companies as mtc  # noqa: E402

# 사업정보로 확인한 v6 누락 (2026-09-15 검토)
TARGETS = {
    "shipbuilding": {"HII", "GD"},
    "infra_construction": {"PWR", "EME", "J"},
    "semi_equipment": {"TER", "Q", "AMAT", "LRCX", "KLAC"},
    "medical_device": {"JNJ", "ABT", "MDT", "SYK", "BSX", "ISRG"},
    "construction_machinery": {"DE", "CAT"},
}
# 앞에서부터 쓸 수 있는 것을 고른다(키에 권한이 없는 모델은 건너뛴다).
CANDIDATES = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o", "gpt-4.1", "o4-mini", "gpt-5-mini"]


def _log(m: str) -> None:
    print(f"[model] {m}", flush=True)


def available_models(api_key: str) -> set[str]:
    try:
        r = requests.get("https://api.openai.com/v1/models",
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
        r.raise_for_status()
        return {m["id"] for m in r.json().get("data", [])}
    except Exception as e:
        _log(f"모델 목록 조회 실패({type(e).__name__}) - 후보를 그대로 시도한다")
        return set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--themes", nargs="*", default=None)
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        return 1

    have = available_models(api_key)
    models = args.models or [m for m in CANDIDATES if not have or m in have]
    if len(models) < 2:
        _log(f"비교할 모델이 부족하다: {models} (키가 쓸 수 있는 모델 {len(have)}개)")
        return 1
    _log(f"비교 모델: {models}")

    theme_ids = args.themes or list(TARGETS)
    themes = {t["id"]: t for t in mtc.load_themes(theme_ids)}
    universe, names = mtc.build_universe_and_names()
    universe = [it for it in universe if it["market"] == "US"]
    valid = {it["symbol"] for it in universe}
    profiles = mtc.load_all_profiles()
    ledger = [r for r in json.loads((ROOT / "data/eval/mapping_decisions.json").read_text(encoding="utf-8"))["decisions"]
              if r["market"] == "US"]

    picks: dict[tuple[str, str], set[str]] = {}
    elapsed: dict[str, float] = {}
    for model in models:
        mtc.MODEL_OVERRIDE = model
        t0 = time.time()
        for tid in theme_ids:
            try:
                raw = mtc.path_a_universe_constrained(themes[tid], universe, names, api_key, profiles)
                picks[(model, tid)] = {mtc._norm_ticker(m) for m in raw} & valid
            except Exception as e:
                _log(f"{model}/{tid} 실패: {type(e).__name__}: {str(e)[:100]}")
                picks[(model, tid)] = set()
        elapsed[model] = time.time() - t0
        _log(f"{model} 완료 - {elapsed[model]:.0f}초, 호출 실패 누적 {mtc.CALL_FAILURES}회")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n" + "=" * 72)
    total = {m: [0, 0, 0, 0] for m in models}  # 정답적중, 정답수, 오답편입, 총편입
    for tid in theme_ids:
        good = TARGETS.get(tid, set()) | {r["ticker"] for r in ledger
                                          if r["theme_id"] == tid and r["decision"] == "keep"}
        bad = {r["ticker"] for r in ledger if r["theme_id"] == tid and r["decision"] == "exclude"}
        print(f"\n[{tid}] 정답 {len(good)}개 / 알려진 오답 {len(bad)}개")
        for m in models:
            got = picks[(m, tid)]
            hit, wrong = got & good, got & bad
            total[m][0] += len(hit); total[m][1] += len(good)
            total[m][2] += len(wrong); total[m][3] += len(got)
            print(f"  {m:16s} 편입 {len(got):2d} / 정답 {len(hit)}/{len(good)} / 오답 {len(wrong)}"
                  f" | 놓침 {sorted(good - got)}")
    print("\n" + "=" * 72)
    print(f"{'모델':16s} {'정답적중':>10s} {'알려진 오답':>12s} {'총 편입':>8s} {'시간(초)':>9s}")
    for m in models:
        h, g, w, t = total[m]
        print(f"{m:16s} {h:5d}/{g:<4d} {w:12d} {t:8d} {elapsed[m]:9.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
