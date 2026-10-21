"""
System C: proposed multi-signal detector, built on USBlock.
Layers: descriptor (what the device claims) + timing (USBlock's rule, unchanged)
        + content (what it types) -> risk score -> allow / alert / block.

At the block score, USBlock's rule is proof (no person types that fast): the device is blocked
and, for real USB hardware, USBlock's reaction runs (unbind, port off, hub on repeat).
Without such proof the device is HELD instead: its keys stop reaching the system and a code is shown
(log, terminal, dashboard). A person reads it and types it on the new keyboard to unlock it; an
injection device cannot see the screen, does not answer, and stays blocked.

The descriptor and content layers judge a new keyboard during its first 30 s (the content layer reads
typed text only then, which limits the privacy cost USBlock's authors warn about). USBlock's rule
keeps running for as long as any keyboard is connected, including keyboards connected before
System C started, so an attack that waits before typing is still caught.

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
from evdev import ecodes as ec, list_devices

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import grab_releasing_keys, hexid, read_input_device  # noqa: E402
from common.keystrokes import MODIFIERS, is_keyboard_like, read_all_events  # noqa: E402
from common.logger import log_event  # noqa: E402
from common.usblock import RES, react  # noqa: E402
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


class Device:
    """One watched keyboard: its identity, its key times and USBlock's detector."""

    def __init__(self, dev, udev_dev, cfg):
        self.dev, self.udev_dev, self.cfg = dev, udev_dev, cfg
        self.name = dev.name
        self.vid, self.pid = hexid(dev.info.vendor), hexid(dev.info.product)
        self.res = RES(self.vid, cfg["timing"])
        self.times, self.usblock = [], None

    def log(self, decision, reason, kind="input"):
        log_event(SYSTEM, kind, self.name, self.vid, self.pid, decision, reason)

    def feed(self, ts, code, val):
        if val == 1:
            if code not in MODIFIERS:
                self.times.append(ts)
            found = self.res.feed(ts, code)
            self.usblock = self.usblock or found

    def block_for_good(self, reason, enforce):
        """Proof of injection: block, run USBlock's reaction, report the leak, keep it blocked."""
        if not enforce:
            self.log("WOULD-BLOCK", reason + " (dry run)")
            return
        try:
            queued, t_block = grab_releasing_keys(self.dev)
        except OSError as err:
            self.log("ERROR", f"grab failed: {err}")
            return
        self.log("BLOCK", reason + " (grabbed)")
        react(self.udev_dev, self.cfg["timing"], lambda d, m: self.log(d, m, "usb"))
        log_leak(self.name, self.vid, self.pid, self.times, queued + drain(self.dev, 1.5), t_block)
        wait_until_unplugged(self.dev)

    def keep_watching(self, enforce):
        """After the first 30 s: USBlock's rule only, for as long as the device is connected."""
        while self.usblock is None:
            batch, gone = read_all_events(self.dev, 1.0)
            for ts, code, val in batch:
                self.feed(ts, code, val)
            if gone:
                return
        self.block_for_good(f"USBlock rule after the first {self.cfg['proposed']['watch_s']} s: {self.usblock}"
                            + f" (+{self.cfg['proposed']['weights']['fast_typing']})", enforce)


def watch_device(node, udev_dev, cfg, whitelist, enforce, existing=False):
    pc = cfg["proposed"]
    raw = read_input_device(node)
    if raw is None:
        return
    try:
        if not is_keyboard_like(raw):
            return
        d = Device(raw, udev_dev, cfg)
        if existing:  # connected before System C started: nothing to judge at plug-in
            d.log("WATCHING", "connected before System C started: USBlock rule only")
            d.keep_watching(enforce)
            return

        d_points, d_reasons, d_fired, usb_parent = analyze_descriptor(udev_dev, raw, node, whitelist, pc)
        d.log("WATCHING", f"descriptor score {d_points}: " + ("; ".join(d_reasons) or "no flags"))

        analyzer = ContentAnalyzer(pc["keywords"])
        total, reasons, fired = compute(d_points, d_reasons, d_fired, None, analyzer, pc)
        deadline = time.time() + pc["watch_s"]
        gone = False
        while total < pc["block_score"]:
            batch, gone = read_all_events(raw, deadline - time.time())
            for ts, code, val in batch:
                analyzer.feed(code, val)
                d.feed(ts, code, val)
            if batch:
                total, reasons, fired = compute(d_points, d_reasons, d_fired, d.usblock, analyzer, pc)
            if gone or time.time() >= deadline:
                break

        summary = f"score {total} after {len(d.times)} keys: " + "; ".join(reasons)

        if total >= pc["block_score"]:
            if has_proof(fired, pc):  # USBlock's rule fired: no person can do this
                d.block_for_good(summary, enforce)
                return
            if not enforce:
                d.log("WOULD-BLOCK", summary + " (dry run, would ask for a code)")
                return
            # Suspicious but not proof: hold the device and ask the person for a code.
            try:
                queued, t_block = grab_releasing_keys(raw)
            except OSError as err:
                d.log("ERROR", f"grab failed: {err}")
                return
            ch = pc.get("challenge", {"digits": 4, "timeout_s": 30})
            code = f"{secrets.randbelow(10 ** ch['digits']):0{ch['digits']}d}"
            d.log("CHALLENGE", summary + f" (held: type {code} on this keyboard within {ch['timeout_s']} s to unlock)")
            print(f"\n    >>> New keyboard '{d.name}' is held. To unlock it, type {code} on it. <<<\n", flush=True)
            passed, gone, later = hold_for_code(raw, code, ch["timeout_s"], t_block)
            log_leak(d.name, d.vid, d.pid, d.times, queued + later, t_block)
            if passed:
                raw.ungrab()
                d.log("ALLOW", summary + " (challenge passed)")
                d.keep_watching(enforce)  # trusted by a person, but USBlock's rule still applies
                return
            why = "device removed" if gone else f"no answer within {ch['timeout_s']} s"
            d.log("BLOCK", summary + f" (challenge failed: {why})")
            if not gone:
                react(udev_dev, cfg["timing"], lambda dec, m: d.log(dec, m, "usb"))
                wait_until_unplugged(raw)
            return

        if not d.times:
            d.log("NO-DATA", summary + " (no keys typed)")
        elif total >= pc["alert_score"]:
            d.log("ALERT", summary + " (suspicious, not blocked)")
        else:
            d.log("ALLOW", summary)
        if not gone:
            d.keep_watching(enforce)
    finally:
        try:
            raw.close()
        except Exception:
            pass


def start(node, udev_dev, cfg, whitelist, enforce, existing=False):
    threading.Thread(target=watch_device, args=(node, udev_dev, cfg, whitelist, enforce, existing),
                     daemon=True).start()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce", action="store_true", help="really block devices")
    args = ap.parse_args()
    with open(os.path.join(BASE, "common", "config.json")) as f:
        cfg = json.load(f)
    whitelist = set(cfg["whitelist"])
    pc = cfg["proposed"]
    print(f"System C started. Enforce: {args.enforce}. Alert at {pc['alert_score']}, block at {pc['block_score']}.")
    context = pyudev.Context()
    for node in list_devices():  # USBlock's rule covers keyboards that are already connected too
        try:
            udev_dev = pyudev.Devices.from_device_file(context, node)
        except Exception:
            udev_dev = None
        start(node, udev_dev, cfg, whitelist, args.enforce, existing=True)
    print("Watching every keyboard-like device... (Ctrl+C to stop)")

    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("input")
    try:
        for device in iter(monitor.poll, None):
            node = device.device_node
            if device.action == "add" and node and node.startswith("/dev/input/event"):
                start(node, device, cfg, whitelist, args.enforce)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
