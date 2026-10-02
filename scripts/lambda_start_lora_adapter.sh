#!/bin/bash
set -e
cd /home/ubuntu
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8
SPLIT=${1:-dev}
ADAPTER=${2:-lora_adapter}
OUT=${3:-score_qwen_elig_lora.json}
DONE=${4:-/tmp/lora_adapter.done}
rm -f "$DONE"
nohup /home/ubuntu/venv/bin/python -u lambda_qwen_lora_score.py --out "$OUT" --split "$SPLIT" --adapter "$ADAPTER" --done "$DONE" >/tmp/qwen_score.log 2>&1 &
echo $! >/tmp/qwen_score.pid
echo "started adapter score pid $(cat /tmp/qwen_score.pid) split $SPLIT"
