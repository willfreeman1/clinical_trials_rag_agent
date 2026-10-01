#!/bin/bash
# Kill the scoring instance if it stalls or overruns 14 hours.
MAX_SEC=50400
STALE_SEC=1200
SETUP_SEC=2700
START=$(date +%s)
while true; do
  sleep 60
  if [ -f /tmp/qwen_score.done ]; then
    exit 0
  fi
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))
  if [ "$ELAPSED" -ge "$MAX_SEC" ]; then
    echo "deadman max ${ELAPSED}s" >> /tmp/deadman.log
    break
  fi
  if [ -f /tmp/keep_alive ]; then
    MTIME=$(stat -c %Y /tmp/keep_alive)
    AGE=$((NOW - MTIME))
    if [ "$AGE" -ge "$STALE_SEC" ]; then
      echo "deadman stale keep_alive ${AGE}s" >> /tmp/deadman.log
      break
    fi
  elif [ "$ELAPSED" -ge "$SETUP_SEC" ]; then
    echo "deadman no keep_alive after ${ELAPSED}s" >> /tmp/deadman.log
    break
  fi
done
if [ -f /tmp/qwen_score.done ]; then
  exit 0
fi
python3 - <<'PY'
import json, urllib.request
key = open("/tmp/lkey").read().strip()
iid = open("/tmp/instance_id").read().strip()
req = urllib.request.Request(
    "https://cloud.lambda.ai/api/v1/instance-operations/terminate",
    data=json.dumps({"instance_ids": [iid]}).encode(),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=30)
PY
