#!/bin/bash
set -e
cd /home/ubuntu
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8
nohup /home/ubuntu/venv/bin/python -u lambda_qwen_elig_v2.py >/tmp/qwen_score.log 2>&1 &
echo $! >/tmp/qwen_score.pid
echo "started pid $(cat /tmp/qwen_score.pid)"
