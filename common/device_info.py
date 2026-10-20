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


def grab_releasing_keys(dev, tries=3):
    """Grab the device so its keys stop reaching the system.
    A key that is held down at that moment would never get its key-up through the grab, so the
    desktop would keep repeating it. Release such keys: briefly ungrab, inject key-ups, grab again.
    Asking the kernel which keys are held throws away key events still queued for us, so those
    are read first and returned; the caller must count them (they reached the system)."""
    dev.grab()
    queued = []
    for _ in range(tries):
        queued += _read_queued(dev)
        held = dev.active_keys()
        if not held:
            break
        dev.ungrab()
        for code in held:
            dev.write(e.EV_KEY, code, 0)
        dev.syn()
        dev.grab()
    return queued


def hexid(number):
    return f"{number:04x}"
