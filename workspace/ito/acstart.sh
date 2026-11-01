#!/bin/bash
# 使い方: acstart.sh <厳しめ|標準|ゆるめ>  既存プロセスを止めて起動し直す
pkill -f "acctl.py" ; sleep 1
cd /workspace/ito && nohup venv/bin/python acctl.py "$1" >> aclog/acctl.out 2>&1 &
echo "started $1 pid $!"
