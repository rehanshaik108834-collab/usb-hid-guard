"""Usage: sudo venv/bin/python attack_sim/make_test_device.py NAME VID PID [SECONDS]"""
import sys
import time
from evdev import UInput, ecodes as e

name = sys.argv[1]
vid = int(sys.argv[2], 16)
pid = int(sys.argv[3], 16)
secs = int(sys.argv[4]) if len(sys.argv) > 4 else 8

ui = UInput({e.EV_KEY: [e.KEY_A, e.KEY_B]}, name=name, vendor=vid, product=pid, bustype=e.BUS_USB)
print(f"Created fake device {name!r} with ID {vid:04x}:{pid:04x} for {secs}s")
time.sleep(secs)
ui.close()
print("Removed.")
