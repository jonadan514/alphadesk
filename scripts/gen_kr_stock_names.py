"""화면용 한국 종목 이름맵(frontend/src/lib/krStockNames.ts)을 다시 만든다.

한국 종목은 6자리 숫자 코드라 티커만으로는 사람이 못 읽는데, theme_members에 회사명
컬럼이 없어서 화면이 이 정적 맵으로 이름을 붙인다.

두 가지를 반드시 지킨다(2026-09-10·09-15에 실제로 사고가 났던 지점).
  1. 누적한다 - 유니버스에서 빠진 종목의 이름도 지우지 않는다. 예전 run에 승인된 소속이
     화면에 남아 있을 수 있어서, 지우면 그 종목이 코드로만 보인다.
  2. 손검수 정적 리스트(src/collectors/kr_kospi_list.py)를 우선한다 - 손으로 정정한
     이름(포스코인터내셔널·한온시스템·아모레 등)이 pykrx 표기로 되돌아가지 않게.
  3. krStockName() 함수를 같이 쓴다 - 예전에 재생성하면서 이 함수가 통째로 빠져
     프런트 빌드가 깨진 적이 있다.

Usage:
  python scripts/gen_kr_stock_names.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "frontend" / "src" / "lib" / "krStockNames.ts"
UNIVERSE = ROOT / "data" / "kr_universe.json"

HEADER = """// 자동 생성(scripts/gen_kr_stock_names.py) - 직접 수정하지 말 것.
// 출처: src/collectors/kr_kospi_list.py(손검수 정적 리스트) + pykrx 전종목
// 유니버스(data/kr_universe.json). 정적 리스트를 우선한다 - 2026-09-10에
// 정정한 이름 4건(포스코인터내셔널/한온시스템/아모레 2건)을 보존하기 위함.
// 유니버스에서 빠진 종목의 이름도 지우지 않고 누적한다 - 예전 run에 승인된 소속이
// 화면에 남아 있을 수 있어서다.
// 한국 종목은 6자리 숫자 코드라 티커만으로는 사람이 못 읽어서, 화면에
// 회사명을 같이 보여주기 위한 정적 맵이다(theme_members에 name 컬럼이 없다).
export const KR_STOCK_NAMES: Record<string, string> = {
"""

FOOTER = """};

/** 한국 종목 코드 -> 회사명. 목록에 없으면 코드를 그대로 돌려준다. */
export function krStockName(code: string): string {
  return KR_STOCK_NAMES[code] ?? code;
}
"""


def existing() -> dict[str, str]:
    if not OUT.exists():
        return {}
    text = OUT.read_text(encoding="utf-8")
    return dict(re.findall(r'"(\d[0-9A-Z]{5})":\s*"((?:[^"\\]|\\.)*)"', text))


def main() -> int:
    names = existing()
    before = len(names)

    payload = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    for item in payload.get("items", []):
        if item.get("name"):
            names[item["symbol"]] = item["name"]

    from collectors.kr_kospi_list import CORE_STOCKS, KOSPI200_ADDITIONS
    for code, name, *_ in list(CORE_STOCKS) + list(KOSPI200_ADDITIONS):
        names[code] = name  # 손검수 리스트가 마지막에 덮어쓴다(우선순위 1)

    lines = [f'  "{code}": "{names[code]}",' for code in sorted(names)]
    OUT.write_text(HEADER + "\n".join(lines) + "\n" + FOOTER, encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"이름맵 {before} -> {len(names)}종목 (유니버스 {len(payload.get('items', []))}) 저장: "
          f"{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
