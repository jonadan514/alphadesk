"""파일 분류 조사기(scripts/classify_code_files.py)가 살아 있는 파일을 '참조 없음'으로 오판하지 않는지.

첫 버전은 정규식으로 import를 읽다가 `from a.b import X, Y` 형태를 놓쳐, 실제로 쓰이는 파일을
삭제 후보로 올렸다. 삭제 후보 목록은 잘못 만들면 살아 있는 코드를 지우게 하므로 조사기 자체를
검증해 둔다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("classify", ROOT / "scripts" / "classify_code_files.py")
classify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classify)


@pytest.mark.parametrize("line,expected", [
    ("from collectors.dart_financials import REPORT_CODES, latest_quarters", "collectors.dart_financials"),
    ("from collectors import dart_client as dart", "dart_client"),
    ("from src.db.quarterly_financials import (a,\n    b)", "src.db.quarterly_financials"),
    ("import collectors.theme_news_collector as news", "collectors.theme_news_collector"),
])
def test_여러_형태의_import를_읽는다(line, expected):
    assert expected in classify.imports_of(line)


def test_문법_오류가_있는_파일은_빈_집합():
    assert classify.imports_of("def (:") == set()


def test_src_아래_모듈은_세_가지_이름으로_불릴_수_있다():
    names = classify.module_names(ROOT / "src" / "collectors" / "dart_financials.py")
    assert {"dart_financials", "collectors.dart_financials", "src.collectors.dart_financials"} <= names


@pytest.fixture(scope="module")
def rows():
    files = classify.python_files()
    texts = classify.read(files)
    imports = {p: classify.imports_of(t) for p, t in texts.items()}
    by_file = {}
    for p in files:
        names = classify.module_names(p)
        by_file[p.relative_to(ROOT).as_posix()] = sorted(
            q.relative_to(ROOT).as_posix() for q, i in imports.items() if q != p and names & i)
    return by_file


@pytest.mark.parametrize("path", [
    "src/collectors/dart_financials.py",      # collect_kr_quarterly_financials.py가 import
    "src/analyzers/theme_earnings.py",        # compute_theme_earnings.py가 import
    "src/db/quarterly_financials.py",         # collect_kr_quarterly_financials.py가 import
    "src/db/fundamentals_cache.py",
    "src/collectors/theme_price_collector.py",
    "src/llm/openai_json.py",
    "src/collectors/kr_profiles.py",
])
def test_실제로_쓰이는_파일은_import한_곳이_잡힌다(rows, path):
    assert rows[path], f"{path}가 참조 없음으로 나왔다 - 조사기가 import를 놓치고 있다"
