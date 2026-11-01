#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path("/home/box/sand-data/connector-secrets/daab1d84-a97b-4e7e-a201-69a05569f5b7/switchbot.json")
d = json.loads(p.read_text())
os.environ["SWITCHBOT_API_TOKEN"] = d["token"]
os.environ["SWITCHBOT_API_SECRET"] = d["secret"]
sys.argv = ["switchbot"] + sys.argv[1:]
import runpy
runpy.run_path("/workspace/ito/switchbot.py", run_name="__main__")
