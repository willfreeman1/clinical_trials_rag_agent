#!/bin/bash
sleep 2700
if [ -f /tmp/keep_alive ]; then
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
