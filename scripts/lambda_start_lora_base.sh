#!/bin/bash
set -e
cd /home/ubuntu
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8
rm -f /tmp/lora_base.done
nohup /home/ubuntu/venv/bin/python -u lambda_qwen_lora_score.py --out score_qwen_elig_v1_base.json --split all --done /tmp/lora_base.done >/tmp/qwen_score.log 2>&1 &
echo $! >/tmp/qwen_score.pid
echo "started base pid $(cat /tmp/qwen_score.pid)"
