import time
from evdev import InputDevice, ecodes as e


def read_input_device(devnode, retries=15):
    """Open /dev/input/eventX. The node can take a moment to appear, so retry."""
    for _ in range(retries):
        try:
            return InputDevice(devnode)
        except (FileNotFoundError, PermissionError, OSError):
            time.sleep(0.1)
    return None


def _read_queued(dev):
    """Key events (timestamp, keycode, value) already waiting in our queue, without blocking."""
    out = []
    try:
        for ev in dev.read():
            if ev.type == e.EV_KEY and ev.value in (0, 1):
                out.append((ev.timestamp(), ev.code, ev.value))
    except (BlockingIOError, OSError):
        pass
    return out


def _send_releases(dev, ups, taps):
    """ups: keys still held down -> inject a key-up.
    taps: keys whose real key-up was swallowed by the grab (Linux already counts them as up, so a
    lone key-up would be dropped) -> inject key-down + key-up. The desktop ignores a key-down for a
    key it already thinks is pressed, so only the key-up has an effect."""
    for code in ups:
        dev.write(e.EV_KEY, code, 0)
        dev.syn()
    for code in taps:
        dev.write(e.EV_KEY, code, 1)
        dev.syn()
        dev.write(e.EV_KEY, code, 0)
        dev.syn()


def grab_releasing_keys(dev, tries=3):
    """Grab the device so its keys stop reaching the system. Returns (queued events, block time).
    A key that is down when the grab happens would never get its key-up through, so the desktop
    would keep repeating it. Held keys are therefore released just BEFORE the grab. After the
    grab, the key events the desktop could still have seen are checked, and any key it still
    thinks is pressed is released too (rare: a key pressed in the instant before the grab).
    Asking the kernel which keys are held throws away key events still queued for us, so those
    are always read first and returned; the caller must count them (they reached the system)."""
    queued = _read_queued(dev)
    _send_releases(dev, dev.active_keys(), [])
    t_open = float("-inf")  # start of the time the desktop was receiving this device's keys
    grabbed = False
    for _ in range(tries):
        t_sure = time.time()   # events up to here certainly reached the desktop
        dev.grab()
        grabbed = True
        t_block = time.time()  # events after here certainly did not
        new = _read_queued(dev)
        queued += new
        last = {}  # key -> (value, time) of its last event the desktop may have received
        for ts, code, val in new:
            if t_open <= ts <= t_block:
                last[code] = (val, ts)
        # Keys the desktop may still think are pressed: the last event it could have seen is a
        # key-down, or a key-up that came so close to the grab that it may have been swallowed.
        # Releasing a key the desktop did not have pressed costs at most that one attacker key.
        maybe_down = [c for c, (val, ts) in last.items() if val == 1 or ts > t_sure]
        if not maybe_down:
            break
        held = set(dev.active_keys())
        ups = [c for c in maybe_down if c in held]
        taps = [c for c in maybe_down if c not in held]
        t_open = time.time()
        dev.ungrab()  # open for a moment to send the key-ups; the block time moves with it
        grabbed = False
        _send_releases(dev, ups, taps)
    if not grabbed:
        dev.grab()
        t_block = time.time()
    return queued, t_block


def hexid(number):
    return f"{number:04x}"
