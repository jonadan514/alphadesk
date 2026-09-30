"""data/kr_profiles.json의 기존 값에 필드별 출처(<필드>_source)를 채운다 (작업지시서 Phase 8).

값은 바꾸지 않고 출처만 덧붙인다. 여러 번 돌려도 결과가 같다(이미 있는 출처는 그대로).

Usage:
  python scripts/backfill_profile_sources.py --dry-run
  python scripts/backfill_profile_sources.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from collectors.kr_profiles import FIELD_SOURCE_KEYS, backfill_field_sources

PROFILES = ROOT / "data" / "kr_profiles.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    out, changed = {}, 0
    tally = {k: Counter() for k in FIELD_SOURCE_KEYS}
    for code, rec in profiles.items():
        new = backfill_field_sources(rec)
        # 값은 그대로여야 한다 - 출처 키만 늘어난 것이어야 한다
        assert {k: v for k, v in new.items() if not k.endswith("_source")} == \
               {k: v for k, v in rec.items() if not k.endswith("_source")}, f"{code}: 값이 바뀌었다"
        if new != rec:
            changed += 1
        out[code] = new
        for k in FIELD_SOURCE_KEYS:
            if new.get(f"{k}_source"):
                tally[k][new[f"{k}_source"]] += 1

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"종목 {len(profiles)}개 중 출처를 채운 것 {changed}개")
    for k in FIELD_SOURCE_KEYS:
        print(f"  {k}_source: {dict(tally[k])}")
    if not args.dry_run:
        PROFILES.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
