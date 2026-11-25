#!/usr/bin/env python3
"""リビングのエアコン自動制御。使い方: acctl.py <夏ゆるめ|夏標準|夏厳しめ|冬ゆるめ|冬標準|冬厳しめ>
別名: ゆるめ/標準/厳しめ は夏の各ルールと同じ。5分おき
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
HEAT_STREAK = 60 * 60  # 暖房が連続したらオフにする時間
HEAT_COOLDOWN = 10 * 60  # その後オフを続ける時間
FIELDS = ["time", "rule", "temp", "hum", "state", "target", "current", "action", "reason", "result"]

OFF = {"mode": "off"}
FAN2 = {"mode": "fan", "fan": 2}
C26F2 = {"mode": "cool", "temperature": 26, "fan": 2}
C26F3 = {"mode": "cool", "temperature": 26, "fan": 3}
DRY = {"mode": "dry", "temperature": 24, "fan": 2}
HEAT = {"mode": "heat", "temperature": 22, "fan": 2}
HEAT23 = {"mode": "heat", "temperature": 23, "fan": 2}
HEAT24 = {"mode": "heat", "temperature": 24, "fan": 2}
HEAT25 = {"mode": "heat", "temperature": 25, "fan": 2}

# 夏: (閾値表: T>x なら設定, 上から), off閾値(T<=x)。T<24.5 は共通で heat22 風2
SUMMER = {
    "夏厳しめ": ([(27.0, "COOL3", C26F3), (26.0, "COOL2", C26F2)], 24.5),
    "夏標準":   ([(27.5, "COOL3", C26F3), (26.5, "COOL2", C26F2), (26.0, "FAN", FAN2)], 25.5),
    "夏ゆるめ": ([(28.0, "COOL3", C26F3), (27.0, "COOL2", C26F2), (26.0, "FAN", FAN2)], 25.0),
}
# 冬: T>cool なら冷房、T>off_above なら off、T<heat_on なら暖房、fan_below があれば heat_on〜fan_below は送風、残りは前回維持
WINTER = {
    "冬ゆるめ": {"heat_on": 24.0, "heat": HEAT23, "fan_below": 25.0, "off_above": 25.5, "cool": [(28.0, "COOL2", C26F2)]},
    "冬標準":   {"heat_on": 25.0, "heat": HEAT25, "off_above": 26.0, "cool": [(27.5, "COOL2", C26F2)]},
    "冬厳しめ": {"heat_on": 25.5, "heat": HEAT25, "off_above": 26.5, "cool": [(28.0, "COOL2", C26F2)]},
}
RULES = {
    **SUMMER,
    "厳しめ": SUMMER["夏厳しめ"],
    "標準": SUMMER["夏標準"],
    "ゆるめ": SUMMER["夏ゆるめ"],
    **WINTER,
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

def decide(rule, T, H, t=None):
    if t is None: t = now()
    if H > 60: return "HUMID", DRY
    night = 1 <= t.hour < 10
    if rule in WINTER:
        w = WINTER[rule]
        for th, name, body in w["cool"]:
            if T > th: return name, body
        if T > w["off_above"]: return "OFF", OFF
        if "fan_below" in w and w["heat_on"] <= T < w["fan_below"]:
            return "FAN", FAN2  # 送風は夜間も可
        if night:
            # 睡眠中(1:00〜10:00 JST)は暖房禁止。HOLD帯で暖房が残るのも防ぐ
            return "OFF", OFF
        if T < w["heat_on"]:
            return "COLD", w["heat"]
        return "HOLD", None
    if T < 24.5:
        # 睡眠中(1:00〜10:00 JST)は暖房禁止。全ルール共通
        if night: return "OFF", OFF
        return "COLD", HEAT
    table, offth = RULES[rule]
    for th, name, body in table:
        if T > th: return name, body
    if T <= offth: return "OFF", OFF
    return "HOLD", None

def is_heat(mode):
    return (mode or "").startswith("heat/")

def actual_ac(row):
    """その行のあと実機がどうなっていたか。成功した POST なら target、それ以外は current。"""
    if row.get("action") == "POST" and row.get("result") == "success" and row.get("target"):
        return row["target"]
    return row.get("current") or ""

def heat_streak_start(rows, t, current):
    """いま暖房中なら、直近の非暖房行のあと最初の暖房行の時刻。連続は開始時刻から測り、ログ欠落では切らない。"""
    if not is_heat(current):
        return None
    start = t
    for r in reversed(rows):
        mode = actual_ac(r)
        if not mode or not r.get("time"):
            continue
        try:
            rt = datetime.fromisoformat(r["time"])
        except ValueError:
            continue
        if is_heat(mode):
            start = rt
        else:
            break
    return start

def cooldown_start(rows):
    for r in reversed(rows):
        if r.get("state") == "COOLDOWN" and r.get("action") == "POST" and r.get("result") == "success":
            try:
                return datetime.fromisoformat(r["time"])
            except ValueError:
                return None
    return None

def in_heat_cooldown(rows, t):
    cs = cooldown_start(rows)
    return cs is not None and (t - cs).total_seconds() < HEAT_COOLDOWN

def apply_heat_cooldown(rows, t, current, state, body):
    """暖房1時間連続 → 10分オフ。除湿・冷房・送風・HOLDなどより最優先。"""
    if in_heat_cooldown(rows, t):
        return "COOLDOWN", OFF
    start = heat_streak_start(rows, t, current)
    if start is not None and (t - start).total_seconds() >= HEAT_STREAK:
        return "COOLDOWN", OFF
    return state, body

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
        rows = history()
        S, body = decide(rule, T, H, t)
        S, body = apply_heat_cooldown(rows, t, cur, S, body)
        row.update(temp=T, hum=H, state=S, current=cur)
        if body is None:
            row.update(target=cur, action="SKIP", reason="hold")
        else:
            tgt = norm(body); row["target"] = tgt
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
