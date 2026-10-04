"""테마 ETF 구성종목과 현재 승인된 소속을 비교해 "시장 인식(perceived)" 후보를 낸다.

SPEC_theme_company_mapping.md 11장. 입력은 fetch_kr_theme_etf_holdings.py의 JSON.
출력은 사람이 보는 보고서 + 검토 파일 `add`에 그대로 붙일 수 있는 항목이다.
이 스크립트는 DB를 읽기만 한다 - 편입은 검토 파일 -> Build Merged Mapping Run -> 승인 절차로만.

    python scripts/report_perception_candidates.py --holdings data/kr_theme_etf_holdings.json

출력:
  - 후보(add): 테마 ETF에 MIN_WEIGHT 이상 들어 있고, 유니버스 안이며, 그 테마의 현재 소속이 아닌 종목
  - 근거 소멸: perceived로 들어가 있는데 이번 ETF 어디에도 MIN_WEIGHT 이상 없는 종목 (빼는 후보)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ETF 안 비중 하한(%). 임의로 정한 숫자 - ETF는 수십 종목을 담아 꼬리 쪽 1% 미만은
# "시장이 그 테마로 본다"기보다 지수 채우기에 가깝다. 몇 분기 결과를 보고 조정한다.
MIN_WEIGHT = 2.0


def build_candidates(holdings: dict, members: dict[str, dict[str, str]],
                     universe_names: dict[str, str], min_weight: float = MIN_WEIGHT) -> dict:
    """holdings: fetch 스크립트의 JSON. members: {theme_id: {ticker: linkage}} (현재 승인분).
    universe_names: {ticker: 이름} - 유니버스 밖 종목은 후보에서 뺀다(시총 하한 등).
    반환: {"add": [[theme, ticker, stage, evidence, "perceived", name], ...],
           "stale": [[theme, ticker, name], ...]}"""
    # (theme, ticker) -> 근거 ETF 목록 [(이름, 코드, 비중)]
    seen: dict[tuple[str, str], list[tuple[str, str, float]]] = {}
    for etf in holdings.get("etfs", []):
        for h in etf.get("holdings", []):
            w = h.get("weight")
            if w is None or w < min_weight:
                continue
            for tid in etf.get("themes", []):
                seen.setdefault((tid, h["ticker"]), []).append((etf["name"], etf["etf"], w))

    add = []
    for (tid, code), srcs in sorted(seen.items()):
        if code not in universe_names or code in members.get(tid, {}):
            continue
        srcs.sort(key=lambda s: -s[2])
        cited = ", ".join(f"{n}({c}) {w:.1f}%" for n, c, w in srcs[:3])
        more = f" 외 {len(srcs) - 3}개" if len(srcs) > 3 else ""
        evidence = f"ETF 편입: {cited}{more} ({holdings.get('date', '')} 기준)"
        add.append([tid, code, "시장 인식", evidence, "perceived", universe_names[code]])

    stale = [[tid, code, universe_names.get(code, "")]
             for tid, mem in sorted(members.items())
             for code, linkage in sorted(mem.items())
             if linkage == "perceived" and (tid, code) not in seen]
    return {"add": add, "stale": stale}


def load_members(conn, market: str) -> dict[str, dict[str, str]]:
    """화면과 같은 규칙: 테마별 승인된 최신 run 하나의 행."""
    out: dict[str, dict[str, str]] = {}
    for (tid,) in conn.execute(
            "SELECT DISTINCT theme_id FROM theme_members WHERE market = ? AND approved = 1", (market,)).fetchall():
        run = conn.execute("SELECT MAX(run_id) FROM theme_members WHERE theme_id = ? AND market = ? AND approved = 1",
                           (tid, market)).fetchone()[0]
        out[tid] = {r[0]: r[1] for r in conn.execute(
            "SELECT ticker, linkage FROM theme_members WHERE theme_id = ? AND market = ? AND run_id = ? AND approved = 1",
            (tid, market, run)).fetchall()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdings", required=True)
    ap.add_argument("--universe", default=str(ROOT / "data" / "kr_universe.json"))
    ap.add_argument("--out", default=None, help="후보 JSON 저장 경로 (기본: out/perception_candidates_<date>_KR.json)")
    ap.add_argument("--min-weight", type=float, default=MIN_WEIGHT)
    args = ap.parse_args()

    from src.db.data_store import get_db

    holdings = json.load(open(args.holdings, encoding="utf-8"))
    names = {it["symbol"]: it["name"] for it in json.load(open(args.universe, encoding="utf-8"))["items"]}
    members = load_members(get_db(), "KR")
    res = build_candidates(holdings, members, names, args.min_weight)

    print(f"[perception] ETF {len(holdings.get('etfs', []))}개({holdings.get('date')}), 비중 하한 {args.min_weight}%")
    print(f"[perception] 후보 {len(res['add'])}건 / 근거 소멸 {len(res['stale'])}건")
    for tid, code, _stage, ev, _l, name in res["add"]:
        print(f"  + [{tid}] {code} {name}: {ev}")
    for tid, code, name in res["stale"]:
        print(f"  - [{tid}] {code} {name}: perceived인데 이번 ETF 근거 없음")

    out = Path(args.out or ROOT / "out" / f"perception_candidates_{holdings.get('date')}_KR.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"date": holdings.get("date"), "min_weight": args.min_weight,
               "add": [r[:5] for r in res["add"]], "add_names": {r[1]: r[5] for r in res["add"]},
               "stale": res["stale"]}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[perception] 저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
