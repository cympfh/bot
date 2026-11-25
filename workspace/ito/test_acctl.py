#!/usr/bin/env python3
"""acctl.py の暖房クールダウン判定テスト。実行: venv/bin/python test_acctl.py"""
from datetime import datetime, timedelta

from acctl import HEAT23, OFF, apply_heat_cooldown, decide


def row(t, current, state="COLD", target="", action="SKIP", result="", rule="冬ゆるめ"):
    return {
        "time": t.isoformat(timespec="seconds"),
        "rule": rule,
        "temp": "",
        "hum": "",
        "state": state,
        "target": target or current,
        "current": current,
        "action": action,
        "reason": "",
        "result": result,
    }


def plan(rule, T, H, t, rows, current):
    S, body = decide(rule, T, H, t)
    return apply_heat_cooldown(rows, t, current, S, body)


def main():
    t = datetime(2026, 11, 25, 15, 0, 0)
    rule = "冬ゆるめ"
    heat, off, fan = "heat/23/2", "off", "fan/2"
    # 昼間・低湿度。22℃ は暖房、24.4℃ は送風

    # 1. 59分暖房 → 通常どおり暖房
    start59 = t - timedelta(minutes=59)
    rows59 = [
        row(start59 - timedelta(minutes=5), off, "OFF"),
        row(start59, off, "COLD", heat, "POST", "success"),
        row(t - timedelta(minutes=30), heat, "COLD"),
        row(t - timedelta(minutes=5), heat, "COLD"),
    ]
    S, body = plan(rule, 22.0, 47.0, t, rows59, heat)
    assert S == "COLD" and body == HEAT23, (S, body)

    # 2. 61分暖房 → COOLDOWN でオフ（HOLD 帯の温度でも優先）
    start61 = t - timedelta(minutes=61)
    rows61 = [
        row(start61 - timedelta(minutes=5), off, "OFF"),
        row(start61, off, "COLD", heat, "POST", "success"),
        row(t - timedelta(minutes=30), heat, "COLD"),
        row(t - timedelta(minutes=5), heat, "COLD"),
    ]
    S, body = plan(rule, 25.2, 47.0, t, rows61, heat)
    assert S == "COOLDOWN" and body == OFF, (S, body)

    # ログ欠落があっても、開始時刻から60分以上なら連続とみなす
    rows_gap = [
        row(t - timedelta(minutes=70), off, "COLD", heat, "POST", "success"),
        row(t - timedelta(minutes=5), heat, "COLD"),
    ]
    S, body = plan(rule, 22.0, 47.0, t, rows_gap, heat)
    assert S == "COOLDOWN" and body == OFF, (S, body)

    # 3. 強制オフから5分後は、寒くても COOLDOWN のまま
    rows_cd5 = rows61 + [
        row(t - timedelta(minutes=5), heat, "COOLDOWN", off, "POST", "success"),
    ]
    S, body = plan(rule, 22.0, 47.0, t, rows_cd5, off)
    assert S == "COOLDOWN" and body == OFF, (S, body)

    # 4. 強制オフから11分後は通常ルールに戻り、寒ければ暖房
    rows_cd11 = rows61 + [
        row(t - timedelta(minutes=11), heat, "COOLDOWN", off, "POST", "success"),
        row(t - timedelta(minutes=6), off, "COOLDOWN", off, "SKIP", ""),
    ]
    S, body = plan(rule, 22.0, 47.0, t, rows_cd11, off)
    assert S == "COLD" and body == HEAT23, (S, body)

    # 5. 暖房していない（送風の連続）→ 通常どおり送風
    rows_fan = [
        row(t - timedelta(minutes=70), off, "FAN", fan, "POST", "success"),
        row(t - timedelta(minutes=5), fan, "FAN"),
    ]
    S, body = plan(rule, 24.4, 47.0, t, rows_fan, fan)
    assert S == "FAN" and body == {"mode": "fan", "fan": 2}, (S, body)

    # 暖房が途中で切れていれば、新しい短い連続はクールダウンしない
    rows_break = [
        row(t - timedelta(minutes=90), off, "COLD", heat, "POST", "success"),
        row(t - timedelta(minutes=40), heat, "FAN", fan, "POST", "success"),
        row(t - timedelta(minutes=20), fan, "COLD", heat, "POST", "success"),
        row(t - timedelta(minutes=5), heat, "COLD"),
    ]
    S, body = plan(rule, 22.0, 47.0, t, rows_break, heat)
    assert S == "COLD" and body == HEAT23, (S, body)

    print("ok")


if __name__ == "__main__":
    main()
