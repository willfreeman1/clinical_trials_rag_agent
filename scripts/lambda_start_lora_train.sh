#!/bin/bash
set -e
cd /home/ubuntu
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8
rm -f /tmp/lora_train.done
SCORE_KIND=${1:-logit2_minus_logit1}
OUT_DIR=${2:-lora_adapter}
LOG=${3:-lora_train_log.json}
nohup /home/ubuntu/venv/bin/python -u lambda_qwen_lora_train.py --score "$SCORE_KIND" --out "$OUT_DIR" --log "$LOG" --done /tmp/lora_train.done >/tmp/qwen_train.log 2>&1 &
echo $! >/tmp/qwen_train.pid
echo "started train pid $(cat /tmp/qwen_train.pid) score $SCORE_KIND"
