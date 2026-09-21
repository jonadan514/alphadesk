"""사람이 내린 매핑 판정을 한 파일(판정 원장)로 모은다.

왜 필요한가 (2026-09-15):
분기마다 매핑을 다시 돌리면 LLM은 같은 실수를 반복한다(칩 설계사를 반도체장비에,
커넥터 회사를 전선에). 두 번 돌려 둘 다 나온 것만 쓰는 투표 방식은 US 오류 16건 중
2건만 걸렀다 - 실수가 일관돼서다. 반면 분기 테스트 run에서 감사가 걸러낸 행 중
US 70%·KR 47%는 이미 사람이 판정한 (테마, 종목)이었다. 같은 판단을 매 분기 다시
하지 않도록 판정을 원장에 쌓아 다음 run에 자동 적용한다(apply_decision_ledger.py).

입력은 검토 파일(data/eval/*review*.json)이다. 검토 파일이 곧 판정 기록이고, 원장은
거기서 다시 만들 수 있는 파생물이다. 새 검토를 마치면 data/eval/review_manifest.json 끝에
항목을 추가하고 이 스크립트를 다시 돌린다. 나중 판정이 앞 판정을 덮는다(순서가 곧 시간 순서).

판정 종류:
  exclude  틀린 편입 - 다음 run에 나오면 자동 제외
  keep     정당한 편입 - 감사가 걸러도 사람 검토로 넘기지 않음, 빠지면 복원 후보
  hold     판단보류로 유지한 것 - keep처럼 다루되 초안에 따로 표시
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "eval" / "mapping_decisions.json"

EVAL_DIR = ROOT / "data" / "eval"
MANIFEST = EVAL_DIR / "review_manifest.json"
# 검토 파일 이름 규칙. manifest에서 빠진 것을 찾는 경고에만 쓴다(읽을 파일을 정하는 데는 쓰지 않는다).
_REVIEW_NAME_RE = re.compile(r"(manual_review|mapping_review|audit_labels)")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_manifest(manifest: Path = MANIFEST) -> list[tuple[str, str]]:
    """[(파일 이름, 판정일)] - manifest에 적힌 순서 그대로(시간 순서, 뒤가 앞을 덮는다)."""
    if not manifest.exists():
        raise FileNotFoundError(f"review_manifest.json이 없다: {manifest}")
    entries = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    out = []
    for i, e in enumerate(entries, 1):
        path, decided = e.get("path"), e.get("decided_at")
        if not path or not decided or not _DATE_RE.match(str(decided)):
            raise ValueError(f"manifest 항목 {i}가 잘못됐다(path와 YYYY-MM-DD decided_at이 필요): {e}")
        out.append((str(path), str(decided)))
    return out


def unlisted_review_files(manifest: Path = MANIFEST) -> list[str]:
    """data/eval에 있는 검토 파일처럼 생긴 것 중 manifest에 없는 것. 조용한 누락을 막는 경고용이다."""
    listed = {p for p, _ in load_manifest(manifest)}
    return sorted(f.name for f in manifest.parent.glob("*.json")
                  if _REVIEW_NAME_RE.search(f.name) and f.name not in listed)


EXCLUDE_KEYS = {"exclude", "unapprove"}
KEEP_KEYS = {"keep", "restore", "approve", "items"}
# 판정이 아니거나(테마 전체 비우기 기록) 사람이 읽는 메모인 키
SKIP_KEYS = {"empty_themes", "tickers"}

_KR_CODE_RE = re.compile(r"^[0-9][0-9A-Z]{5}$")


def _market(ticker: str) -> str:
    return "KR" if _KR_CODE_RE.match(ticker) else "US"


def _walk(node: dict, path: str, date: str, out: list[dict]) -> None:
    for key, val in node.items():
        here = f"{path}.{key}"
        if key in SKIP_KEYS or key.startswith("_"):
            continue
        if isinstance(val, dict):
            _walk(val, here, date, out)
            continue
        if not isinstance(val, list) or key not in EXCLUDE_KEYS | KEEP_KEYS:
            continue
        for item in val:
            if not isinstance(item, list) or len(item) < 2:
                continue
            theme_id, ticker = str(item[0]), str(item[1])
            reason = str(item[2]) if len(item) > 2 else ""
            if key in EXCLUDE_KEYS:
                decision = "exclude"
            else:
                decision = "hold" if "판단보류" in reason else "keep"
            out.append({"market": _market(ticker), "theme_id": theme_id, "ticker": ticker,
                        "decision": decision, "reason": reason, "decided_at": date, "source": here})


def collect(manifest: Path = MANIFEST) -> list[dict]:
    events: list[dict] = []
    for name, date in load_manifest(manifest):
        path = manifest.parent / name
        if not path.exists():
            raise FileNotFoundError(f"manifest에 적힌 검토 파일이 없다: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if "labels" in data:  # 감사 정답지 형식
            # 정답지의 '오류 아님'은 감사 정확도 측정용 라벨이지 편입 검토 결론이 아니다
            # ("SK이노베이션 재생에너지는 약한 연결"도 오류 아님으로 붙어 있다). 자동으로
            # 제외하진 않되 초안에서 다시 보이게 hold로 둔다.
            for lab in data["labels"]:
                ticker = str(lab["ticker"])
                events.append({"market": _market(ticker), "theme_id": lab["theme_id"], "ticker": ticker,
                               "decision": "exclude" if lab.get("error") else "hold",
                               "reason": lab.get("note", ""), "decided_at": date,
                               "source": f"{name}.labels"})
        else:
            _walk(data, name, date, events)
    return events


def main() -> int:
    missing = unlisted_review_files()
    if missing:
        print("경고: data/eval에 있지만 review_manifest.json에 없는 검토 파일 - 원장에 반영되지 않는다:")
        for name in missing:
            print(f"  {name}")
        print("  반영하려면 manifest에 {path, decided_at} 항목을 추가한다.\n")
    events = collect()
    ledger: dict[tuple[str, str, str], dict] = {}
    overridden = 0
    for e in events:
        k = (e["market"], e["theme_id"], e["ticker"])
        if k in ledger and ledger[k]["decision"] != e["decision"]:
            overridden += 1
        ledger[k] = e
    rows = sorted(ledger.values(), key=lambda r: (r["market"], r["theme_id"], r["ticker"]))
    OUT.write_text(json.dumps({
        "_about": "build_decision_ledger.py가 검토 파일에서 생성한 파생물 - 직접 고치지 말고 검토 파일을 고친 뒤 재생성",
        "decisions": rows,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    from collections import Counter
    c = Counter((r["market"], r["decision"]) for r in rows)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"판정 기록 {len(events)}건 -> 원장 {len(rows)}건 (나중 판정으로 바뀐 것 {overridden}건)")
    for mk in ("KR", "US"):
        print(f"  {mk}: " + " / ".join(f"{d} {c[(mk, d)]}" for d in ("exclude", "keep", "hold")))
    print(f"저장: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
