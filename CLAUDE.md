## 진행 중인 전환: 리서치 레이더

이 저장소는 종목 스크리너에서 테마 기반 주간 리서치 레이더로
전환 중이다. 작업 전 반드시 `docs/radar/MASTER_PLAN_research_radar.md`를
읽을 것.

### 반드시 지킬 원칙
1. 단일 종합 점수·등급을 만들지 않는다. 세 축을 각각 표시한다.
2. LLM은 재무 수치를 생성하지 않는다. 숫자는 fundamentals_cache에서만 나온다.
3. 트랩 필터 기준값(F-Score 6, ROE 미국 12%/한국 8%, 이자보상 3배, 부채비율 150%)을
   임의로 바꾸지 않는다.
4. 판정은 통과/탈락/데이터부족 3분류. 계산 불가를 탈락으로 처리하지 않는다.
5. 이력 테이블은 덮어쓰지 않는다.

### 문서
- MASTER_PLAN_research_radar.md — 전체 계획, 원칙, 로드맵
- SPEC_fundamentals_cache.md — Phase 0
- SPEC_theme_company_mapping.md — Phase A-2
- SPEC_phase_a_signals.md — Phase A-3~6
