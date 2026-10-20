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
  Checked in a browser 2026-10-20 and polished: fixed "Keys seen" showing `<built-in method keys...>`,
  tallies now count every session (not just the newest 60), Live monitor has "Latest per device",
  Overview has a time-window switch, command boxes no longer overflow on Method.
- Dashboard screenshots in `report_screenshots/dashboard/` (Fig_6.10 ... Fig_6.13, plus a spare event-log
  shot); report subsection 6.8 "Monitoring dashboard" written with those four figures.
- Viva demo: `demo/viva_demo.sh` (Linux VM). 10 acts: A blocks unknown / misses spoof, B blocks fast /
  misses slow / blocks scanner, C blocks fast / slow shell / Digispark, alerts scanner, allows a human.
  Start from an act with `./demo/viva_demo.sh 6`. Not yet run in the VM.
- Submission audit (2026-10-20, VM): all code compiles, all dashboard pages render with numbers matching
  the report. Fixed in the demo script: not executable, `sudo pkill` could match its own command line,
  focus prompt in the wrong order. Added README.md, requirements.txt, experiments/raw_logs/README.md;
  moved superseded logs and backup results into raw_logs/superseded/ and experiments/history/, helpers
  into tools/. Report 6.1 table now lists the dashboard and the demo script.

## Still to do
1. Report cover: names and course (ICS) are in; replace the placeholder roll numbers (S2024001XXXX) and
   "Dr. Guide Name" with the real ones.
2. Do a dry run of `demo/viva_demo.sh` in the Linux VM before the viva.

## Running the dashboard
Linux VM:  `venv/bin/python dashboard/app.py`
Windows:   `py -m venv venv-win` then `venv-win\Scripts\pip install flask psutil`
           then `venv-win\Scripts\python dashboard\app.py`
Open http://127.0.0.1:5000. "Live monitor" -> "All time" + "Latest per device" shows one card per experiment device.
