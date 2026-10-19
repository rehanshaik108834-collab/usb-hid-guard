"""
Replays a recorded human typing trace through a virtual keyboard (HARMLESS text only).

Usage:
  sudo venv/bin/python attack_sim/replay_trace.py --trace attack_sim/human_traces/rehan_fast_3.json \
       --name "Spoofed KB" --vid 0001 --pid 0001

Options:
  --scale 0.5   plays twice as fast (timing x 0.5); --scale 2 plays twice as slow
"""
import argparse
import json
import time

from evdev import UInput, ecodes as e

from fake_keyboard import press  # reuse the key-press helper

SKIP = {"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT", "KEY_LEFTCTRL", "KEY_RIGHTCTRL",
        "KEY_LEFTALT", "KEY_RIGHTALT", "KEY_CAPSLOCK"}


def key_name(raw):
    return raw[0] if isinstance(raw, list) else raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--name", default="Replay Keyboard")
    ap.add_argument("--vid", default="0001")
    ap.add_argument("--pid", default="0001")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--wait", type=int, default=6)
    args = ap.parse_args()

    with open(args.trace) as f:
        data = json.load(f)

    events = []
    for ev in data["events"]:
        name = key_name(ev["key"])
        if name in SKIP or not hasattr(e, name):
            continue
        events.append((getattr(e, name), ev["t"] * args.scale))
    if not events:
        raise SystemExit("Trace has no usable keys")

    keys = sorted({code for code, _ in events})
    ui = UInput({e.EV_KEY: keys}, name=args.name, vendor=int(args.vid, 16),
                product=int(args.pid, 16), bustype=e.BUS_USB)
    print(f"Created {args.name!r} {args.vid}:{args.pid}, replaying {args.trace} (scale {args.scale})")
    print(f"Open the Text Editor and click inside it. Typing starts in {args.wait}s...")
    time.sleep(args.wait)

    hold = 0.01 if args.scale >= 0.5 else 0.001
    start = time.time()
    actual = []
    for code, t in events:
        delay = start + t - time.time()
        if delay > 0:
            time.sleep(delay)
        actual.append(time.time())
        press(ui, code, hold)
    total = time.time() - start
    gaps = sorted(b - a for a, b in zip(actual, actual[1:]))
    median_ms = 1000 * gaps[len(gaps) // 2]
    print(f"Replayed {len(events)} keys in {total:.2f}s (median gap {median_ms:.0f} ms)")
    time.sleep(1)
    ui.close()
    print("Device removed.")


if __name__ == "__main__":
    main()
