"""테마 매핑 근거(evidence)를 실제 사업정보와 대조해 지어낸 근거를 찾는다.

왜 필요한가 (2026-09-15):
프롬프트 v4까지는 한국 후보를 이름만으로 보여줘서, 모델이 사명의 형태로 사업을
추측하고 근거를 지어냈다(예: 레인보우로보틱스 "수술 로봇을 개발" -> 의료기기
direct). 이런 근거가 이미 승인돼 화면에 표시되고 있으므로, 새 매핑을 승인하기
전에 현재 승인분에 얼마나 섞여 있는지부터 재야 한다.

판정은 3분류다(CLAUDE.md 원칙 4 - 확인 불가를 오류로 치지 않는다):
  consistent    근거가 실제 사업정보와 부합
  contradicts   근거의 제품·사업이 실제 사업정보와 어긋남 (지어낸 근거 의심)
  unverifiable  사업정보가 없거나 요약만으로 판단 불가

DB에 쓰지 않는다. 결과는 표준출력과 out/evidence_audit_*.txt 로만 남긴다.

사용법:
    python scripts/audit_mapping_evidence.py --current-approved   # 화면에 표시 중인 매핑
    python scripts/audit_mapping_evidence.py --run-id 20260915...  # 특정 run 전체
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
    if run_id:
        rows = conn.execute(
            "SELECT theme_id, ticker, linkage, evidence FROM theme_members "
            "WHERE run_id = ? AND market = ? ORDER BY theme_id, ticker",
            (run_id, market),
        ).fetchall()
        return [dict(zip(("theme_id", "ticker", "linkage", "evidence"), r)) for r in rows]

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
            out.append(dict(zip(("theme_id", "ticker", "linkage", "evidence"), r)))
    return out


def judge(theme: dict, members: list[dict], names: dict, profiles: dict, api_key: str) -> dict[str, dict]:
    lines = []
    for m in members:
        prof = profiles.get(m["ticker"]) or {}
        info = " / ".join(x for x in (prof.get("industry"), prof.get("summary")) if x) or "(사업정보 없음)"
        lines.append(f"- {m['ticker']} {names.get(m['ticker'], '')}\n"
                     f"    근거: {m['evidence']}\n"
                     f"    실제 사업정보: {info}")
    prompt = f"""테마: {theme['name_ko']} ({theme['name_en']})
관련 키워드: {', '.join(theme.get('keywords_ko', []))}

아래 각 기업에 대해, 매핑 근거가 실제 사업정보와 부합하는지 판정하시오.

{chr(10).join(lines)}

판정 기준:
- consistent: 근거에 적힌 제품·사업이 실제 사업정보와 부합한다
- contradicts: 근거에 적힌 제품·사업이 실제 사업정보에 없거나 어긋난다
  (예: 실제로는 산업용 로봇 회사인데 근거가 "수술 로봇 개발")
- unverifiable: 사업정보가 없거나, 요약만으로는 부합 여부를 판단할 수 없다
사업정보가 없다는 이유만으로 contradicts로 판정하지 마시오.

반드시 아래 JSON으로만 답하시오:
{{"verdicts": [{{"ticker": "...", "verdict": "consistent|contradicts|unverifiable", "reason": "짧은 한국어 이유"}}]}}"""
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": "당신은 사실관계를 엄격히 대조하는 검증자입니다."},
                           {"role": "user", "content": prompt}],
              "temperature": 0.0, "max_tokens": 3000,
              "response_format": {"type": "json_object"}},
        timeout=120,
    )
    r.raise_for_status()
    parsed = json.loads(r.json()["choices"][0]["message"]["content"])
    return {str(v.get("ticker")): v for v in parsed.get("verdicts", [])}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--current-approved", action="store_true")
    g.add_argument("--run-id")
    ap.add_argument("--market", default="KR")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        return 1

    profiles = json.loads((ROOT / "data" / "kr_profiles.json").read_text(encoding="utf-8"))
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
    _log(f"대상: {scope} / {args.market} {len(rows)}건")

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
                results.append((m, {"verdict": "error", "reason": "판정 호출 실패"}))
            continue
        for m in members:
            results.append((m, v.get(m["ticker"], {"verdict": "missing", "reason": "응답에 없음"})))
        time.sleep(0.5)

    cnt = Counter(v["verdict"] for _, v in results)
    lines = [f"대상: {scope} / {args.market} {len(results)}건",
             "판정: " + " / ".join(f"{k} {cnt[k]}" for k in
                                   ("consistent", "contradicts", "unverifiable", "missing", "error") if cnt[k]),
             ""]
    lines.append("== contradicts (지어낸 근거 의심) ==")
    for m, v in results:
        if v["verdict"] == "contradicts":
            prof = profiles.get(m["ticker"]) or {}
            lines.append(f"  [{m['theme_id']}] {m['ticker']} {names.get(m['ticker'], '')} ({m['linkage']})")
            lines.append(f"      근거: {m['evidence']}")
            lines.append(f"      실제: {prof.get('industry', '-')} | {str(prof.get('summary', ''))[:100]}")
            lines.append(f"      판정이유: {v.get('reason', '')}")
    report = "\n".join(lines)

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    tag = "current" if args.current_approved else args.run_id
    (out_dir / f"evidence_audit_{tag}.txt").write_text(report, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
