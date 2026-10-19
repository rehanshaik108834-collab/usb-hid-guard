"""
Automated experiment runner. MUST run as root (sudo).

Examples:
  sudo venv/bin/python experiments/run_experiments.py --runs 2 --fresh     # quick trial
  sudo venv/bin/python experiments/run_experiments.py --runs 20 --fresh    # full experiment
  sudo venv/bin/python experiments/run_experiments.py --runs 5 --systems C --scenarios S3,S8

Before starting: stop every other detector, open a Text Editor, and be ready to click inside it
when the countdown runs. All typed text is harmless and goes to the focused window.
Do not touch the keyboard or mouse while it runs.
"""
import argparse
import csv
import glob
import os
import re
import subprocess
import sys
import time

import psutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RESULTS = os.path.join(BASE, "experiments", "results.csv")
OVERHEAD = os.path.join(BASE, "experiments", "overhead.csv")
RAW = os.path.join(BASE, "experiments", "raw_logs")
TRACES = os.path.join(BASE, "attack_sim", "human_traces")
FAKE = os.path.join(BASE, "attack_sim", "fake_keyboard.py")
REPLAY = os.path.join(BASE, "attack_sim", "replay_trace.py")
SETTLE = 3.0  # seconds to let detectors finish logging after each run

SYSTEMS = {
    "A": os.path.join(BASE, "system_a_baseline", "baseline_monitor.py"),
    "B": os.path.join(BASE, "system_b_timing", "timing_detector.py"),
    "C": os.path.join(BASE, "system_c_proposed", "main_detector.py"),
}


def traces(pattern):
    files = sorted(glob.glob(os.path.join(TRACES, pattern)))
    return files or sorted(glob.glob(os.path.join(TRACES, "*.json")))


def fake(name, vid, pid, mode, payload="hello", text=None, launcher="none"):
    def build(i):
        cmd = [PY, FAKE, "--name", name, "--vid", vid, "--pid", pid, "--mode", mode, "--wait", "1",
               "--launcher", launcher]
        cmd += ["--text", text] if text else ["--payload", payload]
        return cmd, ""
    return build


def replay(name, vid, pid, pattern):
    def build(i):
        files = traces(pattern)
        f = files[i % len(files)]
        return [PY, REPLAY, "--trace", f, "--name", name, "--vid", vid, "--pid", pid, "--wait", "1"], os.path.basename(f)
    return build


SCENARIOS = {
    "S1": ("Legit keyboard, normal typing", "legit", replay("Legit KB", "046d", "c31c", "*normal*.json")),
    "S2": ("Unknown device, fast attack", "attack", fake("Unknown Board", "dead", "beef", "fast")),
    "S3": ("Fast attack, spoofed ID, plain text", "attack", fake("Spoofed KB", "0001", "0001", "fast")),
    "S4": ("Fast attack, spoofed ID, shell text", "attack", fake("Spoofed KB", "0001", "0001", "fast", "shellish")),
    "S5": ("Composite device (simulated)", "attack", fake("Composite KB", "0001", "0001", "human", "sentence")),
    "S6": ("Fast human typist, legit ID", "legit", replay("Legit KB", "046d", "c31c", "*fast*.json")),
    "S7": ("Slow attack, spoofed ID, plain text", "attack", fake("Spoofed KB", "0001", "0001", "slow")),
    "S8": ("Slow attack, spoofed ID, shell text", "attack", fake("Spoofed KB", "0001", "0001", "slow", "shellish")),
    "S9": ("Barcode scanner (fast, whitelisted)", "legit", fake("Barcode Scanner", "05e0", "1200", "fast", text="4006381333931")),
    "S10": ("Second identical keyboard (same ID)", "legit", replay("Twin KB", "0001", "0001", "*.json")),
    # 046d:c31c is whitelisted but NOT connected, so there is no ID collision to catch it.
    "S11": ("Fast attack, spoofed whitelisted ID (not connected)", "attack", fake("Spoofed Logitech", "046d", "c31c", "fast")),
    "S12": ("Slow attack, spoofed ID, Win+R launcher", "attack", fake("Spoofed KB", "0001", "0001", "slow", launcher="win-r")),
    "S13": ("Digispark board ID, slow typing", "attack", fake("Digispark", "16c0", "27db", "slow")),
    "S14": ("No serial number (simulated), spoofed ID, slow", "attack", fake("No Serial KB", "0001", "0001", "slow")),
}

DEC_RE = re.compile(r"-> (ALLOW|BLOCK|ALERT|NO-DATA|WOULD-BLOCK)\b")
PRIORITY = {"BLOCK": 3, "WOULD-BLOCK": 3, "ALERT": 2, "ALLOW": 1, "NO-DATA": 0}


def parse_log(text):
    """Returns (decision, score, leaked_from_log, latency_ms) from detector log lines of one run."""
    decision, score, leaked, latency = "NONE", "", None, ""
    for line in text.splitlines():
        m = DEC_RE.search(line)
        if m:
            d = m.group(1)
            if PRIORITY[d] >= PRIORITY.get(decision, -1):
                decision = d
                s = re.search(r"\bscore (\d+) after", line)
                if s:
                    score = int(s.group(1))
        elif "-> INFO" in line:
            lk = re.search(r"(\d+) (?:of \d+ )?key presses leaked", line)
            if lk:
                leaked = int(lk.group(1))
            lt = re.search(r"block latency (\d+) ms", line)
            latency = int(lt.group(1)) if lt else (0 if "at plug-in" in line else "")
    return decision, score, leaked, latency


def parse_keys(output):
    m = re.search(r"(?:Typed|Replayed) (\d+) (?:characters|keys)", output)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--systems", default="A,B,C")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--fresh", action="store_true", help="delete old results first")
    args = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("Run with sudo: sudo venv/bin/python experiments/run_experiments.py ...")

    os.makedirs(RAW, exist_ok=True)
    if args.fresh:
        for p in (RESULTS, OVERHEAD):
            if os.path.exists(p):
                os.remove(p)
    new_results = not os.path.exists(RESULTS)
    new_overhead = not os.path.exists(OVERHEAD)
    systems = [s.strip().upper() for s in args.systems.split(",")]
    scen_ids = [s.strip().upper() for s in args.scenarios.split(",")]

    total = len(systems) * len(scen_ids) * args.runs
    print(f"Plan: {len(systems)} systems x {len(scen_ids)} scenarios x {args.runs} runs = {total} runs")
    print("Open a Text Editor and click inside it NOW. Do not touch keyboard/mouse afterwards.")
    for n in range(10, 0, -1):
        print(f"  starting in {n}...", end="\r", flush=True)
        time.sleep(1)
    print()

    rf = open(RESULTS, "a", newline="")
    rw = csv.writer(rf)
    if new_results:
        rw.writerow(["system", "scenario", "scenario_name", "expected", "run", "decision",
                     "score", "latency_ms", "leaked", "keys", "wall_s", "trace"])
    of = open(OVERHEAD, "a", newline="")
    ow = csv.writer(of)
    if new_overhead:
        ow.writerow(["system", "cpu_seconds", "wall_seconds", "avg_cpu_percent", "rss_mb"])

    done = 0
    try:
        for sid in systems:
            logpath = os.path.join(RAW, f"{sid}.log")
            open(logpath, "w").close()
            lf = open(logpath, "a")
            proc = subprocess.Popen([PY, "-u", SYSTEMS[sid], "--enforce"], stdout=lf,
                                    stderr=subprocess.STDOUT, cwd=BASE)
            started = time.time()
            time.sleep(3)
            try:
                for scen in scen_ids:
                    name, expected, build = SCENARIOS[scen]
                    for i in range(args.runs):
                        cmd, trace = build(i)
                        offset = os.path.getsize(logpath)
                        t0 = time.time()
                        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                        time.sleep(SETTLE)
                        wall = time.time() - t0
                        with open(logpath) as f:
                            f.seek(offset)
                            text = f.read()
                        decision, score, leaked, latency = parse_log(text)
                        keys = parse_keys(out.stdout)
                        if decision in ("BLOCK", "WOULD-BLOCK"):
                            leaked = leaked if leaked is not None else 0
                        else:
                            leaked = keys
                        rw.writerow([sid, scen, name, expected, i + 1, decision, score,
                                     latency, leaked, keys, f"{wall:.1f}", trace])
                        rf.flush()
                        done += 1
                        print(f"[{done}/{total}] {sid} {scen} run {i + 1}/{args.runs}: "
                              f"{decision} score={score or '-'} leaked={leaked}/{keys}", flush=True)
                p = psutil.Process(proc.pid)
                t = p.cpu_times()
                wall_total = time.time() - started
                cpu = t.user + t.system
                ow.writerow([sid, f"{cpu:.2f}", f"{wall_total:.1f}",
                             f"{100 * cpu / wall_total:.2f}", f"{p.memory_info().rss / 1e6:.1f}"])
                of.flush()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                lf.close()
    except KeyboardInterrupt:
        print("\nInterrupted. Partial results are saved in experiments/results.csv")
    finally:
        rf.close()
        of.close()
    print("Done. Results:", RESULTS)


if __name__ == "__main__":
    main()
