#!/usr/bin/env python3
"""log.csv から直近24時間の温湿度グラフ graph.png を作る。POSTは縦線と注記。"""
import csv, sys
from datetime import datetime, timedelta
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md
import os
HERE = os.path.dirname(os.path.abspath(__file__))
LOG, PNG = f"{HERE}/aclog/log.csv", f"{HERE}/aclog/graph.png"
hours = float(sys.argv[1]) if len(sys.argv) > 1 else 24
rows = list(csv.DictReader(open(LOG)))
since = datetime.now() - timedelta(hours=hours)
rows = [r for r in rows if r["temp"] and datetime.fromisoformat(r["time"]) >= since]
if not rows: sys.exit()
ts = [datetime.fromisoformat(r["time"]) for r in rows]
fig, (ax, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
ax.plot(ts, [float(r["temp"]) for r in rows], color="tab:red", marker=".", label="Temp (C)")
ax2.plot(ts, [float(r["hum"]) for r in rows], color="tab:blue", alpha=.6, marker=".", label="Humidity (%)")
for t, r in zip(ts, rows):
    if r["action"] == "POST":
        ax.axvline(t, color="gray", ls=":", lw=1)
        ax.annotate(r["target"] + ("*" if r["reason"] == "hourly-resend" else ""), (t, float(r["temp"])),
                    fontsize=7, rotation=90, va="bottom", color="dimgray")
ax.set_ylabel("Temp (C)", color="tab:red"); ax2.set_ylabel("Humidity (%)", color="tab:blue")
ax.xaxis.set_major_formatter(md.DateFormatter("%H:%M"))
ax.set_title(f"Living room  rule={ {'厳しめ':'summer-strict','標準':'summer-normal','ゆるめ':'summer-loose','夏厳しめ':'summer-strict','夏標準':'summer-normal','夏ゆるめ':'summer-loose','冬厳しめ':'winter-strict','冬標準':'winter-normal','冬ゆるめ':'winter-loose'}.get(rows[-1]['rule'], rows[-1]['rule']) }  last {rows[-1]['time'][11:16]} JST  {rows[-1]['temp']}C {rows[-1]['hum']}%  (* = resend)")
tv=[float(r["temp"]) for r in rows]; hv=[float(r["hum"]) for r in rows]
ax.set_ylim(min(22, min(tv)-.5), max(28, max(tv)+.5)); ax2.set_ylim(min(35, min(hv)-3), max(65, max(hv)+3))
ax2.axhline(60, color="tab:blue", ls="--", lw=.8)
ax2.xaxis.set_major_formatter(md.DateFormatter("%H:%M"))
ax.grid(alpha=.3); ax2.grid(alpha=.3); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(PNG, dpi=110)
