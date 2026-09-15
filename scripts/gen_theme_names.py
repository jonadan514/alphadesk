"""config/themes.yaml -> frontend/src/lib/themeNames.ts 생성.

손으로 옮기던 파일이 themes.yaml과 어긋나 있었다(2026-09-15 확인): 한국 전용 테마
k_beauty·k_food·k_content가 빠져 화면에 영문 id로 표시됐고, 건설기계 개명·신규 테마도
따로 반영해야 했다. 보관(archived) 테마도 포함한다 - 과거 주차 데이터를 볼 때 이름이 필요하다.

사용법: python scripts/gen_theme_names.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    themes = yaml.safe_load((ROOT / "config" / "themes.yaml").read_text(encoding="utf-8"))["themes"]
    lines = [
        "// 자동 생성 - 직접 수정하지 말 것. scripts/gen_theme_names.py 로 config/themes.yaml에서 만든다.",
        "// 보관(archived) 테마도 포함한다 - 과거 주차 데이터를 볼 때 이름이 필요하다.",
        "export const THEME_NAMES: Record<string, { ko: string; en: string }> = {",
    ]
    for t in themes:
        lines.append(f"  {t['id']}: {{ ko: {json.dumps(t['name_ko'], ensure_ascii=False)}, "
                     f"en: {json.dumps(t['name_en'], ensure_ascii=False)} }},")
    lines += [
        "};",
        "",
        "export function themeName(themeId: string): { ko: string; en: string } {",
        '  return THEME_NAMES[themeId] ?? { ko: themeId, en: "" };',
        "}",
        "",
    ]
    out = ROOT / "frontend" / "src" / "lib" / "themeNames.ts"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} ({len(themes)} themes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
