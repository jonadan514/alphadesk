"""GitHub Actions 워크플로 실패 시 텔레그램 알림.

각 워크플로의 `if: failure()` notify-failure 잡에서만 실행된다.
어떤 잡이 실패했는지, 로그를 어디서 볼 수 있는지를 요약해서 보낸다.

필요 env:
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID  — 없으면 조용히 건너뜀
  WORKFLOW_NAME  — github.workflow
  RUN_URL        — Actions 실행 로그 링크
  JOB_RESULTS    — "job1=success,job2=failure,..." 형식 (워크플로 yml에서 조립)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정 — 실패 알림 건너뜀")
        return False

    body = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True
    except Exception as e:
        logger.error("텔레그램 발송 실패: %s", e)
        return False


def _parse_job_results(raw: str) -> list[tuple[str, str]]:
    pairs = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        job, result = chunk.split("=", 1)
        pairs.append((job.strip(), result.strip()))
    return pairs


def main() -> None:
    workflow = os.environ.get("WORKFLOW_NAME", "알 수 없는 워크플로")
    run_url = os.environ.get("RUN_URL", "")
    job_results = _parse_job_results(os.environ.get("JOB_RESULTS", ""))

    failed = [f"{job} ({result})" for job, result in job_results if result in ("failure", "cancelled")]

    lines = [f"⚠️ <b>{workflow} 실패</b>"]
    if failed:
        lines.append("실패/취소된 잡: " + ", ".join(failed))
    else:
        # JOB_RESULTS를 못 받았거나 예상 밖 값일 때도 알림 자체는 보낸다
        lines.append("워크플로가 실패로 종료됐습니다 (잡별 상세는 로그 참고).")
    if run_url:
        lines.append(f'<a href="{run_url}">Actions 로그 보기</a>')

    ok = send_telegram("\n".join(lines))
    logger.info("실패 알림 발송 %s", "완료" if ok else "실패/건너뜀")


if __name__ == "__main__":
    main()
