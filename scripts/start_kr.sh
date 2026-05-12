#!/bin/bash
cd /root/projects/us-stock
source venv/bin/activate
python scripts/run_kr_analysis.py
echo ''
echo '=== 한국 분석 완료 ==='
exec bash
