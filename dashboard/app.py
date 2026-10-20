"""
HID Guard dashboard: a read-only web view of the USB detectors and the experiment results.

Run (no sudo needed):   venv/bin/python dashboard/app.py
Then open:              http://127.0.0.1:5000
Start a detector in another terminal (for example System C with --enforce) to see devices live.
"""
import os
import sys
import time

from flask import Flask, abort, render_template, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data  # noqa: E402

app = Flask(__name__)

VERDICT = {"ALLOW": ("Allowed", "allow"), "ALERT": ("Alert", "alert"), "BLOCK": ("Blocked", "block"),
           "WOULD-BLOCK": ("Would block", "block"), "WATCHING": ("Watching", "watch"),
           "NO-DATA": ("No data", "muted"), "ERROR": ("Error", "block"), "INFO": ("Info", "muted"),
           "EXISTING": ("Present at start", "muted"), "REMOVED": ("Removed", "muted")}


@app.context_processor
def shared():
    return {"SYSTEMS": data.SYSTEMS, "VERDICT": VERDICT, "WINDOWS": data.WINDOWS,
            "running": data.detectors(), "now": time.strftime("%H:%M:%S"), "path": request.path}


def _filters():
    window = request.args.get("window", "session")
    if window not in data.WINDOWS:
        window = "session"
    system = request.args.get("system") or None
    return window, (system if system in data.SYSTEMS else None), request.args.get("since") or None


@app.route("/")
def overview():
    return render_template("overview.html", **_overview_ctx(_filters()[0]))


@app.route("/partial/overview")
def overview_partial():
    return render_template("partials/overview_live.html", **_overview_ctx(_filters()[0]))


def _overview_ctx(window):
    sessions = data.live_sessions(window)
    events, _ = data.query_events(data.window_start(window), limit=14)
    return {"sessions": sessions, "tally": data.tally(sessions), "latest": sessions[0] if sessions else None,
            "events": events, "exp": data.experiment(), "started": data.STARTED, "window": window}


@app.route("/monitor")
def monitor():
    window, system, since = _filters()
    return render_template("monitor.html", **_monitor_ctx(window, system, since, _latest()))


@app.route("/partial/monitor")
def monitor_partial():
    window, system, since = _filters()
    return render_template("partials/monitor_live.html", **_monitor_ctx(window, system, since, _latest()))


def _latest():
    return request.args.get("latest") == "1"


def _monitor_ctx(window, system, since, latest):
    sessions = data.live_sessions(window, since, system, latest)
    return {"sessions": sessions[:60], "tally": data.tally(sessions), "window": window, "system": system,
            "since": since, "latest": latest, "start": data.window_start(window, since),
            "now_ts": time.strftime("%Y-%m-%d %H:%M:%S")}


@app.route("/events")
def events():
    window, system, since = _filters()
    if "window" not in request.args:
        window = "all"
    decision = request.args.get("decision") or None
    search = (request.args.get("q") or "").strip() or None
    page = max(1, request.args.get("page", 1, type=int))
    per = 50
    rows, total = data.query_events(data.window_start(window, since), system, decision, search,
                                    limit=per, offset=(page - 1) * per)
    pages = max(1, (total + per - 1) // per)
    return render_template("events.html", rows=rows, total=total, page=page, pages=pages, window=window,
                           system=system, decision=decision, q=search or "", decisions=data.DECISIONS)


@app.route("/results")
def results():
    return render_template("results.html", exp=data.experiment(), typing=data.typing_data(),
                           figures=data.FIGURES)


@app.route("/method")
def method():
    cfg = data.config()
    return render_template("method.html", weights=data.weights(), cfg=cfg, db=data.db_info())


@app.route("/figure/<name>")
def figure(name):
    if name not in {f[0] for f in data.FIGURES}:
        abort(404)
    return send_from_directory(data.EXP, name, max_age=60)


if __name__ == "__main__":
    print("HID Guard dashboard on http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)
