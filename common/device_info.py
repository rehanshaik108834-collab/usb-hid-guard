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


def _release(dev, held):
    for code in held:
        dev.write(e.EV_KEY, code, 0)
    if held:
        dev.syn()


def grab_releasing_keys(dev, tries=3):
    """Grab the device so its keys stop reaching the system. Returns (queued events, block time).
    A key held down at the moment of the grab would never get its key-up through, so the desktop
    would keep repeating it. So held keys are released (key-up injected) just BEFORE the grab.
    Asking the kernel which keys are held throws away key events still queued for us, so those
    are read first and returned; the caller must count them (they reached the system)."""
    queued = _read_queued(dev)
    _release(dev, dev.active_keys())
    dev.grab()
    t_block = time.time()
    # Rare: a key pressed in the instant between the release and the grab is still held.
    for _ in range(tries):
        queued += _read_queued(dev)
        held = dev.active_keys()
        if not held:
            break
        dev.ungrab()  # the device is open again for a moment, so the block time moves too
        _release(dev, held)
        dev.grab()
        t_block = time.time()
    return queued, t_block


def hexid(number):
    return f"{number:04x}"
