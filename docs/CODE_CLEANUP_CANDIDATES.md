# 코드 파일 분류 (작업지시서 15장)

**삭제하지 않는다.** 이 문서는 어떤 파일이 어디서 쓰이는지 조사한 결과와 분류 제안이다.
조사는 `scripts/classify_code_files.py`(ast로 import를 읽음)로 했고, 조사기 자체는
`tests/test_classify_code_files.py`가 검증한다 - 첫 버전이 정규식으로 import를 읽다 여러 이름을 가져오는
`from a.b import X, Y`를 놓쳐 살아 있는 파일을 삭제 후보로 올렸기 때문이다.

## 분류 기준

| 분류 | 뜻 |
|---|---|
| PRODUCTION | 예약 실행·운영 워크플로가 부르는 실행 진입점 |
| CORE | 여러 곳이 import하는 공용 로직(`src/`) |
| ADMIN | 사람이 승인·검토·정정할 때 수동으로 돌리는 도구 |
| MAINTENANCE | 데이터 파일을 갱신·생성하는 유지보수 스크립트 |
| EXPERIMENT | 진단·실험용. 결과를 DB에 쓰지 않는다 |
| LEGACY_CANDIDATE | 아래 네 조건이 모두 참조 없음일 때만 |

LEGACY_CANDIDATE 조건: (1) 워크플로가 호출하지 않음 (2) 다른 Python 파일이 import하지 않음
(3) 문서가 현재 운영 명령으로 소개하지 않음 (4) 다른 기능의 fallback이 아님

전체 Python 파일 85개 (`scripts/`, `src/`, `__init__.py` 제외)

| 분류 | 개수 |
|---|---|
| PRODUCTION | 16 |
| CORE | 29 |
| ADMIN | 12 |
| MAINTENANCE | 11 |
| EXPERIMENT | 8 |
| LEGACY_CANDIDATE | 9 |

## LEGACY_CANDIDATE 검증

| 파일 | 마지막 수정 | 워크플로 | import | 문서 | 비고 |
|---|---|---|---|---|---|
| `scripts/build_ml_features.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | `src/ml/`만 부른다. 부르는 워크플로·문서 없음 |
| `src/analyzers/technical_indicators.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | 참조 전무 |
| `src/collectors/data_fetcher.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | 초기 범용 fetcher. 이후 전용 collector들로 대체된 것으로 보임 |
| `src/ml/features/equity/build_equity_features.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | 1곳 | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |
| `src/ml/features/macro/build_macro_features.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |
| `src/ml/pipeline/feature_store.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | 3곳 | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |
| `src/ml/pipeline/predict.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |
| `src/ml/pipeline/train.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |
| `src/ml/validation/walk_forward.py` | 2026-05-12(초기 커밋 이후 수정 없음) | - | - | - | `src/ml/` 묶음 - `build_ml_features.py`와 서로만 참조 |

**`src/ml/` 전체는 한 덩어리로 판단해야 한다.** 파일별로 보면 `predict.py`·`train.py` 등은 참조가 없지만
`scripts/build_ml_features.py`가 `src/ml/features/...`를 import한다. 그런데 그 스크립트 자체를 부르는 워크플로도
문서도 없다. README(72행)만 `ml/`을 "LightGBM 기반 지수 방향 예측"으로 소개하는데 그 기능
(`index_predictor.py`)은 2026-08-28 REMOVAL_PLAN에서 이미 삭제됐다 - README 설명을 갱신해야 한다.

`requirements.txt`의 `lightgbm`, `scikit-learn`, `scipy`가 이 묶음 때문에 남아 있을 수 있다. 삭제 전에
다른 곳에서 쓰는지 확인할 것.

## 전체 파일 표

### PRODUCTION (16)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `scripts/collect_earnings_surprise.py` | compute-theme-earnings | - | - |
| `scripts/collect_kr_quarterly_financials.py` | collect-dart | - | - |
| `scripts/collect_theme_news.py` | collect-theme-news | - | 1 |
| `scripts/compute_pick_returns.py` | performance-tracking | - | 2 |
| `scripts/compute_theme_earnings.py` | compute-theme-earnings | - | 1 |
| `scripts/compute_theme_labels.py` | compute-theme-labels | - | 1 |
| `scripts/compute_theme_price.py` | compute-theme-price | - | 1 |
| `scripts/generate_narratives.py` | weekly-watchlist | - | - |
| `scripts/generate_weekly_briefing.py` | weekly-watchlist | - | 2 |
| `scripts/map_theme_companies.py` | quarterly-theme-mapping, theme-mapping | 3곳 | 1 |
| `scripts/notify_failure.py` | performance-tracking, weekly-analysis, weekly-watchlist | 1곳 | - |
| `scripts/run_integrated_analysis.py` | weekly-analysis | - | 2 |
| `scripts/run_kr_analysis.py` | weekly-analysis | - | 3 |
| `scripts/run_watchlist_screen.py` | weekly-watchlist | - | 2 |
| `scripts/send_radar_digest.py` | send-radar-digest | - | 1 |
| `scripts/send_telegram_digest.py` | weekly-analysis | - | 1 |

### CORE (29)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `src/analyzers/ai_response_parser.py` | - | 1곳 | - |
| `src/analyzers/ai_summary_generator.py` | - | 2곳 | - |
| `src/analyzers/kr_sector_analyzer.py` | - | 1곳 | - |
| `src/analyzers/macro_snapshot.py` | - | - | 1 |
| `src/analyzers/sector_analyzer.py` | - | 1곳 | 1 |
| `src/analyzers/theme_earnings.py` | - | 1곳 | 1 |
| `src/analyzers/theme_labels.py` | - | 1곳 | 1 |
| `src/analyzers/theme_price.py` | - | 1곳 | 1 |
| `src/analyzers/trap_filter.py` | - | 2곳 | 5 |
| `src/collectors/dart_client.py` | - | 2곳 | - |
| `src/collectors/dart_financials.py` | - | 1곳 | - |
| `src/collectors/earnings_surprise_collector.py` | - | 2곳 | - |
| `src/collectors/fetch_sp500_list.py` | - | 2곳 | - |
| `src/collectors/fetch_sp500_prices.py` | - | 1곳 | - |
| `src/collectors/kr_kospi200_additions.py` | - | 1곳 | - |
| `src/collectors/kr_kospi_list.py` | - | 10곳 | 1 |
| `src/collectors/kr_profiles.py` | - | 5곳 | - |
| `src/collectors/macro_collector.py` | - | - | 1 |
| `src/collectors/theme_news_collector.py` | - | 2곳 | 1 |
| `src/collectors/theme_price_collector.py` | - | 1곳 | 1 |
| `src/collectors/us_price_fetcher.py` | - | 2곳 | - |
| `src/collectors/watchlist_collector.py` | - | 6곳 | 1 |
| `src/db/data_store.py` | - | 28곳 | 1 |
| `src/db/fundamentals_cache.py` | - | 5곳 | 1 |
| `src/db/quarterly_financials.py` | - | 1곳 | - |
| `src/db/theme_mapping.py` | - | 3곳 | 1 |
| `src/db/theme_signals.py` | - | 6곳 | 1 |
| `src/db/turso_http.py` | - | 4곳 | - |
| `src/llm/openai_json.py` | - | 2곳 | - |

### ADMIN (12)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `scripts/apply_decision_ledger.py` | quarterly-theme-mapping | - | 1 |
| `scripts/approve_theme_mapping.py` | approve-theme-mapping | - | 1 |
| `scripts/audit_mapping_evidence.py` | audit-mapping-evidence, quarterly-theme-mapping | 1곳 | 2 |
| `scripts/backfill_profile_sources.py` | - | - | - |
| `scripts/build_decision_ledger.py` | - | - | 2 |
| `scripts/build_merged_mapping_run.py` | build-merged-mapping-run | - | 1 |
| `scripts/export_theme_mapping_review.py` | export-theme-mapping-review | - | 1 |
| `scripts/list_theme_run_ids.py` | adhoc-list-run-ids | - | 1 |
| `scripts/normalize_theme_evidence.py` | normalize-theme-evidence | - | 1 |
| `scripts/notify_mapping_review.py` | quarterly-theme-mapping | - | - |
| `scripts/relabel_theme_labels.py` | relabel-theme-labels | - | 1 |
| `scripts/unapprove_theme_members.py` | unapprove-theme-members | - | 1 |

### MAINTENANCE (11)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `scripts/add_long_summaries.py` | refresh-universe-data | - | - |
| `scripts/backfill_fundamentals.py` | backfill-fundamentals | - | 1 |
| `scripts/backfill_quarterly_financials.py` | backfill-quarterly-financials | - | - |
| `scripts/backfill_theme_news_counts.py` | backfill-theme-news | - | - |
| `scripts/fetch_kr_profiles.py` | audit-mapping-evidence, quarterly-theme-mapping, refresh-universe-data, theme-mapping | - | - |
| `scripts/fetch_kr_universe_pykrx.py` | probe-kr-universe-source, quarterly-theme-mapping, refresh-universe-data, theme-mapping, weekly-watchlist | - | 1 |
| `scripts/fetch_us_profiles.py` | quarterly-theme-mapping, refresh-universe-data | - | 1 |
| `scripts/fill_kr_profiles_from_dart.py` | collect-dart | - | - |
| `scripts/gen_kospi200_universe.py` | - | - | 1 |
| `scripts/gen_kr_stock_names.py` | - | - | 1 |
| `scripts/gen_theme_names.py` | - | - | 1 |

### EXPERIMENT (8)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `scripts/audit_kr_universe.py` | weekly-watchlist | - | 1 |
| `scripts/classify_code_files.py` | - | - | - |
| `scripts/compare_trap_filter_cache.py` | compare-trap-filter-cache | - | - |
| `scripts/diagnose_mapping_model.py` | diagnose-mapping-model | - | 1 |
| `scripts/diagnose_mapping_prompt.py` | diagnose-mapping-prompt | - | 1 |
| `scripts/diagnose_us_chunk_size.py` | diagnose-us-chunk-size | - | - |
| `scripts/inspect_theme_news.py` | inspect-theme-news | - | 1 |
| `scripts/probe_kr_universe_source.py` | probe-kr-universe-source | - | - |

### LEGACY_CANDIDATE (9)

| 파일 | 워크플로 | import한 곳 | 문서 |
|---|---|---|---|
| `scripts/build_ml_features.py` | - | - | 1 |
| `src/analyzers/technical_indicators.py` | - | - | - |
| `src/collectors/data_fetcher.py` | - | - | - |
| `src/ml/features/equity/build_equity_features.py` | - | 1곳 | - |
| `src/ml/features/macro/build_macro_features.py` | - | - | - |
| `src/ml/pipeline/feature_store.py` | - | 3곳 | - |
| `src/ml/pipeline/predict.py` | - | - | - |
| `src/ml/pipeline/train.py` | - | - | - |
| `src/ml/validation/walk_forward.py` | - | - | - |

