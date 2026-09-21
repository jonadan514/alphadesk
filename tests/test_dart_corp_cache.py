"""DART 기업코드 캐시 신선도 (작업지시서 Phase 7).

전에는 캐시 파일의 mtime으로 30일 신선도를 판단했다. 그런데 이 파일은 저장소에 커밋되고
GitHub Actions가 매번 새로 checkout하므로 mtime은 늘 "방금"이다 - 그래서 캐시가 영원히
갱신되지 않고 신규 상장 종목이 계속 빠졌다. 신선도는 파일 옆 메타 파일에 적힌 수집 시각으로
판단한다.
"""
from __future__ import annotations

import io
import json
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

import collectors.dart_client as dc


def corp_zip(pairs: dict[str, str]) -> bytes:
    """{종목코드: 기업코드}를 DART corpCode.xml zip 형식으로 만든다."""
    items = "".join(f"<list><corp_code>{c}</corp_code><stock_code>{s}</stock_code></list>"
                    for s, c in pairs.items())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("CORPCODE.xml", f"<result>{items}</result>")
    return buf.getvalue()


@pytest.fixture
def downloads(monkeypatch):
    """corpCode.xml 다운로드를 가짜로 바꾸고, 몇 번 받았는지 센다."""
    state = {"count": 0, "pairs": {"005930": "00126380"}}

    def fake_get(path, params, *, binary=False):
        assert path == "corpCode.xml"
        state["count"] += 1
        return corp_zip(state["pairs"])

    monkeypatch.setattr(dc, "_get", fake_get)
    return state


def write_cache(cache, pairs, fetched_days_ago: float | None):
    """캐시 파일과(선택) 메타 파일을 만든다. fetched_days_ago=None이면 메타 파일 없음."""
    cache.write_text(json.dumps(pairs), encoding="utf-8")
    meta = dc.meta_path(cache)
    if fetched_days_ago is not None:
        ts = datetime.now(timezone.utc) - timedelta(days=fetched_days_ago)
        meta.write_text(json.dumps({"fetched_at": ts.isoformat()}), encoding="utf-8")


def test_메타가_30일_이내면_다운로드하지_않는다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=5)
    assert dc.load_corp_codes(cache) == {"AAA": "1"}
    assert downloads["count"] == 0


def test_메타가_30일을_넘으면_새로_받는다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=31)
    assert dc.load_corp_codes(cache) == {"005930": "00126380"}
    assert downloads["count"] == 1


def test_메타_파일이_없으면_오래된_것으로_보고_새로_받는다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=None)
    assert dc.load_corp_codes(cache) == {"005930": "00126380"}
    assert downloads["count"] == 1


def test_파일_mtime이_방금이어도_메타가_오래됐으면_새로_받는다(tmp_path, downloads):
    """git checkout 직후 상황 - 이게 원래 버그다. mtime은 방금이지만 실제 데이터는 오래됐다."""
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=90)
    now = time.time()
    os.utime(cache, (now, now))                       # checkout으로 mtime이 갱신된 것처럼
    os.utime(dc.meta_path(cache), (now, now))
    dc.load_corp_codes(cache)
    assert downloads["count"] == 1, "mtime이 아니라 메타의 수집 시각으로 판단해야 한다"


def test_받은_뒤에_메타를_남긴다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    dc.load_corp_codes(cache)
    meta = json.loads(dc.meta_path(cache).read_text(encoding="utf-8"))
    fetched = datetime.fromisoformat(meta["fetched_at"])
    assert datetime.now(timezone.utc) - fetched < timedelta(minutes=1)
    assert json.loads(cache.read_text(encoding="utf-8")) == {"005930": "00126380"}


def test_받은_직후에는_다시_받지_않는다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    dc.load_corp_codes(cache)
    dc.load_corp_codes(cache)
    assert downloads["count"] == 1


def test_메타가_깨져_있으면_오래된_것으로_본다(tmp_path, downloads):
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=1)
    dc.meta_path(cache).write_text("not json", encoding="utf-8")
    dc.load_corp_codes(cache)
    assert downloads["count"] == 1


def test_캐시_형식은_그대로다(tmp_path, downloads):
    """기존 dart_corp_codes.json 형식({종목코드: 기업코드})을 유지한다."""
    cache = tmp_path / "corp.json"
    dc.load_corp_codes(cache)
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data == {"005930": "00126380"} and "fetched_at" not in data


def test_다운로드가_실패하면_기존_캐시를_지우지_않는다(tmp_path, monkeypatch):
    cache = tmp_path / "corp.json"
    write_cache(cache, {"AAA": "1"}, fetched_days_ago=90)

    def boom(path, params, *, binary=False):
        raise RuntimeError("DART 호출 실패")

    monkeypatch.setattr(dc, "_get", boom)
    with pytest.raises(RuntimeError):
        dc.load_corp_codes(cache)
    assert json.loads(cache.read_text(encoding="utf-8")) == {"AAA": "1"}
