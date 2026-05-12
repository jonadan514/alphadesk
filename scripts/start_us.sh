#!/bin/bash
cd /root/projects/us-stock
source venv/bin/activate
python scripts/run_integrated_analysis.py
echo ''
echo '=== 미국 분석 완료 ==='
exec bash
