# 검토 지적사항 A·B·D·E 수정 지시서 (2026-09-21)

Opus가 커밋 d031a3e..c4108ed를 검토해 다섯 건을 찾았다. **C(분기 재무 타입 보정)는
058f85d로 이미 고쳤다.** 남은 네 건을 아래 순서로 고친다.

공통 규칙
- 테스트는 네트워크·운영 DB·LLM을 쓰지 않는다.
- 고치기 **전에** 실패하는 테스트를 먼저 쓰고, 고친 뒤 통과시킨다. (C에서 쓴 방식:
  `git stash push -- <소스파일>`로 소스만 되돌려 새 테스트가 실제로 실패하는지 확인)
- 운영 DB(Turso)의 성질이 걸리는 곳은 `tests/conftest.py`의 `turso_like_db` 픽스처를 쓴다.
- 마지막에 `python -m pytest -q` 전체 통과(현재 165개) 후 커밋.

---

## A. 실행 기록에 "실제로 쓴 모델"이 남지 않는다

**어디** `scripts/map_theme_companies.py:585`
```python
start_mapping_run(conn, run_id, datetime.utcnow().isoformat(), OPENAI_MODEL, PROMPT_VERSION)
```

**무엇이 문제인가** Phase 5에서 모델을 `config/models.yaml`과 `MODEL_<ROLE>` 환경변수로
정할 수 있게 됐다. 그런데 `mapping_runs.model`에는 여전히 상수 `OPENAI_MODEL`
("gpt-4o-mini")이 박힌다. yaml이나 환경변수로 다른 모델을 쓰면 **기록만 거짓말**이 된다.
이 표는 나중에 "어느 모델로 돌린 매핑이 좋았나"를 비교하는 근거인데, 그 비교가 통째로
무의미해진다.

**어떻게** B와 함께 고친다(아래 참조). `start_mapping_run`에는 실제로 호출에 쓰이는
모델 이름을 넘긴다.

---

## B. 모델 선택 규칙이 "기본값과 다르면"이라는 추측에 기대고 있다

**어디** `scripts/map_theme_companies.py:121`
```python
model = OPENAI_MODEL if OPENAI_MODEL != oj.DEFAULT_MODEL else oj.model_for(role or "theme_mapping")
```

**무엇이 문제인가** `scripts/diagnose_mapping_model.py:90`이 `mtc.OPENAI_MODEL = model`로
모델을 바꿔가며 A/B 측정을 한다. 그걸 받아주려고 위 줄을 넣었는데, 규칙이
"상수가 기본값과 다르면 그걸 쓴다"이다. 그래서 **A/B의 기준선(gpt-4o-mini) 팔만**
조건이 거짓이 되어 `model_for()`로 새어나간다. yaml이나 환경변수에 다른 모델이 적혀
있으면 기준선 팔이 조용히 다른 모델로 바뀌고, 측정 결과는 "기준선 대비"가 아니게 된다.
2026-09-15 v7에서 429 재시도 누락 때문에 측정을 통째로 다시 돌린 적이 있다 - 같은 종류의
사고다.

**어떻게** 추측을 없애고 의도를 명시한다.

1. 모듈 상단에 명시적 덮어쓰기 변수를 둔다.
   ```python
   # A/B 측정용 덮어쓰기. None이면 config/models.yaml의 역할별 모델을 쓴다.
   # diagnose_mapping_model.py가 여기에 모델 이름을 넣어 팔을 바꾼다.
   MODEL_OVERRIDE: str | None = None
   ```
2. 실제로 쓸 모델을 돌려주는 함수를 만든다.
   ```python
   def active_model(role: str = "theme_mapping") -> str:
       return MODEL_OVERRIDE or oj.model_for(role)
   ```
3. `_openai_json()`은 `model = active_model(role or "theme_mapping")`을 쓴다.
   docstring의 "OPENAI_MODEL이 기본 모델과 다르면 그것을 우선한다" 설명도 새 규칙으로 고친다.
4. `scripts/diagnose_mapping_model.py:90`을 `mtc.MODEL_OVERRIDE = model`로 바꾼다.
5. **A 해결**: 585줄을 `active_model("theme_mapping")`을 넘기도록 바꾼다.
6. `OPENAI_MODEL` 상수는 다른 참조가 없으면 지운다. 남겨야 하면 "표시용, 선택에 쓰지 않음"
   주석을 단다.

**테스트** (`tests/test_map_theme_companies.py`에 추가, 없으면 새로 만든다)
- `MODEL_OVERRIDE`가 None이면 `active_model("theme_mapping")`이 yaml 값을 돌려준다
  (monkeypatch로 `oj.model_for`를 가짜로)
- `MODEL_OVERRIDE`를 기본 모델과 **같은 이름**으로 넣어도 그 값이 그대로 쓰인다
  (이게 지금 깨져 있는 경우다)
- `MODEL_OVERRIDE`를 다른 이름으로 넣으면 yaml을 읽지 않는다

---

## D. 마이그레이션 행 수를 운영 DB에서는 셀 수 없다

**어디** `src/db/quarterly_financials.py:85`
```python
return cur.rowcount if hasattr(cur, "rowcount") and cur.rowcount is not None else 0
```

**무엇이 문제인가** 운영의 `_TursoConn.execute()`는 커서가 아니라 자기 자신을 돌려주고
`rowcount`가 **없다**. 그래서 운영에서는 실제로 1000행을 옮겨도 항상 0을 돌려준다.
`scripts/collect_kr_quarterly_financials.py:78-80`이 그 값으로 로그를 찍으므로,
**마이그레이션이 돌았는지 로그로 확인할 방법이 사라진다.** 아직 운영에 이전을 실행하지
않았으니, 실행하기 전에 고쳐야 한다.

**어떻게** `INSERT` 전후로 `SELECT COUNT(*) FROM quarterly_financials_raw`를 세서 차이를
돌려준다. `hasattr(cur, "rowcount")` 분기는 지운다.

**주의** Turso는 `COUNT(*)`도 **문자열**로 돌려준다. `int(...)`로 감싸지 않으면
`str - str`로 죽는다. 이게 바로 `turso_like_db` 픽스처가 잡아줄 지점이다.

**테스트** (`tests/test_quarterly_financials.py`)
- `turso_like_db`로 예전 테이블에 2행을 넣고 `migrate_legacy_rows`가 **2**를 돌려준다
- 같은 연결에서 한 번 더 돌리면 **0**을 돌려준다(이미 옮겨진 행은 세지 않는다)
- 돌려준 값이 `int`다

---

## E. 기업코드 캐시의 메타 파일이 커밋되지 않는다

**어디** `.github/workflows/collect-dart.yml:57`
```
git add data/kr_profiles.json data/dart_corp_codes.json
```

**무엇이 문제인가** Phase 7에서 캐시 신선도를 옆 파일
`data/dart_corp_codes_meta.json`(`dart_client.meta_path()`)에 적기로 했는데, 워크플로가
그 파일을 커밋하지 않는다. 메타 파일이 없으면 `_cache_fetched_at()`이 None을 돌려주고
**"오래된 것"으로 보므로, 매 실행마다 corpCode.zip을 새로 내려받는다.** Phase 7이 없앤
낭비가 그대로 돌아온다.

**어떻게** `git add` 줄에 `data/dart_corp_codes_meta.json`을 추가한다. 커밋 메시지
바로 위 주석("사업정보 보강 결과와 기업코드 캐시를...")도 메타 파일을 포함하도록 한 줄 고친다.

**확인** 워크플로 YAML 문법 검사만 한다. **액션은 돌리지 않는다** - 이번 달 무료 분(2000분)을
이미 다 썼다.

---

## 커밋

건별로 나눈다. 메시지 끝에는 작업한 모델의 서명을 붙인다(Sonnet이면
`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`).

1. `fix: 매핑 실행 기록에 실제로 쓴 모델을 남긴다` (A+B, 진단 스크립트 포함)
2. `fix: 예전 분기 재무 이전 행 수를 운영 DB에서도 센다` (D)
3. `ci: DART 기업코드 캐시 메타 파일도 커밋한다` (E)
