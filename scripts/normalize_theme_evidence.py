"""테마 매핑 evidence 표현을 한국어로 통일한다.

Phase A-2 매핑 프롬프트가 언어를 강제하지 않아서 evidence가 영어/한국어로
섞여 나왔음(화면에서 발견 - 사용자 피드백, 2026-09-02). map_theme_companies.py의
MEMBER_FIELDS_INSTRUCTION은 이제 한국어를 강제하도록 고쳤지만, 이미 승인되어
저장된 기존 데이터는 그대로라 별도로 한 번 정리해야 한다.

approved=1인 theme_members 중 evidence에 한글이 거의 없는(영어로 판단되는)
행만 GPT-4o-mini로 번역한다. 사실관계(회사명·제품명·사업부명·숫자)는 그대로
유지하고 언어·문체만 통일 - 링크·티커·승인여부 등 다른 컬럼은 안 건드림.

Usage:
  python scripts/normalize_theme_evidence.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.db.data_store import get_db

OPENAI_MODEL = "gpt-4o-mini"
BATCH_SIZE = 15
HANGUL_RE = re.compile(r"[가-힣]")


def _log(msg: str) -> None:
    print(f"[normalize] {msg}")


def is_korean(text: str) -> bool:
    """한글 비율 15% 이상이면 이미 한국어로 판단 - 실제 한국어 문장은 고유명사가
    섞여도 이 기준을 넉넉히 넘고, 순수 영어 문장은 0%다."""
    if not text:
        return True
    hangul = len(HANGUL_RE.findall(text))
    return hangul / max(len(text), 1) > 0.15


def translate_batch(rows: list[dict], api_key: str) -> dict[str, str]:
    items = "\n".join(f'{i + 1}. [{r["key"]}] {r["evidence"]}' for i, r in enumerate(rows))
    prompt = f"""다음은 어떤 회사가 특정 투자 테마에 속하는 근거 문장들이다.
전부 자연스러운 한국어 한 문장으로 통일해서 다시 쓰시오. 사실관계(회사명,
제품명, 사업부명, 숫자)는 절대 바꾸지 말고, 언어와 문체만 통일한다. 각 항목의
[ ] 안 key는 그대로 유지해서 답하시오.

{items}

반드시 JSON으로만 답하시오: {{"translations": [{{"key": "...", "text": "..."}}]}}"""
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "당신은 정확한 번역가입니다. 사실관계를 절대 바꾸지 않습니다."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        return {t["key"]: t["text"] for t in data.get("translations", []) if t.get("key") and t.get("text")}
    except Exception as e:
        _log(f"  번역 실패: {type(e).__name__}: {e}")
        return {}


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        _log("OPENAI_API_KEY 미설정")
        sys.exit(1)

    conn = get_db()
    rows = conn.execute(
        "SELECT theme_id, ticker, run_id, evidence FROM theme_members WHERE approved = 1"
    ).fetchall()
    _log(f"승인된 행 {len(rows)}개 확인")

    targets = [
        {"theme_id": r[0], "ticker": r[1], "run_id": r[2], "evidence": r[3], "key": f"{r[0]}|{r[1]}"}
        for r in rows if not is_korean(r[3] or "")
    ]
    _log(f"번역 대상(비한국어로 판단) {len(targets)}개")
    if not targets:
        _log("완료 - 번역 대상 없음")
        return

    updated = 0
    for i in range(0, len(targets), BATCH_SIZE):
        chunk = targets[i:i + BATCH_SIZE]
        translations = translate_batch(chunk, api_key)
        for t in chunk:
            new_text = translations.get(t["key"])
            if not new_text:
                _log(f"  {t['key']}: 번역 누락 - 원문 유지")
                continue
            conn.execute(
                "UPDATE theme_members SET evidence = ? WHERE theme_id = ? AND ticker = ? AND run_id = ?",
                (new_text, t["theme_id"], t["ticker"], t["run_id"]),
            )
            updated += 1
        conn.commit()
        _log(f"  배치 {i // BATCH_SIZE + 1}/{(len(targets) + BATCH_SIZE - 1) // BATCH_SIZE}: {len(chunk)}건 처리")
        time.sleep(0.5)

    conn.close()
    _log(f"완료 - {updated}/{len(targets)}건 갱신")


if __name__ == "__main__":
    main()
