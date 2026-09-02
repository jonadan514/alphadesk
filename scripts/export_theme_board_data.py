"""테마 보드 화면 목업 제작용 - 이번 주 theme_signals + 소속 기업을 JSON으로 출력.
임시 스크립트 (SPEC_phase_a_signals.md §6 화면 설계용, 완료 후 삭제 예정)."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import yaml
from src.db.data_store import get_db
from src.db.theme_signals import get_approved_theme_members

THEMES_YAML = ROOT / "config" / "themes.yaml"


def _current_week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


def main() -> None:
    with open(THEMES_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    names = {t["id"]: {"ko": t["name_ko"], "en": t["name_en"]} for t in data["themes"]}

    conn = get_db()
    week_start = _current_week_monday(date.today()).isoformat()

    rows = conn.execute(
        """
        SELECT theme_id, news_count, news_baseline, news_ratio, news_arrow,
               earn_members, earn_improved, earn_insufficient, earn_ratio, earn_arrow, earn_as_of,
               price_median_ret, price_index_ret, price_excess, price_arrow, label, member_count
        FROM theme_signals WHERE market='US' AND week_start=?
        """,
        (week_start,),
    ).fetchall()
    cols = ["theme_id", "news_count", "news_baseline", "news_ratio", "news_arrow",
            "earn_members", "earn_improved", "earn_insufficient", "earn_ratio", "earn_arrow", "earn_as_of",
            "price_median_ret", "price_index_ret", "price_excess", "price_arrow", "label", "member_count"]

    out = []
    for r in rows:
        d = dict(zip(cols, r))
        d["name_ko"] = names.get(d["theme_id"], {}).get("ko", d["theme_id"])
        d["name_en"] = names.get(d["theme_id"], {}).get("en", "")
        out.append(d)

    # 라벨 붙은 테마들의 소속 기업 상세도 같이 뽑기
    members_out = {}
    for d in out:
        if d["label"]:
            members = get_approved_theme_members(conn, d["theme_id"], "US", ("direct", "partial", "peripheral"))
            rows2 = conn.execute(
                f"""
                SELECT ticker, stage, evidence, linkage, confidence
                FROM theme_members WHERE theme_id=? AND market='US' AND approved=1
                AND ticker IN ({",".join("?" for _ in members)})
                """,
                (d["theme_id"], *[m["ticker"] for m in members]),
            ).fetchall() if members else []
            members_out[d["theme_id"]] = [
                {"ticker": r[0], "stage": r[1], "evidence": r[2], "linkage": r[3], "confidence": r[4]}
                for r in rows2
            ]

    conn.close()
    print(json.dumps({"week_start": week_start, "signals": out, "members": members_out},
                      ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
