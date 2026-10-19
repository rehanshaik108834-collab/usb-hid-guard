"""
System B: timing-only detector (single behavioural signal).
Ignores VID/PID completely. For any NEW keyboard-like input device it collects the
first N key presses; if the MEDIAN gap between them is below the threshold, it blocks.

Run (log only):    sudo venv/bin/python system_b_timing/timing_detector.py
Run (really blocks): sudo venv/bin/python system_b_timing/timing_detector.py --enforce
"""
import argparse
import json
import os
import sys
import threading
import time

import pyudev

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import hexid, read_input_device  # noqa: E402
from common.keystrokes import (analyze, collect_keydowns, drain_keydowns,  # noqa: E402
                               is_keyboard_like, read_batch, MODIFIERS)
from common.logger import log_event  # noqa: E402

SYSTEM = "B-timing"


def load_timing_config():
    with open(os.path.join(BASE, "common", "config.json")) as f:
        return json.load(f)["timing"]


def watch_device(node, cfg, enforce):
    dev = read_input_device(node)
    if dev is None:
        return
    try:
        if not is_keyboard_like(dev):
            return
        name = dev.name
        vid, pid = hexid(dev.info.vendor), hexid(dev.info.product)
        log_event(SYSTEM, "input", name, vid, pid, "WATCHING",
                  f"waiting for {cfg['min_keys']} key presses")

        events = collect_keydowns(dev, cfg["min_keys"], cfg["timeout_s"])
        stats = analyze(events)
        if stats is None or stats["keys"] < cfg["min_keys"]:
            n = 0 if stats is None else stats["keys"]
            log_event(SYSTEM, "input", name, vid, pid, "NO-DATA",
                      f"only {n} key presses seen, cannot judge")
            return

        median = stats["median_ms"]
        summary = f"median gap {median:.1f} ms over {stats['keys']} keys (threshold {cfg['threshold_ms']} ms)"
        if median >= cfg["threshold_ms"]:
            log_event(SYSTEM, "input", name, vid, pid, "ALLOW", summary)
            return

        if not enforce:
            log_event(SYSTEM, "input", name, vid, pid, "WOULD-BLOCK", summary + " (dry run)")
            return

        try:
            dev.grab()
            t_block = time.time()
        except OSError as err:
            log_event(SYSTEM, "input", name, vid, pid, "ERROR", f"grab failed: {err}")
            return
        log_event(SYSTEM, "input", name, vid, pid, "BLOCK", summary + " (grabbed)")

        # Count how many key presses got through before the block took effect.
        later = drain_keydowns(dev, 1.5)
        all_times = [t for t, c in events + later if c not in MODIFIERS]
        leaked = sum(1 for t in all_times if t <= t_block)
        latency_ms = (t_block - events[0][0]) * 1000
        log_event(SYSTEM, "input", name, vid, pid, "INFO",
                  f"block latency {latency_ms:.0f} ms from first key; "
                  f"{leaked} of {len(all_times)} key presses leaked before block")

        # Keep the device grabbed until it is unplugged.
        while True:
            _, gone = read_batch(dev, 1.0)
            if gone:
                break
    finally:
        try:
            dev.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true", help="really block devices")
    args = ap.parse_args()
    cfg = load_timing_config()

    print(f"System B started. Enforce: {args.enforce}. Rule: median gap of first "
          f"{cfg['min_keys']} keys < {cfg['threshold_ms']} ms -> block")
    print("Watching for new keyboard-like devices... (Ctrl+C to stop)")

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("input")
    try:
        for device in iter(monitor.poll, None):
            node = device.device_node
            if device.action == "add" and node and node.startswith("/dev/input/event"):
                threading.Thread(target=watch_device, args=(node, cfg, args.enforce),
                                 daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
