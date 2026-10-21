"""
System B: re-implementation of USBlock (Neuner et al., IFIP DBSec 2018), the base paper.
A keyboard is blocked as soon as it produces a rapid event sequence (RES): s consecutive
keypresses, each arriving less than t after the one before (t = 20 ms, s = 3). The rule is
checked on every keypress of every connected keyboard, including those already connected when
System B starts, for as long as they stay connected. Device IDs are ignored, except for Yubico
security keys: for them the RES rule is off and every typed key must be MODHEX instead.
Blocking is immediate and never asks the user; real USB hardware is also unbound and its port
powered off for 10 s, escalating to the whole hub if the same port attacks again (common/usblock.py).

Run (log only):      sudo venv/bin/python system_b_timing/timing_detector.py
Run (really blocks): sudo venv/bin/python system_b_timing/timing_detector.py --enforce
"""
import argparse
import json
import os
import sys
import threading

import pyudev
from evdev import list_devices

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import grab_releasing_keys, hexid, read_input_device  # noqa: E402
from common.keystrokes import drain_keydowns, is_keyboard_like, read_batch, MODIFIERS  # noqa: E402
from common.logger import log_event  # noqa: E402
from common.usblock import RES, react  # noqa: E402

SYSTEM = "B-timing"


def load_config():
    with open(os.path.join(BASE, "common", "config.json")) as f:
        return json.load(f)["timing"]


def watch_device(node, udev_dev, cfg, enforce, existing=False):
    dev = read_input_device(node)
    if dev is None:
        return
    try:
        if not is_keyboard_like(dev):
            return
        name = dev.name
        vid, pid = hexid(dev.info.vendor), hexid(dev.info.product)
        res = RES(vid, cfg)
        rule = ("YubiKey: RES rule off, every key must be MODHEX" if res.yubikey
                else f"RES rule: {res.s} gaps in a row under {res.t_ms} ms, checked on every keypress")
        log_event(SYSTEM, "input", name, vid, pid, "WATCHING",
                  rule + (" (connected before System B started)" if existing else ""))

        events, times, reason = [], [], None
        while reason is None:
            batch, gone = read_batch(dev, 1.0)
            for ts, code in batch:
                events.append((ts, code))
                if code not in MODIFIERS:
                    times.append(ts)
                reason = res.feed(ts, code)
                if reason:
                    break
            if gone:
                break

        if reason is None:  # removed without ever producing a RES
            if not times:
                log_event(SYSTEM, "input", name, vid, pid, "NO-DATA", "no key presses before removal")
            elif res.yubikey:
                log_event(SYSTEM, "input", name, vid, pid, "ALLOW", f"YubiKey: all {len(times)} keys were MODHEX")
            else:
                log_event(SYSTEM, "input", name, vid, pid, "ALLOW",
                          f"no rapid event sequence over {len(times)} keys "
                          f"(longest run of gaps under {res.t_ms} ms: {res.longest})")
            return

        if not enforce:
            log_event(SYSTEM, "input", name, vid, pid, "WOULD-BLOCK", reason + " (dry run)")
            return
        try:
            queued, t_block = grab_releasing_keys(dev)
        except OSError as err:
            log_event(SYSTEM, "input", name, vid, pid, "ERROR", f"grab failed: {err}")
            return
        log_event(SYSTEM, "input", name, vid, pid, "BLOCK", reason + " (grabbed)")
        react(udev_dev, cfg, lambda dec, msg: log_event(SYSTEM, "usb", name, vid, pid, dec, msg))

        # Count how many key presses got through before the block took effect.
        later = drain_keydowns(dev, 1.5)
        queued = [(t, c) for t, c, v in queued if v == 1]
        all_times = [t for t, c in events + queued + later if c not in MODIFIERS]
        leaked = sum(1 for t in all_times if t <= t_block)
        latency_ms = (t_block - times[0]) * 1000
        log_event(SYSTEM, "input", name, vid, pid, "INFO",
                  f"block latency {latency_ms:.0f} ms from first key; "
                  f"{leaked} of {len(all_times)} key presses leaked before block")

        while True:  # keep it blocked until it is unplugged
            _, gone = read_batch(dev, 1.0)
            if gone:
                break
    finally:
        try:
            dev.close()
        except Exception:
            pass


def start(node, udev_dev, cfg, enforce, existing=False):
    threading.Thread(target=watch_device, args=(node, udev_dev, cfg, enforce, existing), daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true", help="really block devices")
    args = ap.parse_args()
    cfg = load_config()

    print(f"System B (USBlock) started. Enforce: {args.enforce}. Rule: {cfg['sequence']} gaps in a row "
          f"under {cfg['threshold_ms']} ms -> block (checked on every keypress)")
    context = pyudev.Context()
    # USBlock monitors every connected keyboard, not only new ones.
    for node in list_devices():
        try:
            udev_dev = pyudev.Devices.from_device_file(context, node)
        except Exception:
            udev_dev = None
        start(node, udev_dev, cfg, args.enforce, existing=True)
    print("Watching every keyboard-like device... (Ctrl+C to stop)")

    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("input")
    try:
        for device in iter(monitor.poll, None):
            node = device.device_node
            if device.action == "add" and node and node.startswith("/dev/input/event"):
                start(node, device, cfg, args.enforce)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
