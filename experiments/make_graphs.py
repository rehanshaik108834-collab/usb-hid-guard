"""Summaries and graphs from experiments/results.csv and overhead.csv."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(BASE, "experiments")
df = pd.read_csv(os.path.join(EXP, "results.csv"))
df["blocked"] = df["decision"].isin(["BLOCK", "WOULD-BLOCK"])
df["flagged"] = df["decision"].isin(["BLOCK", "WOULD-BLOCK", "ALERT"])
df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
SYS = [s for s in ["A", "B", "C"] if s in df["system"].unique()]
LABEL = {"A": "A: Baseline (ID only)", "B": "B: Timing-only", "C": "C: Proposed (multi-signal)"}
COLOR = {"A": "#999999", "B": "#e69f00", "C": "#0072b2"}
SHORT = {"S1": "Legit\nkeyboard", "S2": "Unknown\nfast", "S3": "Spoofed\nfast, plain", "S4": "Spoofed\nfast, shell",
         "S5": "Composite\n(simulated)", "S6": "Fast human\ntypist", "S7": "Spoofed\nslow, plain",
         "S8": "Spoofed\nslow, shell", "S9": "Barcode\nscanner", "S10": "Identical\nkeyboard",
         "S11": "Spoofed\nwhitelisted", "S12": "Win+R\nlauncher", "S13": "Digispark\nID",
         "S14": "No serial\n(simulated)"}


def tick(s):
    return f"{s}\n{SHORT.get(s, '')}"
scen_order = sorted(df["scenario"].unique(), key=lambda s: int(s[1:]))
attack = [s for s in scen_order if (df[df.scenario == s]["expected"] == "attack").all()]
legit = [s for s in scen_order if (df[df.scenario == s]["expected"] == "legit").all()]


def pct(series):
    return 100.0 * series.mean()


rows = []
for s in scen_order:
    for sy in SYS:
        d = df[(df.scenario == s) & (df.system == sy)]
        if d.empty:
            continue
        rows.append({"scenario": s, "name": d["scenario_name"].iloc[0], "expected": d["expected"].iloc[0],
                     "system": sy, "runs": len(d), "blocked_%": round(pct(d["blocked"]), 1),
                     "alert_or_block_%": round(pct(d["flagged"]), 1),
                     "mean_leaked_keys": round(d["leaked"].mean(), 1),
                     "mean_latency_ms": round(d.loc[d.blocked, "latency_ms"].mean(), 1) if d.blocked.any() else np.nan})
summary = pd.DataFrame(rows)
summary.to_csv(os.path.join(EXP, "summary_table.csv"), index=False)
print(summary.to_string(index=False))

print("\nOVERALL")
for sy in SYS:
    a = df[(df.system == sy) & (df.scenario.isin(attack))]
    l = df[(df.system == sy) & (df.scenario.isin(legit))]
    print(f"{LABEL[sy]:30} detection (blocked) {pct(a['blocked']):5.1f}% | flagged {pct(a['flagged']):5.1f}% | "
          f"false-positive blocks {pct(l['blocked']):5.1f}% | legit flagged {pct(l['flagged']):5.1f}% | "
          f"mean leaked keys {a['leaked'].mean():.1f}")


def grouped(ax, scens, value_fn, ylabel):
    w = 0.8 / len(SYS)
    x = np.arange(len(scens))
    for k, sy in enumerate(SYS):
        vals = []
        for s in scens:
            d = df[(df.scenario == s) & (df.system == sy)]
            vals.append(value_fn(d) if not d.empty else 0)
        bars = ax.bar(x + k * w - 0.4 + w / 2, vals, w, label=LABEL[sy], color=COLOR[sy])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{v:.0f}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([tick(sc) for sc in scens], fontsize=8)
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=8, loc="upper center", ncol=3)


# Figure 1: detection of attacks
if attack:
    fig, ax = plt.subplots(figsize=(max(10, 1.2 * len(attack)), 5))
    grouped(ax, attack, lambda d: pct(d["blocked"]), "Attacks blocked (%)")
    ax.set_ylim(0, 128)
    ax.set_title("Attack detection rate by system and scenario")
    ax.set_xlabel("Attack scenario")
    plt.tight_layout()
    plt.savefig(os.path.join(EXP, "fig_detection_rate.png"), dpi=150)
    plt.close()

# Figure 2: false positives on legitimate devices
if legit:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    grouped(axes[0], legit, lambda d: pct(d["blocked"]), "Legitimate runs (%)")
    axes[0].set_title("Wrongly BLOCKED")
    grouped(axes[1], legit, lambda d: pct(d["flagged"]), "")
    axes[1].set_title("Flagged (alert or block)")
    for a in axes:
        a.set_ylim(0, 128)
    plt.tight_layout()
    plt.savefig(os.path.join(EXP, "fig_false_positives.png"), dpi=150)
    plt.close()

# Figure 3: keystrokes leaked
if attack:
    fig, ax = plt.subplots(figsize=(max(10, 1.2 * len(attack)), 5))
    grouped(ax, attack, lambda d: d["leaked"].mean(), "Mean keystrokes that reached the system")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.3)
    ax.set_title("Keystrokes leaked before the attack was stopped (lower is better)")
    plt.tight_layout()
    plt.savefig(os.path.join(EXP, "fig_leaked_keys.png"), dpi=150)
    plt.close()

# Figure 4: detection latency
blocked_runs = df[df.blocked & df.latency_ms.notna() & df.system.isin(["B", "C"])]
if not blocked_runs.empty:
    scens = [s for s in attack if s in blocked_runs.scenario.unique()]
    fig, ax = plt.subplots(figsize=(10, 5))
    w = 0.38
    for k, sy in enumerate([x for x in ["B", "C"] if x in SYS]):
        vals = [blocked_runs[(blocked_runs.scenario == s) & (blocked_runs.system == sy)]["latency_ms"].mean() for s in scens]
        vals = [0 if np.isnan(v) else v for v in vals]
        ax.bar(np.arange(len(scens)) + k * w - w / 2, vals, w, label=LABEL[sy], color=COLOR[sy])
    ax.set_xticks(np.arange(len(scens)))
    ax.set_xticklabels([tick(sc) for sc in scens], fontsize=8)
    ax.set_ylabel("Mean time from first key to block (ms)")
    ax.set_title("Detection latency (only runs that were blocked; 0 = blocked at plug-in or never blocked)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(EXP, "fig_latency.png"), dpi=150)
    plt.close()

# Overhead
op = os.path.join(EXP, "overhead.csv")
if os.path.exists(op):
    print("\nRESOURCE OVERHEAD (whole run, includes idle time)")
    print(pd.read_csv(op).to_string(index=False))
print("\nSaved: summary_table.csv and fig_*.png in experiments/")
