"""Shared helpers: read key-down events from an input device and measure typing speed."""
import select
import statistics
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


def collect_keydowns(dev, min_keys=10, timeout=20.0):
    """Collect key-downs until `min_keys` non-modifier keys were seen, or timeout."""
    events, typed = [], 0
    deadline = time.time() + timeout
    while typed < min_keys:
        batch, gone = read_batch(dev, deadline - time.time())
        for item in batch:
            events.append(item)
            if item[1] not in MODIFIERS:
                typed += 1
        if gone or time.time() >= deadline:
            break
    return events


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


def analyze(events):
    """Typing statistics from key-down events (modifier keys excluded from timing)."""
    times = [t for t, code in events if code not in MODIFIERS]
    if len(times) < 2:
        return None
    gaps = [1000.0 * (b - a) for a, b in zip(times, times[1:])]
    span = times[-1] - times[0]
    return {
        "keys": len(times),
        "median_ms": statistics.median(gaps),
        "mean_ms": statistics.mean(gaps),
        "min_ms": min(gaps),
        "keys_per_sec": (len(times) - 1) / span if span > 0 else float("inf"),
    }


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
