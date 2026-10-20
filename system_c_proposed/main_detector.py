"""
System C: proposed multi-signal detector.
Layers: descriptor (what the device claims) + timing (how fast it types)
        + content (what it types) -> risk score -> allow / alert / block.
It decides AS KEYS ARRIVE, so it can block earlier than System B.

Run (log only):      sudo venv/bin/python system_c_proposed/main_detector.py
Run (really blocks): sudo venv/bin/python system_c_proposed/main_detector.py --enforce
(Stop System A and B first.)
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
from common.device_info import grab_releasing_keys, hexid, read_input_device  # noqa: E402
from common.keystrokes import MODIFIERS, is_keyboard_like, read_all_events  # noqa: E402
from common.logger import log_event  # noqa: E402
from content_analyzer import ContentAnalyzer  # noqa: E402
from descriptor_analyzer import analyze_descriptor  # noqa: E402
from risk_engine import compute  # noqa: E402

SYSTEM = "C-proposed"


def drain(dev, seconds):
    out, end = [], time.time() + seconds
    while time.time() < end:
        batch, gone = read_all_events(dev, end - time.time())
        out.extend(batch)
        if gone:
            break
    return out


def block_device(dev, usb_parent):
    """Returns key events that were still queued when the grab happened."""
    queued = grab_releasing_keys(dev)  # keystrokes stop reaching the system, no key left stuck
    if usb_parent is not None:  # real USB hardware: also deauthorize it
        try:
            with open(os.path.join(usb_parent.sys_path, "authorized"), "w") as f:
                f.write("0")
        except OSError:
            pass
    return queued


def watch_device(node, udev_dev, cfg, whitelist, enforce):
    pc = cfg["proposed"]
    dev = read_input_device(node)
    if dev is None:
        return
    try:
        if not is_keyboard_like(dev):
            return
        name = dev.name
        vid, pid = hexid(dev.info.vendor), hexid(dev.info.product)

        d_points, d_reasons, usb_parent = analyze_descriptor(udev_dev, dev, node, whitelist, pc)
        log_event(SYSTEM, "input", name, vid, pid, "WATCHING",
                  f"descriptor score {d_points}: " + ("; ".join(d_reasons) or "no flags"))

        analyzer = ContentAnalyzer(pc["keywords"])
        times = []
        total, reasons = compute(d_points, d_reasons, times, analyzer, pc)
        deadline = time.time() + pc["watch_s"]

        while total < pc["block_score"]:
            batch, gone = read_all_events(dev, deadline - time.time())
            for ts, code, val in batch:
                analyzer.feed(code, val)
                if val == 1 and code not in MODIFIERS:
                    times.append(ts)
            if batch:
                total, reasons = compute(d_points, d_reasons, times, analyzer, pc)
            if gone or time.time() >= deadline:
                break

        summary = f"score {total} after {len(times)} keys: " + "; ".join(reasons)

        if total >= pc["block_score"]:
            if not enforce:
                log_event(SYSTEM, "input", name, vid, pid, "WOULD-BLOCK", summary + " (dry run)")
                return
            try:
                queued = block_device(dev, usb_parent)
                t_block = time.time()
            except OSError as err:
                log_event(SYSTEM, "input", name, vid, pid, "ERROR", f"grab failed: {err}")
                return
            log_event(SYSTEM, "input", name, vid, pid, "BLOCK", summary + " (grabbed)")
            later = drain(dev, 1.5)
            extra = [ts for ts, code, val in queued + later if val == 1 and code not in MODIFIERS]
            leaked = sum(1 for ts in times + extra if ts <= t_block)
            latency = f"{(t_block - times[0]) * 1000:.0f} ms from first key" if times else "at plug-in, before any key"
            log_event(SYSTEM, "input", name, vid, pid, "INFO",
                      f"block latency {latency}; {leaked} key presses leaked before block")
            while True:  # keep it grabbed until unplugged
                _, gone = read_all_events(dev, 1.0)
                if gone:
                    break
            return

        if not times:
            log_event(SYSTEM, "input", name, vid, pid, "NO-DATA", summary + " (no keys typed)")
        elif total >= pc["alert_score"]:
            log_event(SYSTEM, "input", name, vid, pid, "ALERT", summary + " (suspicious, not blocked)")
        else:
            log_event(SYSTEM, "input", name, vid, pid, "ALLOW", summary)
    finally:
        try:
            dev.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true", help="really block devices")
    args = ap.parse_args()
    with open(os.path.join(BASE, "common", "config.json")) as f:
        cfg = json.load(f)
    whitelist = set(cfg["whitelist"])
    pc = cfg["proposed"]
    print(f"System C started. Enforce: {args.enforce}. Alert at {pc['alert_score']}, block at {pc['block_score']}.")
    print("Watching for new keyboard-like devices... (Ctrl+C to stop)")

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("input")
    try:
        for device in iter(monitor.poll, None):
            node = device.device_node
            if device.action == "add" and node and node.startswith("/dev/input/event"):
                threading.Thread(target=watch_device,
                                 args=(node, device, cfg, whitelist, args.enforce),
                                 daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
