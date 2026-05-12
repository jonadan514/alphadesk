#!/bin/bash
cd /root/projects/us-stock
source venv/bin/activate

echo '======================================'
echo '  [1/2] 미국 분석 시작...'
echo '======================================'
python scripts/run_integrated_analysis.py
echo ''
echo '=== 미국 분석 완료 ==='
echo ''
echo '======================================'
echo '  [2/2] 한국 분석 시작...'
echo '======================================'
python scripts/run_kr_analysis.py
echo ''
echo '=== 한국 분석 완료 ==='
echo ''
echo '>>> 브라우저 열기: http://localhost:3000'
cmd.exe /c start http://localhost:3000 2>/dev/null || true
exec bash
