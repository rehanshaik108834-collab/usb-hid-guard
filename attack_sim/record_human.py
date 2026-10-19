"""
Records how a real person types a fixed sentence (key-down timestamps only).

Usage: sudo venv/bin/python attack_sim/record_human.py --label rehan_normal
Then type the sentence shown and press Enter. Run it a few times per person.
Use labels like: rehan_normal, rehan_fast, friend1_normal, friend2_fast
"""
import argparse
import json
import os
import statistics
import sys
import termios
import time

from evdev import InputDevice, list_devices, ecodes as e

SENTENCE = "the quick brown fox jumps over the lazy dog"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "human_traces")


def find_keyboard(path=None):
    if path:
        return InputDevice(path)
    for p in list_devices():
        d = InputDevice(p)
        keys = d.capabilities().get(e.EV_KEY, [])
        if e.KEY_A in keys and e.KEY_ENTER in keys and e.KEY_SPACE in keys:
            return d
    sys.exit("No keyboard found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--device", help="e.g. /dev/input/event2")
    args = ap.parse_args()

    kb = find_keyboard(args.device)
    print(f"Using keyboard: {kb.name} ({kb.path})")
    print("\nType this sentence, then press Enter:\n")
    print(f"    {SENTENCE}\n")
    print("Start typing now...")

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ECHO  # hide what you type in the terminal
    termios.tcsetattr(fd, termios.TCSADRAIN, new)

    events = []
    first = None
    try:
        for ev in kb.read_loop():
            if ev.type != e.EV_KEY or ev.value != 1:  # key-down only
                continue
            t = ev.timestamp()
            if first is None:
                first = t
            if ev.code == e.KEY_ENTER:
                if events:
                    break
                continue
            events.append({"key": e.KEY[ev.code] if ev.code in e.KEY else str(ev.code),
                           "t": round(t - first, 6)})
    finally:
        termios.tcflush(fd, termios.TCIFLUSH)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    times = [x["t"] for x in events]
    gaps = [round(b - a, 6) for a, b in zip(times, times[1:])]
    if not gaps:
        sys.exit("Not enough keys recorded.")
    n = len([f for f in os.listdir(OUT_DIR) if f.startswith(args.label)]) + 1
    path = os.path.join(OUT_DIR, f"{args.label}_{n}.json")
    with open(path, "w") as f:
        json.dump({"label": args.label, "sentence": SENTENCE,
                   "device": kb.name, "events": events, "gaps": gaps}, f, indent=1)
    print(f"\nSaved {path}")
    print(f"Keys: {len(events)} | average gap: {1000*statistics.mean(gaps):.0f} ms | "
          f"median: {1000*statistics.median(gaps):.0f} ms | "
          f"shortest: {1000*min(gaps):.0f} ms")


if __name__ == "__main__":
    main()
