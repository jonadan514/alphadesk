"""새 매핑 run에 판정 원장을 적용해 검토 초안을 만든다.

build_decision_ledger.py가 모은 사람 판정을 새 run의 감사 결과와 맞춰 본다:
  - 원장에서 exclude인 행이 또 나왔다          -> 초안 exclude에 자동 기입
  - 원장에서 keep/hold인 행이 이번 run에서 빠졌다 -> 초안 restore에 자동 기입(기본 복원)
  - 원장에 없는데 감사가 걸렀다(또는 판정 누락)   -> needs_review: 사람이 볼 것은 이것뿐
  - 원장에서 keep/hold인데 감사가 걸렀다        -> 넘긴다(감사 편차로 이미 확인한 것)

복원은 빼는 방식이다(2026-09-16 변경). 전에는 사람이 복원 목록을 보고 넣을 것을 골랐는데,
LLM 매핑은 실행마다 결과가 흔들려서 멀쩡한 소속이 매 분기 무작위로 빠진다(같은 프롬프트로
돌린 두 run의 일치율 83%). 한 번 사람이 확인한 소속은 기본으로 되살리고, 사업이 바뀌어
더 이상 맞지 않는 것만 사람이 restore에서 지운다.

초안은 build_merged_mapping_run.py가 읽는 검토 파일 형식 그대로다. 사람은
needs_review만 판단해 exclude/keep에 옮기고 data/eval/에 저장한 뒤 병합한다.
그 파일을 build_decision_ledger.py의 REVIEW_FILES에 추가하면 다음 분기부터 재사용된다.

판정 유효기간: 회사 사업은 바뀐다(예: 매각·신사업). TTL_DAYS가 지난 판정은 쓰지 않고
needs_review로 되돌린다.

restore는 이번 run에 행이 하나라도 있는 테마로 한정한다. --theme-id로 일부 테마만
돌린 run에 다른 테마 행을 되살리면, 병합 run에 그 테마가 되살린 행만으로 생겨
화면이 그 몇 줄로 바뀐다.

사용법:
    python scripts/apply_decision_ledger.py --run-id 20260915070022-760a79 --market US \
        --audit out/evidence_audit_20260915070022-760a79_US.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_mapping_evidence import is_error  # noqa: E402

LEDGER = ROOT / "data" / "eval" / "mapping_decisions.json"
TTL_DAYS = 400    # 4분기 + 여유. 분기 run이 조금 늦어져도 직전 4개 분기 판정은 쓰이게.
STALE_DAYS = 300  # 만료는 아니지만 "사업이 바뀌었을 수 있다"고 표시할 나이


def needs_look(v: dict) -> bool:
    """감사가 틀린 편입으로 봤거나, 판정 자체가 없어서 확인이 필요한 행."""
    return is_error(v) or v.get("evidence") in ("missing", "error")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--market", required=True, choices=["KR", "US"])
    ap.add_argument("--audit", required=True, help="audit_mapping_evidence.py의 json 결과")
    ap.add_argument("--today", default=None, help="유효기간 계산 기준일 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--out-dir", default="out")
    args = ap.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    audit = json.loads((ROOT / args.audit).read_text(encoding="utf-8"))
    ledger_rows = json.loads(LEDGER.read_text(encoding="utf-8"))["decisions"]

    expired = 0
    ledger: dict[tuple[str, str], dict] = {}
    for r in ledger_rows:
        if r["market"] != args.market:
            continue
        age = (today - datetime.strptime(r["decided_at"], "%Y-%m-%d").date()).days
        if age > TTL_DAYS:
            expired += 1
            continue
        ledger[(r["theme_id"], r["ticker"])] = r

    run_keys = {(v["theme_id"], v["ticker"]) for v in audit}
    run_themes = {t for t, _ in run_keys}

    exclude, needs_review, hold_seen = [], [], []
    flagged_excluded = flagged_kept = 0
    for v in audit:
        key = (v["theme_id"], v["ticker"])
        dec = ledger.get(key)
        if dec and dec["decision"] == "exclude":
            exclude.append([*key, f"이전 판정({dec['decided_at']}): {dec['reason']}"])
            flagged_excluded += needs_look(v)
        elif dec:
            flagged_kept += needs_look(v)
            if dec["decision"] == "hold":
                hold_seen.append([*key, dec["reason"]])
        elif needs_look(v):
            needs_review.append([*key, f"감사 evidence={v.get('evidence')} fit={v.get('fit')}: "
                                       f"{v.get('reason', '')}"])

    # 확정 소속 복원: keep과 hold(판단보류로 유지했던 것) 모두 기본 복원 대상이다.
    # 오래된 판정은 사업이 바뀌었을 수 있으니 눈에 띄게 표시한다(만료는 TTL_DAYS에서 이미 걸러짐).
    restore, stale = [], []
    for key, dec in sorted(ledger.items()):
        if key in run_keys or key[0] not in run_themes:
            continue
        if dec["decision"] not in ("keep", "hold"):
            continue
        age = (today - datetime.strptime(dec["decided_at"], "%Y-%m-%d").date()).days
        tag = "판단보류였음" if dec["decision"] == "hold" else "정상 편입"
        note = f"이전 판정({dec['decided_at']}) {tag}인데 이번 run에서 빠짐: {dec['reason']}"
        if age >= STALE_DAYS:
            note = f"[판정 {age}일 지남 - 사업 변화 확인] " + note
            stale.append([*key, dec["reason"]])
        restore.append([*key, note])

    flagged = sum(1 for v in audit if needs_look(v))
    summary = [
        f"{args.market} {len(audit)}행 / 감사 적발 {flagged}건",
        f"  이전 판정으로 자동 처리 {flagged_excluded + flagged_kept}건"
        f" (제외 {flagged_excluded} / 감사 편차로 유지 {flagged_kept})",
        f"  사람 검토 필요 {len(needs_review)}건",
        f"자동 제외 {len(exclude)}건(감사 통과분 포함) / 자동 복원 {len(restore)}건"
        + (f" - 그중 오래된 판정 {len(stale)}건 확인 필요" if stale else "")
        + (f" / 만료 판정 {expired}건 미사용" if expired else ""),
    ]

    draft = {
        "_about": (f"apply_decision_ledger.py 자동 초안 ({today}). 사람이 할 일은 두 가지다: "
                   "(1) needs_review를 판단해 exclude/keep으로 옮긴다. "
                   "(2) restore는 이미 확정된 소속이라 기본으로 되살아난다 - 사업이 바뀌어 "
                   "더는 맞지 않는 것만 지운다(특히 '판정 N일 지남' 표시가 붙은 행). "
                   "그 뒤 data/eval/에 저장하고 build-merged로 병합."),
        "run_id": args.run_id,
        "market": args.market,
        "summary": summary,
        "needs_review": needs_review,
        "exclude": exclude,
        "keep": [],
        "restore": restore,
        "info_hold_in_run": hold_seen,
        "info_restore_stale": stale,
    }
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(exist_ok=True)
    stem = f"review_draft_{args.run_id}_{args.market}"
    (out_dir / f"{stem}.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    lines = summary + ["", "== 사람 검토 필요 =="] + [f"  [{t}] {c} {r}" for t, c, r in needs_review]
    lines += ["", "== 자동 제외 =="] + [f"  [{t}] {c} {r}" for t, c, r in exclude]
    lines += ["", "== 자동 복원 (빼려면 restore에서 지운다) =="] + [f"  [{t}] {c} {r}" for t, c, r in restore]
    if stale:
        lines += ["", "== 그중 판정이 오래된 것 - 사업 변화 확인 =="]
        lines += [f"  [{t}] {c} {r}" for t, c, r in stale]
    (out_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
