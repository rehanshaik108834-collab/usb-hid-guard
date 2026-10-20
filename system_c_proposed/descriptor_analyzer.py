"""Layer 1 (descriptor): checks what the device CLAIMS to be, and how that looks."""
import json
import os
import sys

from evdev import InputDevice, list_devices

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from common.device_info import hexid  # noqa: E402


def _sim_overrides(name):
    """Simulated descriptor properties (for software-made devices), keyed by device name."""
    try:
        with open(os.path.join(BASE, "common", "sim_descriptors.json")) as f:
            return json.load(f).get(name, {})
    except Exception:
        return {}


def _physical_device(phys):
    """'usb-0000:00:06.0-1/input1' -> 'usb-0000:00:06.0-1'. One real USB keyboard often shows up as
    several input devices (keys, media keys...) with the same VID:PID and this same prefix.
    Software-made devices have no phys, so they return ''."""
    return phys.rsplit("/input", 1)[0] if phys else ""


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def analyze_descriptor(udev_dev, dev, node, whitelist, pc):
    """Returns (points, reasons, fired, usb_parent). fired = the weight names that applied.
    usb_parent is None for software-made devices."""
    w = pc["weights"]
    vid, pid = hexid(dev.info.vendor), hexid(dev.info.product)
    ident = f"{vid}:{pid}"
    points, reasons, fired = 0, [], set()
    sim = _sim_overrides(dev.name)

    if ident not in whitelist:
        points += w["not_whitelisted"]
        fired.add("not_whitelisted")
        reasons.append(f"VID:PID {ident} not on whitelist (+{w['not_whitelisted']})")
    if ident in pc["attack_board_ids"]:
        points += w["attack_board_id"]
        fired.add("attack_board_id")
        reasons.append(f"VID:PID {ident} matches a known attack board (+{w['attack_board_id']})")

    # Identity collision: another device that is ALREADY connected has the same VID:PID
    # (parts of the same physical device, e.g. a keyboard's media-key interface, do not count).
    me = _physical_device(dev.phys)
    for path in list_devices():
        if path == node:
            continue
        try:
            other = InputDevice(path)
        except OSError:
            continue
        same = (other.info.vendor, other.info.product) == (dev.info.vendor, dev.info.product)
        sibling = bool(me) and _physical_device(other.phys) == me
        other_name = other.name
        other.close()
        if same and not sibling:
            points += w["id_collision"]
            fired.add("id_collision")
            reasons.append(f"VID:PID {ident} already used by connected device '{other_name}' (+{w['id_collision']})")
            break

    usb_parent, classes, serial = None, set(), ""
    if udev_dev is not None:
        try:
            usb_parent = udev_dev.find_parent("usb", "usb_device")
        except Exception:
            usb_parent = None
    if usb_parent is not None:
        serial = _read(os.path.join(usb_parent.sys_path, "serial"))
        for entry in os.listdir(usb_parent.sys_path):
            if ":" in entry:
                cls = _read(os.path.join(usb_parent.sys_path, entry, "bInterfaceClass"))
                if cls:
                    classes.add(cls)

    composite = ("08" in classes and "03" in classes) or sim.get("composite", False)
    tag = " [simulated descriptor]" if sim.get("composite") else ""
    if composite:
        points += w["composite"]
        fired.add("composite")
        reasons.append(f"composite device (storage + keyboard){tag} (+{w['composite']})")
    missing_serial = (usb_parent is not None and not serial) or sim.get("missing_serial", False)
    if missing_serial:
        points += w["missing_serial"]
        fired.add("missing_serial")
        reasons.append(f"missing serial number (+{w['missing_serial']})")
    return points, reasons, fired, usb_parent
