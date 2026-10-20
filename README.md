# HID Guard: USB Security Monitoring Application

Application-based project in cyber security (ICS).
Team: Aditya Sai Koka, Karpurapu Sai Satwik, Mokshagna Manduva, Shaik Rehan.

USB keystroke-injection devices (USB Rubber Ducky, Digispark, Arduino, Raspberry Pi Pico) pretend to be a
keyboard and type commands at machine speed. Identity-based USB whitelisting, the approach of USBGuard,
trusts the Vendor ID and Product ID that a device reports, and an attacker can copy those. This project
implements that approach, shows that a spoofed ID bypasses it, and proposes a detector that also judges a
new keyboard by what it does.

| System | Folder | Decides on |
| --- | --- | --- |
| A, existing approach | `system_a_baseline/` | VID:PID against a whitelist, once at plug-in |
| B, timing only | `system_b_timing/` | Median gap of the first 10 keystrokes below 20 ms |
| C, proposed | `system_c_proposed/` | Points from three layers (descriptor, typing speed, typed content); alert at 30, block at 70 |

## Results (936 automated runs, 14 scenarios)

| | A | B | C |
| --- | --- | --- | --- |
| Attack runs blocked | 20% | 40% | 60% |
| Attack runs blocked or alerted | 20% | 40% | 100% |
| Legitimate runs wrongly blocked | 0 of 112 | 20 of 112 (barcode scanner) | 0 of 112 |
| Keystrokes leaked before a fast attack was stopped | not stopped (spoofed ID) | about 10 | 6 |
| Average CPU / peak memory | 0.13% / 28 MB | 0.32% / 29 MB | 0.41% / 30 MB |

Typing recorded from 11 people never came close to the 20 ms threshold (closest: 86 ms); the simulated
attack typed at a median of 3.4 ms per key. Full tables: `experiments/summary_table.csv`; graphs:
`experiments/fig_*.png`. The full write-up is in the project report, submitted separately.

## Project layout

```
common/              shared code: key reading, safe blocking, logging; config.json holds every threshold and weight
system_a_baseline/   System A (identity whitelist)
system_b_timing/     System B (timing only)
system_c_proposed/   System C (descriptor, timing and content layers + risk engine)
attack_sim/          harmless virtual attack devices (Linux uinput), human typing recorder and replayer
  human_traces/      46 typing recordings from 11 people (key timing only, no text)
  attack_traces/     measured key timing of the simulated attacks
experiments/         experiment runner, results.csv, summary tables, graphs; raw_logs/ explains each log
dashboard/           read-only web dashboard (Flask)
demo/viva_demo.sh    step-by-step live demonstration of all three systems
report_screenshots/  every figure used in the report, numbered by section
screenshots/         the original screenshots, as taken
tools/               environment check (test_env.py) and the volunteer recording helper
logs/                events.log and events.db written by the detectors
```

## Running it

The detectors and the simulator need Linux (tested on Ubuntu 26.04 in VirtualBox) and root, because they
read input devices and create virtual ones. The dashboard runs anywhere.

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# a detector (add nothing for a dry run that only logs)
sudo venv/bin/python system_c_proposed/main_detector.py --enforce

# in a second terminal: a simulated attack (open a text editor and click inside it first)
sudo venv/bin/python attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast

# the dashboard, then open http://127.0.0.1:5000
venv/bin/python dashboard/app.py

# the whole experiment (about 3 hours) and its graphs
sudo venv/bin/python experiments/run_experiments.py --runs 20 --fresh
venv/bin/python experiments/make_graphs.py
venv/bin/python experiments/analyze_traces.py

# the live demonstration, act by act
./demo/viva_demo.sh
```

## Safety

The simulated devices only type harmless text such as "HELLO from the simulated keyboard" or the words
"powershell -Command Write-Host HELLO" without pressing Enter. Run them only on your own machine or a
virtual machine, with a text editor focused.
