import time
from evdev import InputDevice


def read_input_device(devnode, retries=15):
    """Open /dev/input/eventX. The node can take a moment to appear, so retry."""
    for _ in range(retries):
        try:
            return InputDevice(devnode)
        except (FileNotFoundError, PermissionError, OSError):
            time.sleep(0.1)
    return None


def hexid(number):
    return f"{number:04x}"
