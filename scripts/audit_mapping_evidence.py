"""테마 매핑을 실제 사업정보와 대조해 틀린 편입을 찾는다.

왜 필요한가 (2026-09-15):
프롬프트 v4까지는 한국 후보를 이름만으로 보여줘서, 모델이 사명의 형태로 사업을
추측하고 근거를 지어냈다(예: 레인보우로보틱스 "수술 로봇을 개발" -> 의료기기
direct). 이런 편입이 이미 승인돼 화면에 표시되고 있으므로, 새 매핑을 승인하기
전에 현재 승인분에 얼마나 섞여 있는지부터 잰다.

두 축으로 판정한다. 한 축만 보면 사각지대가 생긴다 - v1은 근거의 사실 여부만
물어서, 근거는 사실인데 테마에 안 맞는 편입(HMM "컨테이너선 운영" -> 조선)을
"부합"으로 통과시켰다.
  evidence : consistent / contradicts / unverifiable  - 근거가 사실인가
  fit      : fits / not_fits / unclear                - 이 회사가 이 테마에 속하나
틀린 편입 = evidence가 contradicts 이거나 fit이 not_fits.
unverifiable·unclear는 오류로 치지 않는다(CLAUDE.md 원칙 4).

사업정보는 summary_long(700자)을 우선 쓴다. 140자 요약으로는 지주사·복합기업의
부사업이 안 보여 오판이 났다(SK이노베이션을 정유사로만 보고 배터리 편입을 모순
처리 - 실제로는 자회사 SK온이 배터리 대기업).

DB에 쓰지 않는다. 결과는 표준출력과 out/evidence_audit_*.txt 로만 남긴다.

사용법:
    python scripts/audit_mapping_evidence.py --current-approved
    python scripts/audit_mapping_evidence.py --run-id 20260915...
    python scripts/audit_mapping_evidence.py --current-approved --eval data/eval/evidence_audit_labels_20260915.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db  # noqa: E402

MODEL = "gpt-4o-mini"


def _log(msg: str) -> None:
    print(f"[audit] {msg}", flush=True)


def load_rows(conn, market: str, run_id: str | None) -> list[dict]:
    cols = ("theme_id", "ticker", "linkage", "evidence")
    if run_id:
        rows = conn.execute(
            "SELECT theme_id, ticker, linkage, evidence FROM theme_members "
            "WHERE run_id = ? AND market = ? ORDER BY theme_id, ticker",
            (run_id, market),
        ).fetchall()
        return [dict(zip(cols, r)) for r in rows]

    # 화면이 쓰는 규칙과 동일: (theme_id, market)별 승인된 최신 run 하나.
    themes = [r[0] for r in conn.execute(
        "SELECT DISTINCT theme_id FROM theme_members WHERE market = ? AND approved = 1", (market,)
    ).fetchall()]
    out: list[dict] = []
    for tid in themes:
        latest = conn.execute(
            "SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1",
            (tid, market),
        ).fetchone()[0]
        for r in conn.execute(
            "SELECT theme_id, ticker, linkage, evidence FROM theme_members "
            "WHERE theme_id = ? AND market = ? AND run_id = ? AND approved = 1 ORDER BY ticker",
            (tid, market, latest),
        ).fetchall():
            out.append(dict(zip(cols, r)))
    return out


def _business_info(prof: dict) -> str:
    summary = prof.get("summary_long") or prof.get("summary")
    parts = [x for x in (prof.get("industry"), summary) if x]
    return " / ".join(parts) if parts else "(사업정보 없음)"


def judge(theme: dict, members: list[dict], names: dict, profiles: dict, api_key: str) -> dict[str, dict]:
    lines = []
    for m in members:
        lines.append(f"- {m['ticker']} {names.get(m['ticker'], '')}\n"
                     f"    근거: {m['evidence']}\n"
                     f"    실제 사업정보: {_business_info(profiles.get(m['ticker']) or {})}")
    prompt = f"""테마: {theme['name_ko']} ({theme['name_en']})
관련 키워드: {', '.join(theme.get('keywords_ko', []))}

아래 각 기업을 두 가지 기준으로 따로 판정하시오.

{chr(10).join(lines)}

[evidence] 근거가 사실인가
- consistent: 근거에 적힌 제품·사업이 실제 사업정보와 부합한다
- contradicts: 근거에 적힌 제품·사업이 실제 사업정보에 없거나 어긋난다
  (예: 실제로는 산업용 로봇 회사인데 근거가 "수술 로봇 개발")
  근거의 주어가 이 기업이 아니라 다른 회사면 contradicts다.
- unverifiable: 사업정보가 없거나 부합 여부를 판단할 수 없다
  사업정보가 없다는 이유만으로 contradicts로 판정하지 마시오.
  지주사·복합기업은 자회사·부문 사업도 그 기업의 사업으로 인정하시오.

[fit] 이 기업이 테마에 속하는가 (근거가 사실이어도 테마와 무관할 수 있다)
- fits: 이 테마에서 매출이나 사업이 의미 있게 발생한다
- not_fits: 인접 산업일 뿐 이 테마에 속하지 않는다
  (예: 해운사는 선박을 운영할 뿐 조선 테마가 아니다)
- unclear: 판단할 정보가 부족하다

반드시 아래 JSON으로만 답하시오:
{{"verdicts": [{{"ticker": "...", "evidence": "consistent|contradicts|unverifiable", "fit": "fits|not_fits|unclear", "reason": "짧은 한국어 이유"}}]}}"""
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": "당신은 사실관계와 산업 분류를 엄격히 대조하는 검증자입니다."},
                           {"role": "user", "content": prompt}],
              "temperature": 0.0, "max_tokens": 4000,
              "response_format": {"type": "json_object"}},
        timeout=180,
    )
    r.raise_for_status()
    parsed = json.loads(r.json()["choices"][0]["message"]["content"])
    return {str(v.get("ticker")): v for v in parsed.get("verdicts", [])}


def is_error(v: dict) -> bool:
    return v.get("evidence") == "contradicts" or v.get("fit") == "not_fits"


def evaluate(results: list[tuple[dict, dict]], labels_path: Path) -> list[str]:
    labels = json.loads(labels_path.read_text(encoding="utf-8"))["labels"]
    got = {(m["theme_id"], m["ticker"]): v for m, v in results}
    tp = fp = fn = tn = skipped = absent = 0
    miss: list[str] = []
    false_alarm: list[str] = []
    for lb in labels:
        key = (lb["theme_id"], lb["ticker"])
        if lb.get("debatable"):
            skipped += 1
            continue
        if key not in got:
            absent += 1
            continue
        pred = is_error(got[key])
        if lb["error"] and pred:
            tp += 1
        elif lb["error"] and not pred:
            fn += 1
            miss.append(f"    놓침 {key[0]} {key[1]} - {lb['note']}")
        elif not lb["error"] and pred:
            fp += 1
            false_alarm.append(f"    오탐 {key[0]} {key[1]} - {lb['note']}")
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    out = ["", f"== 정답지 대비 ({labels_path.name}) ==",
           f"  TP {tp} / FP {fp} / FN {fn} / TN {tn}  (판단보류 제외 {skipped}, 대상에 없음 {absent})",
           f"  정밀도 {prec:.0%} / 재현율 {rec:.0%}"]
    return out + miss + false_alarm


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--current-approved", action="store_true")
    g.add_argument("--run-id")
    ap.add_argument("--market", default="KR")
    ap.add_argument("--eval", default=None, help="정답지 JSON 경로")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        return 1

    profiles = json.loads((ROOT / "data" / "kr_profiles.json").read_text(encoding="utf-8"))
    long_cov = sum(1 for p in profiles.values() if p.get("summary_long"))
    names: dict[str, str] = {}
    uni = ROOT / "data" / "kr_universe.json"
    if uni.exists():
        names = {i["symbol"]: i["name"] for i in json.loads(uni.read_text(encoding="utf-8"))["items"]}
    from src.collectors.kr_kospi_list import KOSPI_STOCKS
    for c, n, _ in KOSPI_STOCKS:
        names.setdefault(c, n)

    themes = {t["id"]: t for t in yaml.safe_load((ROOT / "config" / "themes.yaml").read_text(encoding="utf-8"))["themes"]}

    conn = get_db()
    rows = load_rows(conn, args.market, None if args.current_approved else args.run_id)
    conn.close()
    scope = "현재 승인분" if args.current_approved else f"run {args.run_id}"
    _log(f"대상: {scope} / {args.market} {len(rows)}건 / 긴 사업요약 보유 {long_cov}종목")

    by_theme: dict[str, list[dict]] = {}
    for r in rows:
        by_theme.setdefault(r["theme_id"], []).append(r)

    results: list[tuple[dict, dict]] = []
    for tid, members in sorted(by_theme.items()):
        if tid not in themes:
            continue
        try:
            v = judge(themes[tid], members, names, profiles, api_key)
        except Exception as e:
            _log(f"{tid}: 판정 실패 {type(e).__name__}: {str(e)[:120]}")
            for m in members:
                results.append((m, {"evidence": "error", "fit": "error", "reason": "판정 호출 실패"}))
            continue
        for m in members:
            results.append((m, v.get(m["ticker"], {"evidence": "missing", "fit": "missing", "reason": "응답에 없음"})))
        time.sleep(0.5)

    ev = Counter(v.get("evidence") for _, v in results)
    fit = Counter(v.get("fit") for _, v in results)
    errors = [(m, v) for m, v in results if is_error(v)]
    lines = [f"대상: {scope} / {args.market} {len(results)}건",
             "근거: " + " / ".join(f"{k} {ev[k]}" for k in ("consistent", "contradicts", "unverifiable", "missing", "error") if ev[k]),
             "테마적합: " + " / ".join(f"{k} {fit[k]}" for k in ("fits", "not_fits", "unclear", "missing", "error") if fit[k]),
             f"틀린 편입(근거 모순 또는 테마 부적합): {len(errors)}건 ({len(errors) / max(len(results), 1):.0%})",
             ""]
    lines.append("== 틀린 편입 ==")
    for m, v in errors:
        prof = profiles.get(m["ticker"]) or {}
        lines.append(f"  [{m['theme_id']}] {m['ticker']} {names.get(m['ticker'], '')} ({m['linkage']}) "
                     f"evidence={v.get('evidence')} fit={v.get('fit')}")
        lines.append(f"      근거: {m['evidence']}")
        lines.append(f"      실제: {prof.get('industry', '-')} | {str(prof.get('summary', ''))[:90]}")
        lines.append(f"      판정이유: {v.get('reason', '')}")

    if args.eval:
        lines += evaluate(results, ROOT / args.eval)

    report = "\n".join(lines)
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    tag = "current" if args.current_approved else args.run_id
    (out_dir / f"evidence_audit_{tag}.txt").write_text(report, encoding="utf-8")
    # 다음 단계(승인 제외 목록 생성)가 쓸 수 있게 기계 판독용으로도 남긴다.
    (out_dir / f"evidence_audit_{tag}.json").write_text(json.dumps(
        [{"theme_id": m["theme_id"], "ticker": m["ticker"], **v} for m, v in results],
        ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
