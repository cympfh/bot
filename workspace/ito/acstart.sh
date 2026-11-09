#!/bin/bash
# 使い方: acstart.sh <夏ゆるめ|夏標準|夏厳しめ|冬ゆるめ|冬標準|冬厳しめ または夏の別名>  既存プロセスを止めて起動し直す
pkill -f "acctl.py" ; sleep 1
cd "$(dirname "$(readlink -f "$0")")" && nohup venv/bin/python acctl.py "$1" >> aclog/acctl.out 2>&1 &
echo "started $1 pid $!"
