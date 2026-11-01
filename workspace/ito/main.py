import json
import logging
import subprocess
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Literal

from cachetools import TTLCache, cached
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pythonosc import udp_client

app = FastAPI()
logger = logging.getLogger("uvicorn")


STATIC_DIR = Path(__file__).resolve().parent / "static"

LAST_AIRCON_PATH = Path(__file__).resolve().parent / "last_aircon.json"
JST = timezone(timedelta(hours=9))
MODE_LABEL = {"off": "オフ", "cool": "冷房", "dry": "除湿", "heat": "暖房", "fan": "送風"}


def load_last_aircon() -> dict[str, Any] | None:
    try:
        if LAST_AIRCON_PATH.exists():
            return json.loads(LAST_AIRCON_PATH.read_text())
    except Exception as e:
        logger.error(f"Failed to load last aircon: {e}")
    return None


def save_last_aircon(state: dict[str, Any]) -> None:
    LAST_AIRCON_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")



@app.get("/index.html")
@app.get("/")
def index_html():
    return FileResponse(STATIC_DIR / "index.html")



def run(command: str | list[str]) -> str:
    import os
    if isinstance(command, str):
        command = command.strip().split()
    env = os.environ.copy()
    env["PATH"] = f"/home/box/.local/bin:{Path(__file__).resolve().parent}/venv/bin:" + env.get("PATH", "")
    if command and command[0] == "switchbot":
        command = ["/home/box/.local/bin/switchbot", *command[1:]]
    res = subprocess.run(command, capture_output=True, env=env, timeout=20)
    out = res.stdout.decode()
    if not out.strip() and res.stderr:
        logger.error("command %s stderr: %s", command, res.stderr.decode()[:500])
    return out


class Switchbot:
    def __init__(self, device_id: str):
        self.device_id = device_id

    def status(self) -> dict[str, Any]:
        cmd = f"switchbot status {self.device_id}"
        result = run(cmd)
        logger.info(f"Switchbot status command: {cmd}, result: {result}")
        return json.loads(result)

    def status_temp(self, icon: str) -> dict[str, Any]:
        """温湿度"""
        num_retry = 5
        for _ in range(num_retry):
            try:
                data = self.status()
                h = data.get("body", {}).get("humidity", None)
                t = data.get("body", {}).get("temperature", None)
                if h is None or t is None:
                    time.sleep(1)
                    continue
                return {"raw": data, "message": f"{icon}\n{t}℃\n{h}%"}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from Switchbot status: {e}")
                continue

        return {"raw": None, "message": "Timeout"}

    def scene(self, scene_id: str) -> dict[str, Any]:
        result = json.loads(run(f"switchbot scene {scene_id}"))
        return {"status": "Accepted", "sceneId": scene_id, "result": result}

    def send(self, command: dict[str, Any]) -> dict[str, Any]:
        cmd = [
            "switchbot",
            "send",
            self.device_id,
            json.dumps(command),
        ]
        return json.loads(run(cmd))


class VRC:
    def __init__(self):
        res = subprocess.run("withcache ipwin", shell=True, capture_output=True)
        ip = res.stdout.decode().strip()
        port = 9000
        self.client = udp_client.SimpleUDPClient(ip, port)

    def send(self, dest: str, args: list[Any]):
        self.client.send_message(dest, args)


@app.get("/api/temp/bun")
def get_bun():
    result = _bun_cached()
    if result.get("raw") is None:
        _bun_cached.cache.clear()
        result = _bun_cached()
    return result


@cached(cache=TTLCache(maxsize=32, ttl=300))
def _bun_cached():
    return Switchbot("EC3F07FEBB30").status_temp("🐤")


@app.get("/api/temp/onmo")
def get_onmo():
    result = _onmo_cached()
    if result.get("raw") is None:
        _onmo_cached.cache.clear()
        result = _onmo_cached()
    return result


@cached(cache=TTLCache(maxsize=32, ttl=300))
def _onmo_cached():
    return Switchbot("F5BD2BF834BF").status_temp("🏘")


@app.get("/api/temp/hub2")
def get_hub2():
    result = _hub2_cached()
    if result.get("raw") is None:
        _hub2_cached.cache.clear()
        result = _hub2_cached()
    return result


@cached(cache=TTLCache(maxsize=32, ttl=300))
def _hub2_cached():
    return Switchbot("D641FC309593").status_temp("🛋")


@app.get("/api/tenki")
@cached(cache=TTLCache(maxsize=32, ttl=300))
def get_tenki():
    icon = run("tenki --icon").strip()
    emoji = run("tenki --emoji").strip()
    return {"icon": icon, "emoji": emoji}


@app.get("/api/tenki/forecast")
@cached(cache=TTLCache(maxsize=32, ttl=300))
def get_tenki_forecast():
    lines = run("tenki -f -j Tokyo").strip().split("\n")

    def label(line: str) -> str:
        ws = line.split()
        time = ws[1]
        temp = ws[2]
        return f"{time}\n{temp}"

    def icon(line: str) -> str:
        ws = line.split()
        tenki = ws[3]
        icons = {
            "lightning": "\u26a1",
            "thunder": "\u26a1",
            "snow": "\u2603",
            "shower": "\u2614",
            "rain": "\u2602",
            "Haze": "\xf0\x9f\x8c\x81",
            "fog": "\xf0\x9f\x8c\x81",
            "clouds": "\u2601",
            "sun": "\u2600",
            "clear": "\u2600",
            "mist": "\xf0\x9f\x8c\xab",
        }
        icon = icons.get(tenki.lower(), tenki.lower())
        return icon

    labels = [label(line) for line in lines[1:]]
    icons = [icon(line) for line in lines[1:]]
    return {"raw": lines, "loc": lines[0], "labels": labels, "icons": icons}



@app.get("/api/sun")
@cached(cache=TTLCache(maxsize=8, ttl=3600))
def get_sun():
    """東京都文京区の今日の日の出・日の入り（Asia/Tokyo）。"""
    from zoneinfo import ZoneInfo
    from astral import LocationInfo
    from astral.sun import sun as astral_sun

    tz = ZoneInfo("Asia/Tokyo")
    today = datetime.now(tz).date()
    loc = LocationInfo(
        name="Bunkyo",
        region="Tokyo",
        timezone="Asia/Tokyo",
        latitude=35.7081,
        longitude=139.7525,
    )
    s = astral_sun(loc.observer, date=today, tzinfo=tz)
    sunrise = s["sunrise"]
    sunset = s["sunset"]
    return {
        "place": "東京都文京区",
        "date": today.isoformat(),
        "sunrise": sunrise.strftime("%H:%M"),
        "sunset": sunset.strftime("%H:%M"),
        "sunrise_iso": sunrise.isoformat(),
        "sunset_iso": sunset.isoformat(),
    }



@app.get("/api/weather")
@cached(cache=TTLCache(maxsize=8, ttl=600))
def get_weather():
    """東京都文京区の現在天気アイコンと、今日の雨の開始/終了見込み。"""
    import urllib.request
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Tokyo")
    now = datetime.now(tz)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=35.7081&longitude=139.7525"
        "&current=weather_code,precipitation"
        "&hourly=precipitation,weather_code,precipitation_probability"
        "&timezone=Asia%2FTokyo&forecast_days=2"
    )
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    def is_rain(code: int | None, precip: float | None) -> bool:
        c = int(code or 0)
        p = float(precip or 0)
        if p >= 0.1:
            return True
        return (
            51 <= c <= 67
            or 80 <= c <= 82
            or 95 <= c <= 99
        )

    def icon_for(code: int) -> str:
        if code == 0:
            return "☀️"
        if code in (1, 2):
            return "🌤"
        if code == 3:
            return "☁️"
        if code in (45, 48):
            return "🌫"
        if 51 <= code <= 57:
            return "🌦"
        if 61 <= code <= 67 or 80 <= code <= 82:
            return "🌧"
        if 71 <= code <= 77 or 85 <= code <= 86:
            return "❄️"
        if 95 <= code <= 99:
            return "⛈"
        return "🌡"

    cur = data.get("current") or {}
    code = int(cur.get("weather_code") or 0)
    precip_now = float(cur.get("precipitation") or 0)
    raining = is_rain(code, precip_now)

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    precs = hourly.get("precipitation") or []
    codes = hourly.get("weather_code") or []

    # hours from now (ceil to next hour boundary for messaging)
    note = None
    hours = None
    kind = None  # "until_stop" | "until_rain" | None

    def parse_hour(s: str) -> datetime:
        # 2026-09-16T15:00
        return datetime.fromisoformat(s).replace(tzinfo=tz)

    future = []
    for t_s, p, c in zip(times, precs, codes):
        t = parse_hour(t_s)
        if t >= now.replace(minute=0, second=0, microsecond=0):
            future.append((t, float(p or 0), int(c or 0)))

    if raining:
        stop_at = None
        for t, p, c in future:
            if t <= now:
                continue
            if not is_rain(c, p):
                stop_at = t
                break
        if stop_at is None:
            note = "今日中は降り続きそう"
            kind = "until_stop"
        else:
            hours = max(1, int((stop_at - now).total_seconds() // 3600) + (0 if (stop_at - now).total_seconds() % 3600 == 0 else 1))
            # simpler: round up hours
            secs = (stop_at - now).total_seconds()
            hours = max(1, int((secs + 3599) // 3600))
            note = f"あと約{hours}時間で止みそう"
            kind = "until_stop"
    else:
        rain_at = None
        for t, p, c in future:
            if t <= now:
                continue
            if is_rain(c, p):
                rain_at = t
                break
        if rain_at is not None:
            secs = (rain_at - now).total_seconds()
            hours = max(1, int((secs + 3599) // 3600))
            note = f"約{hours}時間後に雨"
            kind = "until_rain"

    return {
        "place": "東京都文京区",
        "icon": icon_for(code),
        "weather_code": code,
        "precipitation_mm": precip_now,
        "raining": raining,
        "note": note,
        "hours": hours,
        "kind": kind,
        "at": now.strftime("%Y-%m-%d %H:%M"),
    }


@app.get("/api/aircon")
def get_aircon():
    """最後に POST したエアコン操作の状態。"""
    state = load_last_aircon()
    if state is None:
        return {"mode": None, "temperature": None, "fan": None, "at": None, "label": None}
    return state

class AirconRequest(BaseModel):
    mode: Literal["off", "cool", "dry", "heat", "fan"]
    temperature: int | None = None
    fan: int | None = None


@app.post("/api/aircon")
async def aircon(data: AirconRequest):
    """エアコン操作。temperature と fan は省略可。"""
    device_id = "02-202010092320-98867876"
    defaults = {
        "off": (26, 1, 3, "off"),
        "cool": (24, 2, 1, "on"),
        "dry": (24, 3, 1, "on"),
        "heat": (26, 5, 1, "on"),
        "fan": (25, 4, 3, "on"),
    }
    if data.mode not in defaults:
        return {"error": "Invalid mode"}

    temp, mode_num, fan, power = defaults[data.mode]
    if data.temperature is not None:
        temp = data.temperature
    if data.fan is not None:
        fan = data.fan
    parameter = f"{temp},{mode_num},{fan},{power}"

    command = {
        "commandType": "command",
        "command": "setAll",
        "parameter": parameter,
    }
    result = Switchbot(device_id).send(command)
    at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    state = {
        "mode": data.mode,
        "temperature": temp,
        "fan": fan,
        "power": power,
        "parameter": parameter,
        "at": at,
        "label": MODE_LABEL.get(data.mode, data.mode),
        "result": result,
    }
    save_last_aircon(state)
    return result


@app.post("/api/scene/id/{scene_id}")
async def scene(scene_id: str):
    return Switchbot("(dummy)").scene(scene_id)


class Oyasumi(BaseModel):
    level: int


@app.post("/api/vrc/oyasumi")
async def oyasumi(data: Oyasumi):
    assert 0 <= data.level <= 3, "level must be between 0 and 3"
    vrc = VRC()
    vrc.send("/avatar/parameters/rbs_enable_suimin", [data.level > 0])
    vrc.send("/avatar/parameters/rbs_foot_anchor", [data.level > 1])
    vrc.send("/avatar/parameters/rbs_hand_anchor", [data.level > 2])
    return data
