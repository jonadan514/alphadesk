"""pykrx로 국고채 금리(장외 최종호가 수익률)를 받아 JSON으로 떨어뜨린다 (2026-10-05).

주간 브리핑의 금리·환율 줄에 한국 금리를 넣기 위한 것. 한국은행 ECOS 키 없이 이미 쓰는 pykrx(KRX)로 받는다.
fetch_kr_universe_pykrx.py와 같은 이유로 격리 환경(pandas<3.0 + pykrx 1.2.8)에서 돌고 저장소 모듈을 import하지 않는다.
저장은 scripts/save_kr_treasury.py가 JSON을 읽어 한다.

    /tmp/krxenv/bin/python scripts/fetch_kr_treasury_pykrx.py --out data/kr_treasury.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

TENORS = {"kr3y": "국고채 3년", "kr10y": "국고채 10년"}
LOOKBACK_DAYS = 21   # 달력일 - 5거래일 전 비교에 넉넉하게


def _log(msg: str) -> None:
    print(f"[kr-treasury] {msg}", flush=True)


def _norm(name: str) -> str:
    return str(name).replace(" ", "")


def fetch() -> dict:
    from pykrx import bond
    out: dict[str, list[dict]] = {k: [] for k in TENORS}
    end = datetime.utcnow() + timedelta(hours=9)          # KST
    day = end
    seen = 0
    # 날짜별 스냅샷(그날의 전 만기 수익률)으로 받는다 - 기간 조회 형식은 버전마다 인자가 달라서.
    while (end - day).days <= LOOKBACK_DAYS:
        if day.weekday() < 5:
            ymd = day.strftime("%Y%m%d")
            try:
                df = bond.get_otc_treasury_yields(ymd)
            except Exception as e:  # noqa: BLE001
                _log(f"{ymd} 조회 실패 {type(e).__name__}: {str(e)[:120]}")
                df = None
            if df is not None and not df.empty:
                col = "수익률" if "수익률" in df.columns else df.columns[0]
                idx = {_norm(i): i for i in df.index}
                for key, name in TENORS.items():
                    src = idx.get(_norm(name))
                    if src is not None:
                        try:
                            out[key].append({"date": day.strftime("%Y-%m-%d"), "value": float(df.loc[src, col])})
                        except (TypeError, ValueError):
                            pass
                seen += 1
        day -= timedelta(days=1)
    _log(f"거래일 {seen}일 수신 - " + ", ".join(f"{k} {len(v)}개" for k, v in out.items()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/kr_treasury.json")
    args = ap.parse_args()
    data = fetch()
    if not any(data.values()):
        _log("받은 값이 없음 - 파일을 쓰지 않는다")
        return 1
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": datetime.utcnow().isoformat(), "items": data}, f, ensure_ascii=False, indent=1)
    for k, v in data.items():
        if v:
            _log(f"{k} 최근 {v[0]['date']} {v[0]['value']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
