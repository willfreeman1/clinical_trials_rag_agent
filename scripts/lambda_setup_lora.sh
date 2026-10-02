#!/bin/bash
set -e
python3 -m venv ~/venv
source ~/venv/bin/activate
pip install -q --upgrade pip
pip install -q torch --index-url https://download.pytorch.org/whl/cu124
pip install -q transformers accelerate numpy peft
python3 -c "import torch; import peft; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'peft', peft.__version__)"
echo "SETUP_DONE"
