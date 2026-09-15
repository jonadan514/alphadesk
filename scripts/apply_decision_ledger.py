"""새 매핑 run에 판정 원장을 적용해 검토 초안을 만든다.

build_decision_ledger.py가 모은 사람 판정을 새 run의 감사 결과와 맞춰 본다:
  - 원장에서 exclude인 행이 또 나왔다       -> 초안 exclude에 자동 기입
  - 원장에서 keep인 행이 이번 run에서 빠졌다 -> 초안 restore에 자동 기입
  - 원장에 없는데 감사가 걸렀다(또는 판정 누락) -> needs_review: 사람이 볼 것은 이것뿐
  - 원장에서 keep/hold인데 감사가 걸렀다     -> 넘긴다(감사 편차로 이미 확인한 것)

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
TTL_DAYS = 400  # 4분기 + 여유. 분기 run이 조금 늦어져도 직전 4개 분기 판정은 쓰이게.


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

    restore, dropped_holds = [], []
    for key, dec in sorted(ledger.items()):
        if key in run_keys or key[0] not in run_themes:
            continue
        if dec["decision"] == "keep":
            restore.append([*key, f"이전 판정({dec['decided_at']}) 정상 편입인데 이번 run에서 빠짐: {dec['reason']}"])
        elif dec["decision"] == "hold":
            dropped_holds.append([*key, dec["reason"]])

    flagged = sum(1 for v in audit if needs_look(v))
    summary = [
        f"{args.market} {len(audit)}행 / 감사 적발 {flagged}건",
        f"  이전 판정으로 자동 처리 {flagged_excluded + flagged_kept}건"
        f" (제외 {flagged_excluded} / 감사 편차로 유지 {flagged_kept})",
        f"  사람 검토 필요 {len(needs_review)}건",
        f"자동 제외 {len(exclude)}건(감사 통과분 포함) / 복원 초안 {len(restore)}건"
        + (f" / 만료 판정 {expired}건 미사용" if expired else ""),
    ]

    draft = {
        "_about": (f"apply_decision_ledger.py 자동 초안 ({today}). needs_review만 판단해 exclude/keep으로 "
                   "옮긴 뒤 data/eval/에 저장하고 build-merged로 병합. restore는 이전 승인분에 원본이 "
                   "있어야 복원된다(없으면 병합 로그에 경고)."),
        "run_id": args.run_id,
        "market": args.market,
        "summary": summary,
        "needs_review": needs_review,
        "exclude": exclude,
        "keep": [],
        "restore": restore,
        "info_hold_in_run": hold_seen,
        "info_hold_dropped": dropped_holds,
    }
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(exist_ok=True)
    stem = f"review_draft_{args.run_id}_{args.market}"
    (out_dir / f"{stem}.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    lines = summary + ["", "== 사람 검토 필요 =="] + [f"  [{t}] {c} {r}" for t, c, r in needs_review]
    lines += ["", "== 자동 제외 =="] + [f"  [{t}] {c} {r}" for t, c, r in exclude]
    lines += ["", "== 복원 초안 =="] + [f"  [{t}] {c} {r}" for t, c, r in restore]
    if dropped_holds:
        lines += ["", "== 참고: 판단보류였는데 이번에 빠진 것(복원하지 않음) =="]
        lines += [f"  [{t}] {c} {r}" for t, c, r in dropped_holds]
    (out_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
