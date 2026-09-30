# 뉴스 수집 코드 점검 (분기 재설계 6-1)

점검일 2026-09-17. 코드는 수정하지 않았다. 수치는 `scripts/inspect_theme_news.py`(읽기 전용)와
2026-09-16 주간 수집 실행 로그에서 나왔다.

## 테마별 검색 키워드 (config/themes.yaml)

| 테마 | 시장 | 한국어 키워드 | 영어 키워드 |
|---|---|---|---|
| AI 반도체 (`ai_semiconductor`) | US/KR | AI 반도체, HBM, AI 가속기, GPU 수요, 온디바이스 AI | AI chip, AI accelerator, HBM memory, GPU demand, inference chip |
| 데이터센터 전력 (`datacenter_power`) | US/KR | 데이터센터 전력, 수전설비, 데이터센터 전력수요, 전력 조달 | datacenter power, data center electricity, grid interconnection, power capacity |
| 데이터센터 냉각 (`datacenter_cooling`) | US/KR | 데이터센터 냉각, 액침냉각, 서버 열관리, 공조 설비 | datacenter cooling, liquid cooling, immersion cooling, thermal management |
| AI 소프트웨어·에이전트 (`ai_software`) | US | AI 소프트웨어, AI 에이전트, 엔터프라이즈 AI, AI 수익화 | AI software, AI agent, enterprise AI, AI monetization, LLM application |
| 반도체 장비·소재 (`semi_equipment`) | US/KR | 반도체 장비, 반도체 소재, 웨이퍼 장비, 전공정 장비, 반도체 CAPEX | semiconductor equipment, wafer fab equipment, semicap, chip capex |
| 전력망·송배전 (`power_grid`) | US/KR | 전력망, 송배전, 변압기, 전력기기, 송전망 투자, 배전반 | power grid, transmission, transformer, grid investment, switchgear |
| 원전·SMR (`nuclear_smr`) | US/KR | 원자력 발전, SMR, 소형모듈원자로, 원전 수주, 원전 해체 | nuclear power, SMR, small modular reactor, nuclear reactor order |
| 재생에너지 (`renewable_energy`) | US/KR | 태양광, 풍력, 해상풍력, 재생에너지 발전 | solar power, wind power, offshore wind, renewable energy |
| 에너지저장(ESS) (`energy_storage`) | US/KR | 에너지저장장치, ESS, 계통 안정화, 전력저장 | energy storage, ESS, grid storage, battery storage system |
| 천연가스·LNG (`lng_gas`) | US/KR | 천연가스, LNG, 가스 발전, LNG 수출, LNG 운반선 | natural gas, LNG, gas turbine, LNG export terminal |
| 전선·케이블 (`cable_wire`) | KR/US | 해저케이블, 전력케이블, 초고압 케이블, HVDC | submarine cable, power cable, HVDC cable, high voltage cable |
| 조선 (`shipbuilding`) | US/KR | 조선업, 선박 수주, LNG선, 컨테이너선, 조선 신조선가 | shipbuilding, ship order, LNG carrier, newbuilding price |
| 방산 (`defense`) | US/KR | 방위산업, 방산 수출, 국방예산, 무기 수주, K-방산 | defense contractor, defense budget, weapons order, military spending |
| 항공우주·위성 (`aerospace_space`) | US/KR | 항공기 부품, 우주 발사체, 위성 통신, 저궤도 위성 | aerospace parts, space launch, satellite constellation, low earth orbit |
| 건설기계 (`construction_machinery`) | US/KR | 건설기계, 굴착기, 건설장비 수출, 중장비 | construction equipment, excavator, heavy machinery, compact equipment |
| 인프라 건설 (`infra_construction`) | KR/US | 인프라 투자, 건설 수주, 해외 건설, SOC 예산 | infrastructure spending, construction contract, engineering and construction, public works |
| 산업자동화 (`factory_automation`) | US/KR | 산업자동화, 스마트팩토리, 공작기계, 산업용 로봇, 물류자동화 | factory automation, industrial robot, smart factory, machine tools |
| 비만치료제 (`glp1_obesity`) | US/KR | 비만치료제, GLP-1, 위고비, 젭바운드, 경구용 비만약 | GLP-1, obesity drug, weight loss drug, semaglutide, tirzepatide |
| 바이오시밀러 (`biosimilar`) | US/KR | 바이오시밀러, 바이오 복제약, 시밀러 허가 | biosimilar, biosimilar approval, interchangeable biosimilar |
| CDMO·위탁생산 (`cdmo`) | US/KR | CDMO, 위탁생산, 바이오 위탁개발, 생산능력 증설 | CDMO, contract manufacturing, biologics manufacturing, fill finish |
| 의료기기 (`medical_device`) | US/KR | 의료기기, 수술 로봇, 진단기기, 임플란트 | medical device, surgical robot, diagnostic device, implant |
| 치매·신경질환 (`neuro_alzheimer`) | US/KR | 알츠하이머 치료제, 치매 신약, 신경질환 치료제, 파킨슨병 | Alzheimer drug, dementia treatment, neurodegenerative, Parkinson therapy |
| K-뷰티 (`k_beauty`) | KR | K뷰티, 화장품 수출, 인디 브랜드, 화장품 ODM | K-beauty, Korean cosmetics, beauty export |
| K-푸드 (`k_food`) | KR | K푸드, 식품 수출, 라면 수출, 냉동식품 수출 | K-food, Korean food export, instant noodle export |
| K-콘텐츠·엔터 (`k_content`) | KR | K콘텐츠, 엔터테인먼트 실적, 앨범 판매, 공연 매출, 드라마 제작 | K-content, K-pop, Korean drama production |
| 게임 (`game`) | KR/US | 게임 신작, 게임 매출, 모바일 게임, 게임 퍼블리싱 | video game, game publisher, mobile game, game release |
| 여행·항공 (`travel_airline`) | US/KR | 여행 수요, 항공 여객, 면세점, 호텔 객실단가 | travel demand, airline traffic, duty free, hotel RevPAR |
| 2차전지 (`battery`) | US/KR | 2차전지, 배터리 소재, 양극재, 전고체 배터리, 배터리 수주 | EV battery, cathode material, solid state battery, battery cell |
| 전기차 밸류체인 (`ev_value_chain`) | US/KR | 전기차 판매, 전기차 부품, 충전 인프라, 전기차 보조금 | electric vehicle sales, EV parts, charging infrastructure, EV subsidy |
| 자율주행 (`autonomous_driving`) | US/KR | 자율주행, 로보택시, 라이다, ADAS | autonomous driving, robotaxi, lidar, ADAS |
| 피지컬 AI (`physical_ai`) | US/KR | 피지컬 AI, 로봇 파운데이션 모델, 머신비전, 엣지 AI, 로봇 구동부, 산업용 AI | physical AI, embodied AI, robot foundation model, machine vision, edge AI, robotics platform |
| 희토류·핵심광물 (`rare_earth`) | US/KR | 희토류, 핵심광물, 영구자석, 광물 수출 통제 | rare earth, critical minerals, permanent magnet, mineral export control |
| 구리·산업금속 (`copper_metals`) | US/KR | 구리 가격, 전기동, 알루미늄 가격, 니켈 가격 | copper price, copper demand, aluminum price, industrial metals |
| 특수가스·소재 (`specialty_gas`) | US/KR | 특수가스, 반도체 소재 국산화, 산업용 가스, 전자재료 | specialty gas, electronic materials, industrial gas |
| 석유화학 업황 (`petrochemical`) | US/KR | 석유화학, 에틸렌 스프레드, 정제마진, 화학 업황 | petrochemical, ethylene spread, refining margin, chemical downturn |

## 1. 출처 API

**Google News RSS** (`https://news.google.com/rss/search`). 공식 API가 아니라 RSS 엔드포인트다.

- 한국: `hl=ko&gl=KR&ceid=KR:ko` / 미국: `hl=en-US&gl=US&ceid=US:en`
- 검색어에 날짜 연산자를 붙여 주 단위로 조회: `<키워드> after:2026-09-14 before:2026-09-21`
  (`before`는 배타적)
- 키워드 하나당 **최대 100건**(`limit=100`)만 받는다
- 키워드마다 1초 쉬고 호출(요율제한 방어). 인증·키 없음
- 받는 필드: 제목, 링크, pubDate(발행일), source(매체명)

## 2. 테마별 기사 매칭 방식

**키워드별로 따로 검색해서 합친다.** 테마 하나에 키워드가 3-6개(한국어 평균 4.4개, 영어 4.0개)이고,
각각 따로 Google News에 검색해 결과를 모은 뒤 중복을 제거한다. 기사 본문이나 제목을 다시 매칭하지
않는다 - **Google 검색 결과를 그대로 그 테마의 기사로 본다.**

- 시장별로 키워드가 다르다(`keywords_ko` / `keywords_en`). 번역이 아니라 각각 손으로 정한 목록이다.
- 테마별 최소 기사 수 기본 10건, 개별 지정 6건인 테마 6개
  (데이터센터 냉각, 에너지저장, 전선·케이블, 바이오시밀러, 치매·신경, 특수가스)
- 키워드를 바꾸면 `keywords_changed_at`을 남기고 그 이전 기록은 기준선에 쓰지 않는다
  (현재: 건설기계 2026-09-15)

전체 키워드 목록은 위 표에 있다.

## 3. 중복 기사 제거

**두 단계로 한다.**

1. URL 해시: 쿼리스트링(트래킹 파라미터)을 떼고 SHA-256 앞 16자로 비교
2. 제목 유사도: 특수문자를 공백으로 바꾸고 소문자화한 뒤, `difflib` 유사도 **90% 이상**이면 같은 기사로 본다

2026-09-16 실행 예: 원본 281건 → URL 중복 제거 → 제목 중복 제거 순으로 줄어든다(테마마다 로그에 남는다).
DB의 기본키가 `(테마, 시장, URL 해시)`라 같은 기사가 다른 주에 다시 들어오면 `INSERT OR IGNORE`로 무시된다.

## 4. 기사 보관 기간

**과거 1년치는 없다. 약 10주(70일)뿐이다.**

| | 기사 수 | 테마 | 수집 주 범위 | 분기 |
|---|---|---|---|---|
| 한국 | 65,548 | 34 | 2026-07-13 ~ 2026-09-14 (10주) | 전부 2026-Q3 |
| 미국 | 96,509 | 32 | 2026-07-13 ~ 2026-09-14 (10주) | 전부 2026-Q3 |

- 삭제 로직은 없다. 2026-09-01에 8주 백필을 한 뒤 매주 쌓인 것이 전부다.
- **분기 비교(직전 4분기 평균)를 하려면 최소 5분기치가 필요한데 지금은 1분기치도 안 된다.**
  Google News RSS는 과거 날짜 범위 조회가 되므로 백필은 가능하다(주 단위로 `after:/before:`를 넣으면 된다).

## 5. 분기를 나누는 날짜 기준

**지금은 "수집한 주"가 기준이다.** 기사에 발행일(`published_at`)이 함께 저장되지만, 집계는
`week_start`(수집 대상 주의 월요일)로만 한다.

- 발행일 결측: **0건**(한국·미국 모두). 발행일 기준 재집계가 가능하다.
- 그런데 **발행일이 수집한 주 범위를 벗어난 기사가 10% 있다**(한국 6,780건, 미국 9,823건).
  Google의 `after:/before:` 필터가 정확하지 않아 앞뒤 주 기사가 섞여 들어온다.
  분기를 발행일로 나누면 이 10%가 다른 분기로 재배치된다.
- 현재 데이터는 전부 2026-Q3 안에 있어 두 기준의 분기별 합계가 같다(65,548 / 96,509).
  분기 경계를 넘는 주가 생기면 달라진다.

## 6. 추가로 확인된 것 — 키워드 100건 상한

2026-09-16 실행에서 **키워드-주 조합 281개 중 45개(16%)가 정확히 100건**이었다. 상한에 걸렸다는 뜻이다.
즉 인기 키워드는 실제 기사가 200건이든 500건이든 100건으로 잘려 저장된다.

- 영향: 뜨거운 테마일수록 기사 수가 눌려서, 분기 뉴스 비율(이번 분기 ÷ 직전 4분기 평균)이
  실제보다 작게 나온다. "뉴스 많음 = 1.5배 이상" 기준이 덜 민감해진다.
- 대응 후보: 상한을 올린다 / 키워드를 쪼갠다 / 상한 도달 여부를 기록해 데이터부족으로 표시한다.

## 7. 시황 기사 비율 (6-2 참고)

제목에 주가 관련 단어(급등, 급락, 주가, 특징주, 상한가, 하한가, 신고가, 강세, 약세, surge, soar,
plunge 등)가 들어간 기사는 **한국 3%(2,118건), 미국 2%(2,367건)**다. 지금은 걸러내지 않는다.
