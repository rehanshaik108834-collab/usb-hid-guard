"""
Simulated keystroke-injection device (HARMLESS: it only types text).

Usage:
  sudo venv/bin/python attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast

Modes (delay between key presses):
  fast   : 2 ms, machine speed, like a Rubber Ducky
  slow   : random 80-300 ms, a stealthy attacker trying to look human
  human  : about 150 ms with natural variation

--launcher win-r presses Win+R first (the Windows "Run" dialog shortcut that real attack
scripts use). On Ubuntu it does nothing by default, so the text still goes to the editor.

IMPORTANT: Open the 'Text Editor' app and click inside it before the countdown
ends. The text will be typed there. Never point this at anything but a text editor.
"""
import argparse
import json
import os
import random
import re
import sqlite3
import time

from evdev import UInput, ecodes as e

PAYLOADS = {
    "hello": "HELLO from the simulated keyboard. This is a harmless test.",
    "shellish": "powershell -Command Write-Host HELLO",
    "sentence": "the quick brown fox jumps over the lazy dog",
}

# character -> (keycode, needs_shift)
KEYMAP = {}
for ch in "abcdefghijklmnopqrstuvwxyz":
    code = getattr(e, f"KEY_{ch.upper()}")
    KEYMAP[ch] = (code, False)
    KEYMAP[ch.upper()] = (code, True)
for ch in "1234567890":
    KEYMAP[ch] = (getattr(e, f"KEY_{ch}"), False)
KEYMAP.update({
    " ": (e.KEY_SPACE, False),
    "-": (e.KEY_MINUS, False),
    "_": (e.KEY_MINUS, True),
    ".": (e.KEY_DOT, False),
    ",": (e.KEY_COMMA, False),
    "/": (e.KEY_SLASH, False),
    ":": (e.KEY_SEMICOLON, True),
    "=": (e.KEY_EQUAL, False),
    "'": (e.KEY_APOSTROPHE, False),
    "\n": (e.KEY_ENTER, False),
})


def next_delay(mode):
    if mode == "fast":
        return 0.002
    if mode == "slow":
        return random.uniform(0.08, 0.30)
    return max(0.05, random.gauss(0.15, 0.05))  # human


def press(ui, code, hold):
    ui.write(e.EV_KEY, code, 1)
    ui.syn()
    time.sleep(hold)
    ui.write(e.EV_KEY, code, 0)
    ui.syn()


def type_text(ui, text, mode):
    """Returns (planned delays, actual key-down times)."""
    delays, times = [], []
    for ch in text:
        if ch not in KEYMAP:
            continue
        code, shift = KEYMAP[ch]
        delay = next_delay(mode)
        hold = min(0.01, delay / 2)
        if shift:
            ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
            ui.syn()
        times.append(time.time())
        press(ui, code, hold)
        if shift:
            ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
            ui.syn()
        time.sleep(max(0, delay - hold))
        delays.append(delay)
    return delays, times


def read_challenge_code(name, since, wait=10.0):
    """The code System C shows for this keyboard, read from its event log (what a person sees on
    the dashboard or the detector's terminal). Returns None if no code check appears in time."""
    db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "events.db")
    end = time.time() + wait
    while time.time() < end:
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
            row = conn.execute("SELECT reason FROM events WHERE decision = 'CHALLENGE' AND name = ? AND ts >= ? "
                               "ORDER BY id DESC LIMIT 1", (name, since)).fetchone()
            conn.close()
        except sqlite3.Error:
            row = None
        m = re.search(r"type (\d+) on this keyboard", row[0]) if row else None
        if m:
            return m.group(1)
        time.sleep(0.3)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="Fake Keyboard")
    p.add_argument("--vid", default="dead")
    p.add_argument("--pid", default="beef")
    p.add_argument("--mode", choices=["fast", "slow", "human"], default="fast")
    p.add_argument("--payload", choices=list(PAYLOADS), default="hello")
    p.add_argument("--text", help="custom text instead of a preset payload")
    p.add_argument("--launcher", choices=["none", "win-r"], default="none",
                   help="press a launcher shortcut before typing")
    p.add_argument("--wait", type=int, default=6, help="seconds before typing starts")
    p.add_argument("--save-gaps", help="save the measured gaps between key presses to this JSON file")
    p.add_argument("--answer-challenge", action="store_true",
                   help="act like a person at the screen: if System C holds this keyboard and shows a "
                        "code, type that code (an attack device cannot do this)")
    args = p.parse_args()

    text = args.text if args.text else PAYLOADS[args.payload]
    keys = sorted({code for code, _ in KEYMAP.values()} | {e.KEY_LEFTSHIFT, e.KEY_LEFTMETA})
    ui = UInput({e.EV_KEY: keys}, name=args.name, vendor=int(args.vid, 16),
                product=int(args.pid, 16), bustype=e.BUS_USB)
    print(f"Created {args.name!r} with ID {args.vid}:{args.pid}, mode={args.mode}")
    print(f"Open the Text Editor and click inside it. Typing starts in {args.wait}s...")
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    time.sleep(args.wait)

    start = time.time()
    if args.launcher == "win-r":
        ui.write(e.EV_KEY, e.KEY_LEFTMETA, 1)
        ui.syn()
        press(ui, e.KEY_R, 0.01)
        ui.write(e.EV_KEY, e.KEY_LEFTMETA, 0)
        ui.syn()
        time.sleep(0.5)  # attack scripts wait for the Run dialog to open
    delays, times = type_text(ui, text, args.mode)
    total = time.time() - start
    avg_ms = 1000 * sum(delays) / max(1, len(delays))
    print(f"Typed {len(delays)} characters in {total:.2f}s (average gap {avg_ms:.1f} ms)")
    if args.save_gaps:
        gaps = [round(b - a, 6) for a, b in zip(times, times[1:])]
        os.makedirs(os.path.dirname(os.path.abspath(args.save_gaps)), exist_ok=True)
        with open(args.save_gaps, "w") as f:
            json.dump({"name": args.name, "mode": args.mode, "gaps": gaps}, f)
    if args.answer_challenge:
        code = read_challenge_code(args.name, started)
        if code:
            time.sleep(1.0)  # a person reads the code first
            type_text(ui, code, "human")
            print(f"Typed the code {code} shown on screen")
        else:
            print("No code check was shown")
    time.sleep(1)
    ui.close()
    print("Device removed.")


if __name__ == "__main__":
    main()
