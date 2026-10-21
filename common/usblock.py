"""USBlock (Neuner et al., IFIP DBSec 2018): the rapid event sequence (RES) rule and its reaction.
Shared by System B (the re-implementation) and System C (which keeps the rule unchanged).

Rule (paper Sec. 3.4): a RES is s consecutive keypresses, each arriving less than t after the
one before (t = 20 ms, s = 3). It is checked on every keypress for as long as the device is
connected (Sec. 3.5). Yubico devices (Sec. 3.6): the RES rule is off; every key must be MODHEX.

Reaction (Sec. 3.4 and 4.1), for real USB hardware: unbind the device's drivers (authorized = 0)
and switch off the power of its USB port for 10 s. If the same port attacks again (the driver was
bound again), switch off the hub the device hangs on for 10 s instead, and keep doing so until an
administrator steps in. Software-made (uinput) devices have no USB port; they are only grabbed.
"""
import os
import threading
import time

from evdev import ecodes as ec

from common.keystrokes import MODIFIERS


class RES:
    """Rapid-event-sequence detector for one device. feed() returns a reason when the device
    must be blocked, otherwise None."""

    def __init__(self, vid, cfg):
        self.t_ms, self.s = cfg["threshold_ms"], cfg["sequence"]
        self.yubikey = vid in cfg["yubico_vids"]
        self.modhex = ({getattr(ec, f"KEY_{c.upper()}") for c in cfg["modhex"]} | {ec.KEY_ENTER, ec.KEY_KPENTER}
                       if self.yubikey else set())
        self.last, self.gaps, self.keys, self.longest = None, [], 0, 0

    def feed(self, ts, code):
        if code in MODIFIERS:
            return None
        self.keys += 1
        if self.yubikey:
            if code not in self.modhex:
                return f"YubiKey ID sent a non-MODHEX key {ec.KEY.get(code, code)} after {self.keys} keys"
            return None
        if self.last is not None:
            gap = 1000.0 * (ts - self.last)
            self.gaps = self.gaps + [gap] if gap < self.t_ms else []
            self.longest = max(self.longest, len(self.gaps))
        self.last = ts
        if len(self.gaps) >= self.s:
            shown = ", ".join(f"{g:.1f}" for g in self.gaps[-self.s:])
            return (f"rapid event sequence: {self.s} gaps in a row under {self.t_ms} ms "
                    f"({shown} ms) after {self.keys} keys")
        return None


def usb_device(udev_dev):
    """The USB device (sysfs) behind an input device, or None for a software-made device."""
    try:
        return udev_dev.find_parent("usb", "usb_device") if udev_dev is not None else None
    except Exception:
        return None


def _write(path, value):
    with open(path, "w") as f:
        f.write(value)


def _later(seconds, path, value):
    def run():
        try:
            _write(path, value)
        except OSError:
            pass
    timer = threading.Timer(seconds, run)
    timer.daemon = True
    timer.start()


_offenders = {}   # USB port path -> (times blocked, time of the last block)
_lock = threading.Lock()


def react(udev_dev, cfg, log):
    """USBlock's reaction for real USB hardware. log(decision, message) records each step.
    Returns True if a USB device was switched off."""
    dev = usb_device(udev_dev)
    if dev is None:
        return False
    off_s = cfg.get("port_off_s", 10)
    try:
        _write(os.path.join(dev.sys_path, "authorized"), "0")
        log("INFO", f"USB device {dev.sys_name} switched off (authorized = 0, drivers unbound)")
    except OSError as err:
        log("ERROR", f"could not switch off USB device {dev.sys_name}: {err}")
        return False

    port = os.path.realpath(os.path.join(dev.sys_path, "port"))
    if not os.path.isfile(os.path.join(port, "disable")):
        return True
    now = time.time()
    with _lock:
        count, last = _offenders.get(port, (0, 0.0))
        count = count + 1 if now - last < cfg.get("repeat_window_s", 120) else 1
        _offenders[port] = (count, now)
    hub = usb_device(dev) if count > 1 else None  # find_parent starts above dev: its hub
    if hub is not None:  # the device came back and attacked again: switch off the whole hub
        try:
            _write(os.path.join(hub.sys_path, "authorized"), "0")
            _later(off_s, os.path.join(hub.sys_path, "authorized"), "1")
            log("INFO", f"repeated attack (#{count}) on USB port {os.path.basename(port)}: hub {hub.sys_name} "
                        f"switched off for {off_s} s; administrator attention needed")
            return True
        except OSError as err:
            log("ERROR", f"could not switch off hub {hub.sys_name}: {err}")
    try:
        _write(os.path.join(port, "disable"), "1")
        _later(off_s, os.path.join(port, "disable"), "0")
        log("INFO", f"USB port {os.path.basename(port)} powered off for {off_s} s")
    except OSError as err:
        log("ERROR", f"could not power off USB port {os.path.basename(port)}: {err}")
    return True
