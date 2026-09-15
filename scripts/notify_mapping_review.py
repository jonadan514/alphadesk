"""분기 매핑 run이 끝나면 감사 결과를 요약해 텔레그램으로 검토를 요청한다.

매핑은 자동으로 돌리지만 승인은 사람이 한다. LLM 매핑은 티커 착오(게임 테마에 코스맥스),
사명 기반 추측, 실행마다 흔들리는 누락이 있어 감사 도구만으로 걸러지지 않는다
(2026-09-15 확인 - 감사 정밀도·재현율 약 94%, 감사 자체도 판정 편차가 있음).

필요 env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RUN_ID, RUN_URL
입력: out/evidence_audit_<RUN_ID>_{KR,US}.txt 의 머리 5줄
      out/review_draft_<RUN_ID>_{KR,US}.txt 의 머리 4줄 (판정 원장 적용 결과 - 사람 검토 필요 건수)
"""
from __future__ import annotations

import html
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.notify_failure import send_telegram  # noqa: E402


def _head(path: Path) -> str:
    if not path.exists():
        return "(감사 결과 없음 - 로그 확인)"
    lines = path.read_text(encoding="utf-8").splitlines()
    keep = [ln for ln in lines[:6] if ln.startswith(("대상", "틀린 편입", "  그중"))]
    return "\n".join(keep) or "(요약 없음)"


def _draft(path: Path) -> str:
    """판정 원장 적용 요약. 없으면 빈 문자열(원장 단계 실패 시 감사 요약만 보낸다)."""
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:4])


def main() -> int:
    run_id = os.environ.get("RUN_ID", "").strip()
    run_url = os.environ.get("RUN_URL", "")
    warning = os.environ.get("MAP_WARNING", "").strip()
    out = ROOT / "out"
    if not run_id:
        text = f"⚠️ <b>분기 테마 매핑</b>\nrun_id를 얻지 못했다 - 매핑 단계 로그 확인 필요\n{html.escape(run_url)}"
        send_telegram(text)
        return 1
    kr = _head(out / f"evidence_audit_{run_id}_KR.txt")
    us = _head(out / f"evidence_audit_{run_id}_US.txt")
    kr_d = _draft(out / f"review_draft_{run_id}_KR.txt")
    us_d = _draft(out / f"review_draft_{run_id}_US.txt")
    if kr_d:
        kr += "\n" + kr_d
    if us_d:
        us += "\n" + us_d
    text = (
        "🗂️ <b>분기 테마 매핑 완료 - 검토 필요</b>\n"
        f"run_id: <code>{html.escape(run_id)}</code>\n"
        + (f"⚠️ 매핑 {html.escape(warning)} - 일부 테마 결과 불완전, 재실행 권장\n" if warning else "")
        + "\n"
        f"<b>KR 감사</b>\n{html.escape(kr)}\n\n"
        f"<b>US 감사</b>\n{html.escape(us)}\n\n"
        "아직 승인 안 됨 - 화면은 기존 매핑 그대로다.\n"
        "절차: docs/radar/RUNBOOK_theme_mapping.md\n"
        f"{html.escape(run_url)}"
    )
    ok = send_telegram(text)
    print("텔레그램 발송", "성공" if ok else "실패/건너뜀")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
