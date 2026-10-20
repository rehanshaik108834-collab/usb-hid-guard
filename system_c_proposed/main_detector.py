"""
System C: proposed multi-signal detector.
Layers: descriptor (what the device claims) + timing (how fast it types)
        + content (what it types) -> risk score -> allow / alert / block.
It decides AS KEYS ARRIVE, so it can block earlier than System B.

At the block score, machine-speed typing is proof (no person types that fast): the device is blocked.
Without such proof the device is HELD instead: its keys stop reaching the system and a code is shown
(log, terminal, dashboard). A person reads it and types it on the new keyboard to unlock it; an
injection device cannot see the screen, does not answer, and stays blocked.

Run (log only):      sudo venv/bin/python system_c_proposed/main_detector.py
Run (really blocks): sudo venv/bin/python system_c_proposed/main_detector.py --enforce
(Stop System A and B first.)
"""
import argparse
import json
import os
import secrets
import sys
import threading
import time

import pyudev
from evdev import ecodes as ec

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import grab_releasing_keys, hexid, read_input_device  # noqa: E402
from common.keystrokes import MODIFIERS, is_keyboard_like, read_all_events  # noqa: E402
from common.logger import log_event  # noqa: E402
from content_analyzer import ContentAnalyzer  # noqa: E402
from descriptor_analyzer import analyze_descriptor  # noqa: E402
from risk_engine import compute, has_proof  # noqa: E402

SYSTEM = "C-proposed"
DIGITS = {getattr(ec, f"KEY_{d}"): d for d in "0123456789"}
DIGITS.update({getattr(ec, f"KEY_KP{d}"): d for d in "0123456789"})


def drain(dev, seconds):
    out, end = [], time.time() + seconds
    while time.time() < end:
        batch, gone = read_all_events(dev, end - time.time())
        out.extend(batch)
        if gone:
            break
    return out


def switch_off(usb_parent, name=None, vid=None, pid=None):
    """Real USB hardware: deauthorize it, so the device is disconnected from its drivers.
    With a name, the outcome is logged (software-made devices have no USB parent: nothing to log)."""
    if usb_parent is None:
        return
    try:
        with open(os.path.join(usb_parent.sys_path, "authorized"), "w") as f:
            f.write("0")
        if name:
            log_event(SYSTEM, "usb", name, vid, pid, "INFO",
                      f"USB device {usb_parent.sys_name} switched off (authorized = 0)")
    except OSError as err:
        if name:
            log_event(SYSTEM, "usb", name, vid, pid, "ERROR", f"could not switch off USB device: {err}")


def block_device(dev, usb_parent, deauthorize=True, who=()):
    """Returns (key events still queued at the grab, block time). A held device is grabbed but
    not deauthorized, so its keys can still be read for the code check."""
    queued, t_block = grab_releasing_keys(dev)  # keystrokes stop reaching the system, no key left stuck
    if deauthorize:
        switch_off(usb_parent, *who)
    return queued, t_block


def hold_for_code(dev, code, timeout, t_block):
    """Reads the held device until the code is typed on it. Returns (passed, gone, events read)."""
    typed, events, deadline = "", [], time.time() + timeout
    while time.time() < deadline:
        batch, gone = read_all_events(dev, deadline - time.time())
        events.extend(batch)
        for ts, code_, val in batch:
            if val == 1 and ts > t_block and code_ in DIGITS:
                typed = (typed + DIGITS[code_])[-len(code):]
                if typed == code:
                    return True, False, events
        if gone:
            return False, True, events
    return False, False, events


def log_leak(name, vid, pid, times, events, t_block):
    extra = [ts for ts, code, val in events if val == 1 and code not in MODIFIERS]
    leaked = sum(1 for ts in times + extra if ts <= t_block)
    latency = f"{(t_block - times[0]) * 1000:.0f} ms from first key" if times else "at plug-in, before any key"
    log_event(SYSTEM, "input", name, vid, pid, "INFO",
              f"block latency {latency}; {leaked} key presses leaked before block")


def wait_until_unplugged(dev):
    while True:
        _, gone = read_all_events(dev, 1.0)
        if gone:
            return


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

        d_points, d_reasons, d_fired, usb_parent = analyze_descriptor(udev_dev, dev, node, whitelist, pc)
        log_event(SYSTEM, "input", name, vid, pid, "WATCHING",
                  f"descriptor score {d_points}: " + ("; ".join(d_reasons) or "no flags"))

        analyzer = ContentAnalyzer(pc["keywords"])
        times = []
        total, reasons, fired = compute(d_points, d_reasons, d_fired, times, analyzer, pc)
        deadline = time.time() + pc["watch_s"]

        while total < pc["block_score"]:
            batch, gone = read_all_events(dev, deadline - time.time())
            for ts, code, val in batch:
                analyzer.feed(code, val)
                if val == 1 and code not in MODIFIERS:
                    times.append(ts)
            if batch:
                total, reasons, fired = compute(d_points, d_reasons, d_fired, times, analyzer, pc)
            if gone or time.time() >= deadline:
                break

        summary = f"score {total} after {len(times)} keys: " + "; ".join(reasons)

        if total >= pc["block_score"]:
            proof = has_proof(fired, pc)
            if not enforce:
                note = "" if proof else ", would ask for a code"
                log_event(SYSTEM, "input", name, vid, pid, "WOULD-BLOCK", summary + f" (dry run{note})")
                return
            try:
                queued, t_block = block_device(dev, usb_parent, deauthorize=proof, who=(name, vid, pid))
            except OSError as err:
                log_event(SYSTEM, "input", name, vid, pid, "ERROR", f"grab failed: {err}")
                return

            if proof:  # machine-speed typing: no person can do this, block for good
                log_event(SYSTEM, "input", name, vid, pid, "BLOCK", summary + " (grabbed)")
                log_leak(name, vid, pid, times, queued + drain(dev, 1.5), t_block)
                wait_until_unplugged(dev)
                return

            # Suspicious but not proof: hold the device and ask the person for a code.
            ch = pc.get("challenge", {"digits": 4, "timeout_s": 30})
            code = f"{secrets.randbelow(10 ** ch['digits']):0{ch['digits']}d}"
            log_event(SYSTEM, "input", name, vid, pid, "CHALLENGE",
                      summary + f" (held: type {code} on this keyboard within {ch['timeout_s']} s to unlock)")
            print(f"\n    >>> New keyboard '{name}' is held. To unlock it, type {code} on it. <<<\n", flush=True)
            passed, gone, later = hold_for_code(dev, code, ch["timeout_s"], t_block)
            log_leak(name, vid, pid, times, queued + later, t_block)
            if passed:
                dev.ungrab()
                log_event(SYSTEM, "input", name, vid, pid, "ALLOW", summary + " (challenge passed)")
                return  # a person answered: the keyboard is trusted from now on
            why = "device removed" if gone else f"no answer within {ch['timeout_s']} s"
            log_event(SYSTEM, "input", name, vid, pid, "BLOCK", summary + f" (challenge failed: {why})")
            switch_off(usb_parent, name, vid, pid)
            if not gone:
                wait_until_unplugged(dev)
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
