"""검토를 거친 두 매핑 결과를 합쳐 새 run을 만든다.

왜 필요한가 (2026-09-15):
LLM 매핑은 실행마다 결과가 흔들린다. 프롬프트 v5.1은 지어낸 근거를 크게 줄였지만,
같은 실행에서 LS ELECTRIC·HD현대일렉트릭(전력망), 한전KPS(원전), 엘앤에프(배터리)
같은 정당한 소속을 놓쳤다. 한 번의 실행으로는 정확도와 완전성을 동시에 잡지 못한다.

화면은 (theme_id, market)별로 "승인된 최신 run 하나"만 보여주므로 여러 run의 행을
섞어 승인할 수 없다. 그래서 다음을 합친 새 run을 만든다:
  기준 run의 행 - 검토에서 제외(exclude)하기로 한 행
  + 현재 화면에 표시 중인 승인분에서 되살리기(restore)로 한 행 (원래 근거 그대로 복사)

기존 행은 절대 수정·삭제하지 않는다(CLAUDE.md 원칙 5). 새 run의 행은 approved=0으로
들어가며, 승인은 approve_theme_mapping.py로 따로 한다. 예외는 unapprove 목록뿐이다 -
병합 run에 그 테마의 행이 하나도 없으면 화면이 예전 run으로 되돌아가므로, 검토에서
오류로 확정한 예전 행의 approved만 0으로 내린다(행 자체는 남는다).

사용법:
    python scripts/build_merged_mapping_run.py --review data/eval/v5_1_manual_review_20260915.json --dry-run
    python scripts/build_merged_mapping_run.py --review data/eval/v5_1_manual_review_20260915.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db  # noqa: E402
from src.db.theme_mapping import ensure_schema, finish_mapping_run, insert_theme_member, start_mapping_run  # noqa: E402

COLS = ("theme_id", "ticker", "market", "stage", "evidence", "linkage", "confidence", "flagged", "run_id")


def _log(msg: str) -> None:
    print(f"[merge] {msg}", flush=True)


def _as_bool(v) -> bool:
    """Turso HTTP 클라이언트는 INTEGER를 문자열로 돌려준다. bool("0")은 True라서
    그대로 쓰면 flagged가 전부 1로 뒤집힌다."""
    return str(v).strip().lower() in ("1", "true")


def latest_approved_run(conn, theme_id: str, market: str, before: str | None = None) -> str | None:
    sql = "SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1"
    args: list = [theme_id, market]
    if before:
        sql += " AND run_id < ?"
        args.append(before)
    row = conn.execute(sql, tuple(args)).fetchone()
    return row[0] if row and row[0] else None


def find_source_row(conn, theme_id: str, ticker: str, market: str, before: str) -> tuple | None:
    """되살릴 원본 행을 찾는다. 승인된 최신 행을 먼저 보고, 없으면 과거 아무 run에서나 찾는다.

    왜 승인분만 보면 안 되는가(2026-09-16): LLM 매핑은 실행마다 결과가 흔들려서, 사람이
    정상이라 확정한 소속도 어느 분기에 한 번 빠질 수 있다. 그 분기 병합 run에 행이 없으면
    다음 분기에는 "승인된 이력"이 사라져 영영 되살릴 수 없게 된다 - 한 번의 실행 편차가
    확정 소속을 영구히 지우는 셈이다. 그래서 승인 여부와 무관하게 과거 행에서 근거를 가져온다
    (판정 원장이 "이 소속은 사람이 확인했다"는 근거고, 여기서 찾는 건 근거 문장일 뿐이다).
    """
    src_run = latest_approved_run(conn, theme_id, market, before=before)
    if src_run:
        row = conn.execute(
            f"SELECT {', '.join(COLS)} FROM theme_members "
            "WHERE theme_id = ? AND ticker = ? AND market = ? AND run_id = ? AND approved = 1",
            (theme_id, ticker, market, src_run),
        ).fetchone()
        if row:
            return row
    return conn.execute(
        f"SELECT {', '.join(COLS)} FROM theme_members "
        "WHERE theme_id = ? AND ticker = ? AND market = ? AND run_id < ? "
        "ORDER BY run_id DESC LIMIT 1",
        (theme_id, ticker, market, before),
    ).fetchone()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", required=True)
    ap.add_argument("--market", default="KR")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    review = json.loads((ROOT / args.review).read_text(encoding="utf-8"))
    base = review["run_id"]
    exclude = {(t, c) for t, c, *_ in review.get("exclude", [])}
    restore = [(t, c) for t, c, *_ in review.get("restore", [])]
    unapprove = [(t, c) for t, c, *_ in review.get("unapprove", [])]

    conn = get_db()
    ensure_schema(conn)

    base_rows = [dict(zip(COLS, r)) for r in conn.execute(
        f"SELECT {', '.join(COLS)} FROM theme_members WHERE run_id = ? AND market = ?",
        (base, args.market),
    ).fetchall()]
    if not base_rows:
        _log(f"기준 run {base}에 {args.market} 행이 없다 - run_id 확인 필요")
        return 1

    missing_ex = [k for k in exclude if k not in {(r["theme_id"], r["ticker"]) for r in base_rows}]
    if missing_ex:
        _log(f"경고: exclude 중 기준 run에 없는 항목 {len(missing_ex)}건 {missing_ex[:5]} - 오타 확인")

    kept = [r for r in base_rows if (r["theme_id"], r["ticker"]) not in exclude]
    kept_keys = {(r["theme_id"], r["ticker"]) for r in kept}
    _log(f"기준 run {base}: {args.market} {len(base_rows)}행 - 제외 {len(base_rows) - len(kept)} = {len(kept)}행")

    # 되살리기: 기준 run보다 먼저 승인돼 현재 화면에 표시 중인 행에서 원래 근거를 그대로 가져온다.
    restored: list[dict] = []
    not_found: list[tuple[str, str]] = []
    for tid, code in restore:
        if (tid, code) in kept_keys:
            _log(f"  되살리기 불필요(이미 유지됨): {tid} {code}")
            continue
        row = find_source_row(conn, tid, code, args.market, base)
        if not row:
            not_found.append((tid, code))
            continue
        src = dict(zip(COLS, row))
        from_unapproved = src["run_id"] != latest_approved_run(conn, tid, args.market, before=base)
        if from_unapproved:
            _log(f"  되살리기(승인 이력 없음, run {src['run_id']}에서 근거 복사): {tid} {code}")
        restored.append(src)
    if not_found:
        _log(f"경고: 되살릴 원본을 어느 run에서도 못 찾음 {len(not_found)}건 {not_found} - 병합에서 빠진다")
    _log(f"되살리기 {len(restored)}행")

    final = kept + restored
    by_theme: dict[str, int] = defaultdict(int)
    for r in final:
        by_theme[r["theme_id"]] += 1

    # 병합 run에 행이 없는 테마는 화면이 예전 run으로 되돌아간다 - 보이게 알린다.
    themes_with_old = {r[0] for r in conn.execute(
        "SELECT DISTINCT theme_id FROM theme_members WHERE market = ? AND approved = 1", (args.market,)
    ).fetchall()}
    fallback = sorted(t for t in themes_with_old if by_theme.get(t, 0) == 0)
    if fallback:
        _log(f"주의: 병합 run에 행이 없어 예전 승인분이 계속 표시될 테마 {fallback}")

    for tid in sorted(by_theme):
        _log(f"  {tid:24s} {by_theme[tid]}")

    run_id = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-merge"
    stats = {"base_run": base, "base_rows": len(base_rows), "excluded": len(base_rows) - len(kept),
             "restored": len(restored), "restore_not_found": not_found, "final_rows": len(final),
             "review_file": args.review, "unapprove": unapprove, "fallback_themes": fallback}
    if args.dry_run:
        _log(f"[dry-run] 새 run {run_id} 에 {len(final)}행을 쓸 예정 - 쓰지 않음")
        _log(json.dumps(stats, ensure_ascii=False))
        conn.close()
        return 0

    now = datetime.utcnow().isoformat()
    start_mapping_run(conn, run_id, now, "merge", f"merge base={base} review={args.review}")
    for r in final:
        insert_theme_member(conn, r["theme_id"], r["ticker"], r["market"], r["stage"], r["evidence"],
                            r["linkage"], r["confidence"] or "normal", _as_bool(r["flagged"]), run_id, now)
    conn.commit()

    for tid, code in unapprove:
        cur = conn.execute(
            "UPDATE theme_members SET approved = 0 WHERE theme_id = ? AND ticker = ? AND market = ? AND approved = 1",
            (tid, code, args.market),
        )
        _log(f"승인 해제 {tid} {code}: {cur.rowcount if hasattr(cur, 'rowcount') else '?'}행")
    conn.commit()

    finish_mapping_run(conn, run_id, datetime.utcnow().isoformat(), stats)
    written = conn.execute("SELECT COUNT(*) FROM theme_members WHERE run_id = ?", (run_id,)).fetchone()[0]
    _log(f"병합 run 생성 완료 run_id={run_id} / 기록 {int(written)}행 (approved=0 - 승인은 별도)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
