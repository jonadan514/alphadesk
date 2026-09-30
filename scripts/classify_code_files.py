"""scripts/·src/의 Python 파일이 어디서 쓰이는지 조사해 분류 근거를 만든다 (작업지시서 15장).

삭제하지 않는다. 각 파일이 아래 네 가지 중 어디서 참조되는지 세어서 docs/CODE_CLEANUP_CANDIDATES.md의
표를 채울 근거를 준다. LEGACY_CANDIDATE는 네 조건이 모두 "참조 없음"일 때만 붙는다.

  1. GitHub Actions 워크플로(.github/workflows)에서 호출하는가
  2. 다른 Python 파일이 import하는가
  3. 문서(README·docs)가 현재 운영 명령으로 소개하는가
  4. 다른 파일의 fallback으로 쓰이는가 (사람이 판단해야 하므로 여기서는 import 여부로 갈음)

Usage:
  python scripts/classify_code_files.py            # 표를 출력
  python scripts/classify_code_files.py --json     # 기계가 읽는 형식
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("scripts", "src")
SKIP_PARTS = {"__pycache__", "node_modules"}


def python_files() -> list[Path]:
    out = []
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            if SKIP_PARTS & set(p.parts) or p.name == "__init__.py":
                continue
            out.append(p)
    return sorted(out)


def read(paths) -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8", errors="replace") for p in paths}


def module_names(p: Path) -> set[str]:
    """이 파일을 import할 때 쓰일 수 있는 이름들. src/collectors/x.py -> {x, collectors.x, src.collectors.x}."""
    rel = p.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    names = {parts[-1], ".".join(parts)}
    if parts[0] == "src" and len(parts) > 1:
        names.add(".".join(parts[1:]))
    return names


def imports_of(text: str) -> set[str]:
    """ast로 정확하게 import를 읽는다. 정규식으로 하면 `from a.b import X, Y` 같은 여러 이름
    import를 놓쳐 살아 있는 파일을 '참조 없음'으로 오판한다(첫 버전에서 실제로 그랬다)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            for alias in node.names:
                found.add(f"{node.module}.{alias.name}")
                found.add(alias.name)          # `from collectors import dart_client`
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = python_files()
    texts = read(files)
    workflows = {p: p.read_text(encoding="utf-8", errors="replace")
                 for p in (ROOT / ".github" / "workflows").glob("*.yml")}
    docs = {p: p.read_text(encoding="utf-8", errors="replace")
            for p in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md"), ROOT / "CLAUDE.md"] if p.exists()}
    imports = {p: imports_of(t) for p, t in texts.items()}

    rows = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        names = module_names(p)
        wf = sorted(w.stem for w, t in workflows.items() if rel in t or f"{p.name}" in t and p.parent.name == "scripts" and f"scripts/{p.name}" in t)
        imported_by = sorted(q.relative_to(ROOT).as_posix() for q, imps in imports.items()
                             if q != p and names & imps)
        documented = sorted(d.relative_to(ROOT).as_posix() for d, t in docs.items() if rel in t or (f"scripts/{p.name}" in t and p.parent.name == "scripts"))
        rows.append({"file": rel, "workflows": wf, "imported_by": imported_by, "documented_in": documented})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for r in rows:
        print(f"{r['file']}\n  액션 {r['workflows']}\n  import {r['imported_by']}\n  문서 {r['documented_in'][:4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
