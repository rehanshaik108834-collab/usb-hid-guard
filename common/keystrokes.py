"""Shared helpers: read key-down events from an input device and measure typing speed."""
import select
import time

from evdev import ecodes as e

MODIFIERS = {
    e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL,
    e.KEY_LEFTALT, e.KEY_RIGHTALT, e.KEY_LEFTMETA, e.KEY_RIGHTMETA, e.KEY_CAPSLOCK,
}
LETTERS = {getattr(e, f"KEY_{c}") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
DIGITS = {getattr(e, f"KEY_{c}") for c in "1234567890"}


def is_keyboard_like(dev):
    """True if the input device has letter keys (so mice, buttons, tablets are ignored)."""
    keys = set(dev.capabilities().get(e.EV_KEY, []))
    return bool(keys & (LETTERS | DIGITS))


def read_batch(dev, timeout):
    """Wait up to `timeout` seconds. Returns (list of (timestamp, keycode), device_gone)."""
    try:
        ready, _, _ = select.select([dev.fd], [], [], max(0.0, timeout))
    except (OSError, ValueError):
        return [], True
    if not ready:
        return [], False
    out = []
    try:
        for ev in dev.read():
            if ev.type == e.EV_KEY and ev.value == 1:  # key-down only
                out.append((ev.timestamp(), ev.code))
    except BlockingIOError:
        pass
    except OSError:
        return out, True  # device unplugged
    return out, False


def drain_keydowns(dev, seconds):
    """Keep reading for `seconds`; returns the extra key-down events."""
    events = []
    end = time.time() + seconds
    while time.time() < end:
        batch, gone = read_batch(dev, end - time.time())
        events.extend(batch)
        if gone:
            break
    return events


def read_all_events(dev, timeout):
    """Like read_batch, but returns (timestamp, keycode, value) for key-down (1) AND key-up (0)."""
    try:
        ready, _, _ = select.select([dev.fd], [], [], max(0.0, timeout))
    except (OSError, ValueError):
        return [], True
    if not ready:
        return [], False
    out = []
    try:
        for ev in dev.read():
            if ev.type == e.EV_KEY and ev.value in (0, 1):
                out.append((ev.timestamp(), ev.code, ev.value))
    except BlockingIOError:
        pass
    except OSError:
        return out, True
    return out, False
