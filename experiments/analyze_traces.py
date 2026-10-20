"""Summarise recorded human typing and plot it against simulated attack timings."""
import glob
import json
import os
import random
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACES = os.path.join(BASE, "attack_sim", "human_traces")

groups = {}
print(f"{'file':28} {'keys':>4} {'avg ms':>7} {'median':>7} {'min':>5} {'<20ms':>6} {'<10ms':>6}")
for path in sorted(glob.glob(os.path.join(TRACES, "*.json"))):
    with open(path) as f:
        data = json.load(f)
    gaps = [g * 1000 for g in data["gaps"]]
    label = os.path.basename(path).rsplit("_", 1)[0]
    groups.setdefault(label, []).extend(gaps)
    under20 = 100 * sum(g < 20 for g in gaps) / len(gaps)
    under10 = 100 * sum(g < 10 for g in gaps) / len(gaps)
    print(f"{os.path.basename(path):28} {len(gaps)+1:>4} {statistics.mean(gaps):>7.0f} "
          f"{statistics.median(gaps):>7.0f} {min(gaps):>5.0f} {under20:>5.0f}% {under10:>5.0f}%")

if not groups:
    raise SystemExit("No recordings found in attack_sim/human_traces")

human = [g for gaps in groups.values() for g in gaps]

print(f"\nAll human gaps: n={len(human)}, median={statistics.median(human):.0f} ms, "
      f"fastest={min(human):.0f} ms, share under 20 ms={100*sum(g<20 for g in human)/len(human):.1f}%")

# Attack timing as MEASURED during the experiment (saved by fake_keyboard.py --save-gaps).
# The barcode scanner types fast too, but it is a legitimate device, so it is left out.
fast_attack, slow_attack = [], []
for path in glob.glob(os.path.join(BASE, "attack_sim", "attack_traces", "*.json")):
    with open(path) as f:
        data = json.load(f)
    if data["name"] == "Barcode Scanner":
        continue
    gaps = [g * 1000 for g in data["gaps"]]
    if data["mode"] == "fast":
        fast_attack += gaps
    elif data["mode"] == "slow":
        slow_attack += gaps
measured = bool(fast_attack and slow_attack)
if measured:
    print(f"Fast attack gaps (measured): n={len(fast_attack)}, median={statistics.median(fast_attack):.1f} ms, "
          f"slowest={max(fast_attack):.1f} ms, share at or above 20 ms="
          f"{100*sum(g>=20 for g in fast_attack)/len(fast_attack):.1f}%")
    print(f"Slow attack gaps (measured): n={len(slow_attack)}, median={statistics.median(slow_attack):.0f} ms")
else:  # no experiment has saved attack timing yet
    random.seed(1)
    fast_attack = [random.gauss(2.0, 0.3) for _ in range(300)]
    slow_attack = [random.uniform(80, 300) for _ in range(300)]
    print("No measured attack timing found (attack_sim/attack_traces); using simulated values.")
kind = "measured" if measured else "simulated"

bins = [2 ** (i / 2) for i in range(-2, 22)]  # log-spaced, about 0.5 ms to 1.5 s
plt.figure(figsize=(9, 5))
plt.hist(human, bins=bins, alpha=0.7, label="Human typing (recorded)")
plt.hist(fast_attack, bins=bins, alpha=0.7, label=f"Fast attack ({kind})")
plt.hist(slow_attack, bins=bins, alpha=0.5, label=f"Slow attack ({kind})")
plt.axvline(20, linestyle="--", color="red", label="20 ms threshold")
plt.xscale("log")
plt.xlabel("Gap between key presses (ms, log scale)")
plt.ylabel("Number of key presses")
plt.title("Inter-key intervals: human vs injected keystrokes")
plt.legend()
plt.tight_layout()
out = os.path.join(BASE, "experiments", "fig_human_vs_attack_hist.png")
plt.savefig(out, dpi=150)
print("Saved", out)
