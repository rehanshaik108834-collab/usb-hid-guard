"""Reads the detectors' event database and experiment files and shapes them for the dashboard.
Read-only: the dashboard never writes to logs/ or experiments/."""
import csv
import glob
import json
import os
import re
import sqlite3
import statistics
import time

import psutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "logs", "events.db")
EXP = os.path.join(BASE, "experiments")
TRACES = os.path.join(BASE, "attack_sim", "human_traces")
ATTACKS = os.path.join(BASE, "attack_sim", "attack_traces")
CONFIG = os.path.join(BASE, "common", "config.json")

SYSTEMS = {
    "A": {"log": "A-baseline", "name": "Baseline", "long": "Identity whitelist (existing approach)",
          "script": "baseline_monitor.py", "path": "system_a_baseline/baseline_monitor.py"},
    "B": {"log": "B-timing", "name": "Timing only", "long": "Keystroke-timing detector",
          "script": "timing_detector.py", "path": "system_b_timing/timing_detector.py"},
    "C": {"log": "C-proposed", "name": "Proposed", "long": "Multi-signal behavioural detector",
          "script": "main_detector.py", "path": "system_c_proposed/main_detector.py"},
}
LOG_TO_LETTER = {v["log"]: k for k, v in SYSTEMS.items()}
FINAL = {"ALLOW", "ALERT", "BLOCK", "WOULD-BLOCK", "NO-DATA", "ERROR"}
DECISIONS = ["ALLOW", "ALERT", "BLOCK", "WOULD-BLOCK", "WATCHING", "INFO", "NO-DATA", "ERROR", "EXISTING", "REMOVED"]
WINDOWS = {"session": "Since dashboard start", "hour": "Last hour", "day": "Last 24 hours", "all": "All time"}
STARTED = time.strftime("%Y-%m-%d %H:%M:%S")


# ---------- events ----------

def _connect():
    if not os.path.exists(DB):
        return None
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)


def window_start(window, since=None):
    if since:
        return since
    if window == "hour":
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600))
    if window == "day":
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 86400))
    if window == "all":
        return None
    return STARTED


def query_events(start=None, system=None, decision=None, search=None, limit=200, offset=0, ascending=False):
    """Returns (rows, total). rows are dicts, newest first unless ascending."""
    conn = _connect()
    if conn is None:
        return [], 0
    where, args = [], []
    if start:
        where.append("ts >= ?"); args.append(start)
    if system in SYSTEMS:
        where.append("system = ?"); args.append(SYSTEMS[system]["log"])
    if decision:
        where.append("decision = ?"); args.append(decision)
    if search:
        where.append("(name LIKE ? OR vid || ':' || pid LIKE ? OR reason LIKE ?)")
        args += [f"%{search}%"] * 3
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM events {clause}", args).fetchone()[0]
        order = "ASC" if ascending else "DESC"
        cur = conn.execute(f"SELECT id, ts, system, kind, name, vid, pid, decision, reason FROM events {clause} "
                           f"ORDER BY id {order} LIMIT ? OFFSET ?", args + [limit, offset])
        rows = [dict(zip(("id", "ts", "system", "kind", "name", "vid", "pid", "decision", "reason"), r)) for r in cur]
    finally:
        conn.close()
    for r in rows:
        r["letter"] = LOG_TO_LETTER.get(r["system"], "?")
    return rows, total


# ---------- reason parsing ----------

_TAIL = re.compile(r"\s*\((grabbed|dry run|suspicious, not blocked|no keys typed)\)\s*$")


def _layer(text):
    t = text.lower()
    if "fast typing" in t or "median gap" in t:
        return "timing"
    if "launcher" in t or "shell keyword" in t:
        return "content"
    if "whitelist" in t and "not" not in t:
        return "identity"
    return "descriptor"


def parse_signals(letter, reason):
    """Splits a decision reason into [{text, points, layer}]."""
    if not reason:
        return []
    text = _TAIL.sub("", reason).strip()
    if letter == "C":
        body = text.split(": ", 1)[1] if ": " in text else ""
        if not body or body == "no flags":
            return []
        items = [s.strip() for s in body.split("; ") if s.strip()]
    else:
        items = [text]
    out = []
    for item in items:
        m = re.search(r"\(\+(\d+)\)\s*$", item)
        out.append({"text": re.sub(r"\s*\(\+\d+\)\s*$", "", item), "points": int(m.group(1)) if m else None,
                    "layer": _layer(item)})
    return out


def _num(pattern, text, cast=float):
    m = re.search(pattern, text or "")
    return cast(m.group(1)) if m else None


# ---------- device sessions ----------

def build_sessions(rows_ascending):
    """Groups events into one 'session' per device appearance: WATCHING -> decision -> INFO."""
    sessions, open_ = [], {}
    for e in rows_ascending:
        d = e["decision"]
        if d in ("EXISTING", "REMOVED"):
            continue
        key = (e["system"], e["name"], e["vid"], e["pid"])
        s = open_.get(key)
        if d == "WATCHING" or (d in FINAL and (s is None or s["decision"])):
            s = {"id": e["id"], "letter": e["letter"], "name": e["name"], "vid": e["vid"], "pid": e["pid"],
                 "kind": e["kind"], "started": e["ts"], "decision": None, "score": None, "keys": None,
                 "median_ms": None, "signals": [], "latency_ms": None, "leaked": None, "reason": e["reason"],
                 "descriptor_score": _num(r"descriptor score (\d+)", e["reason"], int)}
            sessions.append(s)
            open_[key] = s
        if d in FINAL:
            s.update(decision=d, decided=e["ts"], reason=e["reason"],
                     score=_num(r"\bscore (\d+)", e["reason"], int),
                     keys=_num(r"(?:after|over) (\d+) keys", e["reason"], int),
                     median_ms=_num(r"median (?:gap )?([\d.]+) ms", e["reason"]),
                     signals=parse_signals(e["letter"], e["reason"]))
        elif d == "WATCHING" and e["letter"] == "C":
            s["signals"] = parse_signals("C", e["reason"])
            s["score"] = s["descriptor_score"]
        elif d == "INFO" and s is not None:
            if "at plug-in" in (e["reason"] or ""):
                s["latency_ms"] = 0
            else:
                s["latency_ms"] = _num(r"block latency (\d+) ms", e["reason"], int)
            s["leaked"] = _num(r"(\d+) (?:of \d+ )?key presses leaked", e["reason"], int)
    for s in sessions:
        s["state"] = (s["decision"] or "WATCHING")
    return list(reversed(sessions))


def live_sessions(window="session", since=None, system=None, limit=60):
    rows, _ = query_events(window_start(window, since), system=system, limit=2000, ascending=False)
    rows.reverse()
    return build_sessions(rows)[:limit]


def tally(sessions):
    t = {"seen": len(sessions), "ALLOW": 0, "ALERT": 0, "BLOCK": 0, "WATCHING": 0}
    for s in sessions:
        k = "BLOCK" if s["state"] == "WOULD-BLOCK" else s["state"]
        if k in t:
            t[k] += 1
    return t


def detectors():
    """Which detectors are running right now, and whether they enforce."""
    found = {}
    for p in psutil.process_iter(["cmdline", "create_time"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
        except (psutil.Error, TypeError):
            continue
        for letter, info in SYSTEMS.items():
            if info["script"] in cmd and "python" in cmd:
                found[letter] = {"enforce": "--enforce" in cmd,
                                 "since": time.strftime("%H:%M", time.localtime(p.info["create_time"]))}
    return found


def db_info():
    conn = _connect()
    if conn is None:
        return {"exists": False, "count": 0, "first": None, "last": None}
    try:
        n, first, last = conn.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM events").fetchone()
    finally:
        conn.close()
    return {"exists": True, "count": n, "first": first, "last": last}


# ---------- configuration ----------

def config():
    with open(CONFIG) as f:
        return json.load(f)


WEIGHT_TEXT = {
    "not_whitelisted": ("VID:PID not on the whitelist", "descriptor"),
    "attack_board_id": ("VID:PID of a known attack board", "descriptor"),
    "id_collision": ("VID:PID already used by another connected device", "descriptor"),
    "composite": ("Composite device: storage and keyboard together", "descriptor"),
    "missing_serial": ("No serial number reported", "descriptor"),
    "fast_typing": ("Median keystroke gap below the threshold", "timing"),
    "launcher": ("Launcher shortcut typed (Win+R, Ctrl+Alt+T, Alt+F2)", "content"),
    "shell_keyword": ("Shell command keyword typed", "content"),
}


def weights():
    w = config()["proposed"]["weights"]
    return [{"key": k, "text": WEIGHT_TEXT.get(k, (k, ""))[0], "layer": WEIGHT_TEXT.get(k, ("", "descriptor"))[1],
             "points": v} for k, v in w.items()]


# ---------- experiment results ----------

def _read_csv(name):
    path = os.path.join(EXP, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def experiment():
    rows = _read_csv("results.csv")
    if not rows:
        return None
    order = sorted({r["scenario"] for r in rows}, key=lambda s: int(s[1:]))
    cells, names, expected = {}, {}, {}
    for r in rows:
        k = (r["scenario"], r["system"])
        c = cells.setdefault(k, {"n": 0, "block": 0, "alert": 0, "leaked": [], "latency": []})
        c["n"] += 1
        names[r["scenario"]] = r["scenario_name"]
        expected[r["scenario"]] = r["expected"]
        if r["decision"] in ("BLOCK", "WOULD-BLOCK"):
            c["block"] += 1
            if r["latency_ms"] not in ("", None):
                c["latency"].append(float(r["latency_ms"]))
        elif r["decision"] == "ALERT":
            c["alert"] += 1
        c["leaked"].append(float(r["leaked"] or 0))

    def outcome(scen, sy):
        c = cells.get((scen, sy))
        if not c:
            return None
        n, exp = c["n"], expected[scen]
        leaked = statistics.mean(c["leaked"]) if c["leaked"] else 0
        lat = statistics.mean(c["latency"]) if c["latency"] else None
        if c["block"] == n:
            label = "Blocked"
            note = "at plug-in" if lat == 0 or (lat is None and leaked == 0) else f"{leaked:.1f} keys leaked"
        elif c["alert"] == n:
            label, note = "Alert", "not blocked"
        elif c["block"] == 0 and c["alert"] == 0:
            label, note = "Allowed", f"{leaked:.0f} keys typed" if exp == "attack" else ""
        else:
            label, note = f"Blocked {c['block']}/{n}", f"{c['alert']} alerts"
        if exp == "attack":
            grade = "good" if c["block"] == n else ("part" if c["block"] + c["alert"] == n else "bad")
        else:
            grade = "bad" if c["block"] else ("part" if c["alert"] else "good")
        return {"label": label, "note": note, "n": n, "grade": grade, "latency": lat}

    matrix = [{"id": s, "name": names[s], "expected": expected[s],
               "cells": {sy: outcome(s, sy) for sy in SYSTEMS}} for s in order]

    summary = {}
    for sy in SYSTEMS:
        att = [r for r in rows if r["system"] == sy and r["expected"] == "attack"]
        leg = [r for r in rows if r["system"] == sy and r["expected"] == "legit"]
        if not att:
            continue
        blocked = sum(r["decision"] in ("BLOCK", "WOULD-BLOCK") for r in att)
        flagged = blocked + sum(r["decision"] == "ALERT" for r in att)
        fp = sum(r["decision"] in ("BLOCK", "WOULD-BLOCK") for r in leg)
        alerts = sum(r["decision"] == "ALERT" for r in leg)
        summary[sy] = {"attacks": len(att), "blocked": blocked, "flagged": flagged, "legit": len(leg),
                       "false_blocks": fp, "legit_alerts": alerts,
                       "blocked_pct": 100 * blocked / len(att), "flagged_pct": 100 * flagged / len(att),
                       "fp_pct": 100 * fp / len(leg) if leg else 0,
                       "leaked": statistics.mean(float(r["leaked"] or 0) for r in att)}
    overhead = {r["system"]: r for r in _read_csv("overhead_summary.csv")}
    return {"runs": len(rows), "scenarios": len(order), "matrix": matrix, "summary": summary,
            "overhead": overhead}


def typing_data():
    gaps, people, recs = [], set(), 0
    for p in glob.glob(os.path.join(TRACES, "*.json")):
        with open(p) as f:
            gaps += [g * 1000 for g in json.load(f)["gaps"]]
        people.add(os.path.basename(p).split("_")[0])
        recs += 1
    fast = []
    for p in glob.glob(os.path.join(ATTACKS, "*.json")):
        with open(p) as f:
            d = json.load(f)
        if d.get("mode") == "fast" and d.get("name") != "Barcode Scanner":
            fast += [g * 1000 for g in d["gaps"]]
    if not gaps:
        return None
    return {"people": len(people), "recordings": recs, "gaps": len(gaps),
            "median": statistics.median(gaps), "under20": 100 * sum(g < 20 for g in gaps) / len(gaps),
            "attack_median": statistics.median(fast) if fast else None,
            "threshold": config()["timing"]["threshold_ms"]}


FIGURES = [
    ("fig_detection_rate.png", "Attack detection rate", "Share of attack runs each system blocked, by scenario."),
    ("fig_false_positives.png", "False positives", "Legitimate runs wrongly blocked (left) and flagged (right)."),
    ("fig_leaked_keys.png", "Keystrokes leaked", "Mean keystrokes that reached the computer before the attack was stopped."),
    ("fig_latency.png", "Detection latency", "Mean time from the first keystroke to the block."),
    ("fig_human_vs_attack_hist.png", "Human and attack timing", "Gaps between keystrokes: recorded people against the measured attacks."),
]
