import time
from evdev import InputDevice, list_devices, UInput, ecodes as e

def show(title):
    print(f"\n{title}")
    for path in list_devices():
        d = InputDevice(path)
        print(f"  {path:20} {d.name:35} VID={d.info.vendor:04x} PID={d.info.product:04x}")

show("Input devices BEFORE:")

cap = {e.EV_KEY: [e.KEY_H, e.KEY_I]}
ui = UInput(cap, name="TestKB", vendor=0x1234, product=0x5678, bustype=e.BUS_USB)
time.sleep(1)

show("Input devices AFTER creating the virtual keyboard (look for TestKB):")
ui.close()
print("\nDone. Virtual keyboard removed.")
