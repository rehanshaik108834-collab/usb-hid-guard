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
  Start from an act with `./demo/viva_demo.sh 6`. Dry run done 2026-10-20: all 10 acts as expected.
- Submission audit (2026-10-20, VM): all code compiles, all dashboard pages render with numbers matching
  the report. Fixed in the demo script: not executable, `sudo pkill` could match its own command line,
  focus prompt in the wrong order. Added README.md, requirements.txt, experiments/raw_logs/README.md;
  moved superseded logs and backup results into raw_logs/superseded/ and experiments/history/, helpers
  into tools/. Report 6.1 table now lists the dashboard and the demo script.

- Code check (2026-10-20): System C blocks outright only on machine-speed typing; otherwise it holds the
  keyboard and shows a 4-digit code (CHALLENGE). Typing it on the device unlocks it. New scenarios S15/S16;
  experiment now 1,056 runs, 16 scenarios (C 64% blocked, 100% flagged, 0 false blocks). Report, README,
  dashboard and demo (new act 11) updated. Real keyboard tests done with a 2.4G wireless receiver (3554:fa09): code typed -> unlocked;
  no code -> blocked and USB switched off (authorized = 0). Report 6.9 + Fig 6.14-6.17; Fig 6.10/6.12 refreshed.

- USBlock phase (2026-10-21): base paper is USBlock (Neuner et al., DBSec 2018). `common/usblock.py` holds
  its rule (3 gaps in a row under 20 ms, YubiKey MODHEX exception) and reaction (authorized = 0, port off
  10 s, hub off 10 s on a repeat attack within 120 s). B and C watch keyboards present at start; C keeps
  USBlock's rule running after its 30 s window. New scenario S17 (fast attack after 35 s). Experiment now
  1,116 runs, 17 scenarios: A 25% / B 42% / C 67% attacks blocked, C 100% flagged, 0 false blocks.
  Report "Improving USBlock" (https://claude.ai/artifact/C93kLTwERG4sssLqDMAmoM) sections 2-6 updated.

## Links (all made with Claude; ask Rehan for access if one does not open)
- Report to submit, "Improving USBlock": https://claude.ai/artifact/C93kLTwERG4sssLqDMAmoM
- Presentation, 7 slides in the teacher's format: https://claude.ai/artifact/SuGyv5fQgQb7aBPPRNAUPi
  Palette: paper #F5F2EA with faint grain, text #18212C, muted #46505C, accent #B8501E,
  blue #2C5C8F, dividers #C8C3B8. Light mode only; dark only for the slide 4 evidence band.
- Team study guide (explains everything + viva Q&A): https://claude.ai/artifact/9Znw3qzntyc2BdScyxMKRy

## Working on this project with Claude Code
Open Claude Code in this folder and start with: "Read HANDOFF.md and README.md, then help me with ...".
The team is beginners: ask for exact commands. Always commit and push after work
(a VM snapshot restore once wiped 6 hours of unpushed work).

## Still to do
1. Export the report as PDF and the presentation as .pptx (Share -> Export) for submission.

## Running the dashboard
Linux VM:  `venv/bin/python dashboard/app.py`
Windows:   `py -m venv venv-win` then `venv-win\Scripts\pip install flask psutil`
           then `venv-win\Scripts\python dashboard\app.py`
Open http://127.0.0.1:5000. "Live monitor" -> "All time" + "Latest per device" shows one card per experiment device.
