"""DART OpenAPI 호출 (분기 재설계 docs/REDESIGN_SPEC.md 4-1).

키는 환경변수 DART_API_KEY로만 받는다. 코드·저장소·로그에 키를 남기지 않는다.

쓰는 API
  corpCode.xml        전체 기업 고유번호 zip. 종목코드(6자리) -> 기업코드(8자리) 매핑
  company.json        기업개황(업종코드 등)
  list.json           공시 검색 - 최근 사업보고서 접수번호 찾기
  document.xml        공시 원문 zip - 사업보고서의 "사업의 개요" 텍스트 추출
  fnlttSinglAcnt.json 단일회사 주요계정 - 매출액·영업이익·당기순이익

DART 상태 코드: 000 정상 / 013 조회된 데이터 없음 / 020 요청 제한 초과 / 800 점검 /
010·011 키 오류. 013은 오류가 아니라 "그 보고서가 없다"는 뜻이라 빈 결과로 돌려준다.
"""
from __future__ import annotations

import io
import json
import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

BASE = "https://opendart.fss.or.kr/api"
MAX_ATTEMPTS = 5
NO_DATA = "013"
RETRY_STATUSES = {"020", "800", "900"}


class DartKeyError(RuntimeError):
    """키가 없거나 잘못됐다 - 재시도해도 소용없으니 즉시 멈춘다."""


def api_key() -> str:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        raise DartKeyError("DART_API_KEY 환경변수가 없다 (GitHub Actions는 Secrets에 등록)")
    return key


def _get(path: str, params: dict, *, binary: bool = False):
    """재시도 포함 GET. binary면 bytes, 아니면 파싱된 JSON."""
    params = {"crtfc_key": api_key(), **params}
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}"
                time.sleep(min(2 ** (attempt + 1), 30))
                continue
            r.raise_for_status()
            if binary:
                # 오류일 때는 zip 대신 JSON/XML 오류 메시지가 온다
                if r.content[:2] != b"PK":
                    msg = r.content[:300].decode("utf-8", errors="replace")
                    if "010" in msg or "011" in msg:
                        raise DartKeyError("DART 키가 유효하지 않다")
                    if NO_DATA in msg:
                        return None
                    last = msg
                    time.sleep(min(2 ** (attempt + 1), 30))
                    continue
                return r.content
            data = r.json()
            status = str(data.get("status", ""))
            if status == "000":
                return data
            if status == NO_DATA:
                return {"status": NO_DATA, "list": []}
            if status in ("010", "011", "012"):
                raise DartKeyError(f"DART 키 오류 status={status}")
            if status in RETRY_STATUSES:
                last = f"status={status} {data.get('message', '')}"
                time.sleep(min(2 ** (attempt + 2), 60))
                continue
            raise RuntimeError(f"DART 오류 status={status} {data.get('message', '')}")
        except (requests.Timeout, requests.ConnectionError) as e:
            last = type(e).__name__
            time.sleep(min(2 ** (attempt + 1), 30))
    raise RuntimeError(f"DART 호출 실패 {path}: {last}")


# ── 기업코드 매핑 ──────────────────────────────────────────────

def load_corp_codes(cache: Path, max_age_days: int = 30) -> dict[str, str]:
    """{종목코드: 기업코드}. 캐시 파일이 max_age_days보다 새로우면 다운로드하지 않는다."""
    if cache.exists() and (time.time() - cache.stat().st_mtime) < max_age_days * 86400:
        return json.loads(cache.read_text(encoding="utf-8"))
    raw = _get("corpCode.xml", {}, binary=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    root = ET.fromstring(xml_bytes)
    mapping: dict[str, str] = {}
    for item in root.iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        if stock and corp:
            mapping[stock] = corp
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(mapping, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return mapping


# ── 재무 ──────────────────────────────────────────────────────

def fetch_key_accounts(corp_code: str, year: int, reprt_code: str) -> list[dict]:
    """단일회사 주요계정. 보고서가 없으면 빈 목록."""
    data = _get("fnlttSinglAcnt.json",
                {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code})
    return list(data.get("list") or [])


# ── 기업개황·사업의 개요 ──────────────────────────────────────

def fetch_company(corp_code: str) -> dict:
    data = _get("company.json", {"corp_code": corp_code})
    return data if data.get("status") == "000" else {}


def latest_annual_report_no(corp_code: str, bgn_de: str, end_de: str) -> str | None:
    """기간 안에서 가장 최근 사업보고서(A001) 접수번호. 없으면 None."""
    data = _get("list.json", {"corp_code": corp_code, "bgn_de": bgn_de, "end_de": end_de,
                              "pblntf_detail_ty": "A001", "page_count": "10"})
    items = [i for i in (data.get("list") or []) if "사업보고서" in (i.get("report_nm") or "")]
    if not items:
        return None
    items.sort(key=lambda i: i.get("rcept_dt", ""), reverse=True)
    return items[0].get("rcept_no")


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def business_overview(rcept_no: str, max_chars: int = 2500) -> str | None:
    """사업보고서 원문에서 'II. 사업의 내용'의 '1. 사업의 개요' 본문을 뽑는다.

    원문은 DART 전용 XML이라 구조가 회사마다 조금씩 다르다. 제목 문자열로 구간을 잡고
    태그를 걷어낸 텍스트만 쓴다. 못 찾으면 None(사업정보 없음과 같게 취급).
    """
    raw = _get("document.xml", {"rcept_no": rcept_no}, binary=True)
    if not raw:
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        # 본문이 가장 큰 파일이다(첨부·감사보고서는 따로 있다)
        name = max(zf.namelist(), key=lambda n: zf.getinfo(n).file_size)
        text = zf.read(name).decode("utf-8", errors="replace")
    plain = _SPACE_RE.sub(" ", _TAG_RE.sub(" ", text))
    start = re.search(r"1\s*\.\s*사업의\s*개요", plain)
    if not start:
        return None
    rest = plain[start.end():]
    end = re.search(r"2\s*\.\s*주요\s*(제품|사업)", rest)
    body = (rest[:end.start()] if end else rest).strip()
    return body[:max_chars] if len(body) >= 50 else None
