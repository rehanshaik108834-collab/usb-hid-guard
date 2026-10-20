# Project status (handoff)

Last updated: 2026-10-20. Read this first when continuing the work on another machine.

## What the project is
USB Security Monitoring Application (application-based project). Detects USB keystroke-injection
("BadUSB" / Rubber Ducky) attacks on Linux.
- System A `system_a_baseline/`: identity whitelist (existing approach, like USBGuard).
- System B `system_b_timing/`: timing-only detector.
- System C `system_c_proposed/`: proposed multi-signal detector (descriptor + timing + content -> risk score;
  block at 70, alert at 30). Settings in `common/config.json`.
- `attack_sim/`: virtual attack devices (Linux uinput), human typing recorder/replayer.
- `experiments/`: automated runner, results, graphs.

The detectors and simulator need Linux (evdev, uinput, udev) and sudo. Everything else runs anywhere.

## Done
- Final experiment: 936 runs, 14 scenarios (`experiments/results.csv`, graphs `experiments/fig_*.png`).
  C: 60% of attack runs blocked, 100% blocked or alerted, 0 legitimate devices blocked, 6 keys leaked on
  fast attacks (B: ~10). A: 20% blocked. B: 40% blocked, but blocks the barcode scanner every time.
- Human typing: 11 people, 46 recordings; closest a human came to the 20 ms threshold: 86 ms.
- Bugs found and fixed: replay catch-up burst (S1/S6/S10 re-run), stuck key after blocking
  (`grab_releasing_keys` in `common/device_info.py`; verified against Text Editor output, 179/180 exact).
- `report_screenshots/`: labelled figures in report order (Fig_3.1 ... Fig_7.5), raw originals in `originals/`.
- Report (Claude Docs, all 9 sections written):
  https://claude.ai/code/artifact/9b3e1fb6-e831-48c3-984f-232980c1b10f
- Dashboard `dashboard/` (Flask, read-only, light theme): Overview, Live monitor, Event log, Results, Method.
  All pages render without errors.

## Still to do
1. Look at the dashboard in a browser and polish the design if needed (not yet visually checked).
2. Take dashboard screenshots (Overview, Live monitor with data, Results, Method) into
   `report_screenshots/dashboard/`, then fill report subsection "6.8 Monitoring dashboard" (still a
   placeholder in the doc).
3. Fill in team names / roll numbers / course on the report's cover.
4. Demo script for the viva (run in the Linux VM).

## Running the dashboard
Linux VM:  `venv/bin/python dashboard/app.py`
Windows:   `py -m venv venv-win` then `venv-win\Scripts\pip install flask psutil`
           then `venv-win\Scripts\python dashboard\app.py`
Open http://127.0.0.1:5000. "Live monitor" -> "All time" shows the experiment's devices.
