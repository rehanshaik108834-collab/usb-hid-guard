"""
System A: Baseline USB monitor (identity-based, like USBGuard).
Decision rule: device VID:PID on whitelist -> ALLOW, otherwise BLOCK.
No behaviour checking at all. That is its weakness.

Run (dry run, only logs):   sudo venv/bin/python system_a_baseline/baseline_monitor.py
Run (really blocks):        sudo venv/bin/python system_a_baseline/baseline_monitor.py --enforce
"""
import argparse
import json
import os
import sys

import pyudev
from evdev import InputDevice, list_devices

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import hexid, read_input_device  # noqa: E402
from common.logger import log_event  # noqa: E402

SYSTEM = "A-baseline"
held = {}  # blocked input devices we keep grabbed


def load_whitelist():
    with open(os.path.join(BASE, "common", "config.json")) as f:
        return set(json.load(f)["whitelist"])


def attr(device, name):
    try:
        return device.attributes.asstring(name)
    except Exception:
        return None


def handle_input(device, whitelist, enforce):
    node = device.device_node
    if not node or not node.startswith("/dev/input/event"):
        return
    dev = read_input_device(node)
    if dev is None:
        log_event(SYSTEM, "input", node, "????", "????", "ERROR", "could not open device")
        return
    vid, pid = hexid(dev.info.vendor), hexid(dev.info.product)
    if f"{vid}:{pid}" in whitelist:
        log_event(SYSTEM, "input", dev.name, vid, pid, "ALLOW", "VID:PID on whitelist")
        dev.close()
        return
    if enforce:
        try:
            dev.grab()  # stops this device's keystrokes reaching the system
            held[node] = dev
            log_event(SYSTEM, "input", dev.name, vid, pid, "BLOCK", "not on whitelist (grabbed)")
        except OSError as err:
            log_event(SYSTEM, "input", dev.name, vid, pid, "ERROR", f"grab failed: {err}")
    else:
        log_event(SYSTEM, "input", dev.name, vid, pid, "WOULD-BLOCK", "not on whitelist (dry run)")
        dev.close()


def handle_usb(device, whitelist, enforce):
    vid, pid = attr(device, "idVendor"), attr(device, "idProduct")
    if not vid or not pid:
        return
    if attr(device, "bDeviceClass") == "09":  # skip USB hubs
        return
    name = attr(device, "product") or "unknown USB device"
    if f"{vid}:{pid}" in whitelist:
        log_event(SYSTEM, "usb", name, vid, pid, "ALLOW", "VID:PID on whitelist")
        return
    if enforce:
        try:
            with open(os.path.join(device.sys_path, "authorized"), "w") as f:
                f.write("0")
            log_event(SYSTEM, "usb", name, vid, pid, "BLOCK", "not on whitelist (authorized=0)")
        except OSError as err:
            log_event(SYSTEM, "usb", name, vid, pid, "ERROR", f"block failed: {err}")
    else:
        log_event(SYSTEM, "usb", name, vid, pid, "WOULD-BLOCK", "not on whitelist (dry run)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true", help="really block devices")
    args = parser.parse_args()
    whitelist = load_whitelist()

    print(f"System A started. Enforce mode: {args.enforce}. Whitelist size: {len(whitelist)}")
    for path in list_devices():  # devices already present at startup
        d = InputDevice(path)
        log_event(SYSTEM, "input", d.name, hexid(d.info.vendor), hexid(d.info.product),
                  "EXISTING", "present at startup, not checked")
        d.close()

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by("input")
    monitor.filter_by("usb")
    print("Watching for new devices... (Ctrl+C to stop)")
    try:
        for device in iter(monitor.poll, None):
            if device.action == "add":
                if device.subsystem == "input":
                    handle_input(device, whitelist, args.enforce)
                elif device.subsystem == "usb" and device.device_type == "usb_device":
                    handle_usb(device, whitelist, args.enforce)
            elif device.action == "remove":
                if device.subsystem == "input" and device.device_node:
                    held.pop(device.device_node, None)
                    log_event(SYSTEM, "input", device.device_node, "----", "----", "REMOVED", "")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
