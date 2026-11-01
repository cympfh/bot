#!/usr/bin/env python3
"""リビングのエアコン自動制御。使い方: acctl.py <厳しめ|標準|ゆるめ>  (5分おき)
ログ: <このディレクトリ>/aclog/log.csv  グラフ: <このディレクトリ>/aclog/graph.png"""
import csv, json, os, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta

API = "http://127.0.0.1:9094"
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = f"{HERE}/aclog"
LOG = f"{DIR}/log.csv"
PNG = f"{DIR}/graph.png"
INTERVAL = 300
RESEND = 60 * 60
FIELDS = ["time", "rule", "temp", "hum", "state", "target", "current", "action", "reason", "result"]

OFF = {"mode": "off"}
FAN2 = {"mode": "fan", "fan": 2}
C26F2 = {"mode": "cool", "temperature": 26, "fan": 2}
C26F3 = {"mode": "cool", "temperature": 26, "fan": 3}
DRY = {"mode": "dry", "temperature": 24, "fan": 2}
HEAT = {"mode": "heat", "temperature": 22, "fan": 2}

# (閾値表: T>x なら設定, 上から), off閾値(T<=x)
RULES = {
    "厳しめ": ([(27.0, "COOL3", C26F3), (26.0, "COOL2", C26F2)], 24.5),
    "標準":   ([(27.5, "COOL3", C26F3), (26.5, "COOL2", C26F2), (26.0, "FAN", FAN2)], 25.5),
    "ゆるめ": ([(28.0, "COOL3", C26F3), (27.0, "COOL2", C26F2), (26.0, "FAN", FAN2)], 25.0),
}

def now(): return datetime.now()
def get(path):
    with urllib.request.urlopen(API + path, timeout=10) as r: return json.load(r)
def post(body):
    req = urllib.request.Request(API + "/api/aircon", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r: return json.load(r)

def ensure_api():
    try: get("/api/aircon"); return
    except Exception: pass
    env = dict(os.environ, PATH=f"/home/box/.local/bin:{HERE}/venv/bin:" + os.environ.get("PATH", ""))
    subprocess.Popen(["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "9094"], cwd=HERE,
                     env=env, stdout=open(f"{DIR}/uvicorn.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(8)

def norm(d):
    m = d.get("mode")
    if m == "off" or d.get("power") == "off": return "off"
    if m == "fan": return f"fan/{d.get('fan')}"
    return f"{m}/{d.get('temperature')}/{d.get('fan')}"

def decide(rule, T, H):
    if H > 60: return "HUMID", DRY
    if T < 20: return "COLD", HEAT
    table, offth = RULES[rule]
    for th, name, body in table:
        if T > th: return name, body
    if T <= offth: return "OFF", OFF
    return "HOLD", None

def write(row):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new: w.writeheader()
        w.writerow(row)
    print(",".join(str(row[k]) for k in FIELDS), flush=True)

def history():
    if not os.path.exists(LOG): return []
    with open(LOG) as f: return list(csv.DictReader(f))

def last_post_time(rows, target):
    for r in reversed(rows):
        if r["action"] == "POST" and r["target"] == target and r["result"] == "success":
            return datetime.fromisoformat(r["time"])
    return None

def step(rule):
    t = now()
    row = dict.fromkeys(FIELDS, ""); row.update(time=t.isoformat(timespec="seconds"), rule=rule)
    try:
        ensure_api()
        T = H = None
        for _ in range(3):
            try:
                b = get("/api/temp/hub2")["raw"]["body"]; T, H = float(b["temperature"]), float(b["humidity"]); break
            except Exception: time.sleep(5)
        if T is None: raise RuntimeError("hub2 read failed")
        cur = norm(get("/api/aircon"))
        S, body = decide(rule, T, H)
        row.update(temp=T, hum=H, state=S, current=cur)
        if body is None:
            row.update(target=cur, action="SKIP", reason="hold")
        else:
            tgt = norm(body); row["target"] = tgt
            rows = history()
            since = t - timedelta(seconds=RESEND)
            recent = [r for r in rows if r["time"] and datetime.fromisoformat(r["time"]) >= since and r["state"]]
            lp = last_post_time(rows, tgt)
            if tgt != cur: reason = "change"
            elif (rows and datetime.fromisoformat(rows[0]["time"]) <= since and recent
                  and all(r["state"] == S and r["rule"] == rule for r in recent)
                  and (lp is None or (t - lp).total_seconds() >= RESEND)): reason = "hourly-resend"
            else: reason = None
            if reason:
                res = post(body)
                row.update(action="POST", reason=reason, result=res.get("message", res.get("statusCode")))
            else:
                row.update(action="SKIP", reason="match")
    except Exception as e:
        row.update(action="ERROR", reason=str(e)[:200])
    write(row)

def main():
    rule = sys.argv[1] if len(sys.argv) > 1 else "標準"
    if rule not in RULES: sys.exit(f"rule must be one of {list(RULES)}")
    os.makedirs(DIR, exist_ok=True)
    while True:
        step(rule)
        try: subprocess.run([sys.executable, f"{HERE}/acgraph.py"], timeout=60)
        except Exception: pass
        time.sleep(INTERVAL)

if __name__ == "__main__": main()
