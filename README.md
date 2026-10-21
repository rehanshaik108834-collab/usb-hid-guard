# HID Guard: USB Security Monitoring Application

Application-based project in cyber security (ICS).
Team: Aditya Sai Koka, Karpurapu Sai Satwik, Mokshagna Manduva, Shaik Rehan.

USB keystroke-injection devices (USB Rubber Ducky, Digispark, Arduino, Raspberry Pi Pico) pretend to be a
keyboard and type commands at machine speed. The project builds on the paper **USBlock: Blocking USB-based
Keypress Injection Attacks** (Neuner et al., IFIP DBSec 2018), which blocks a keyboard as soon as it types
faster than any person can. We re-implemented USBlock in full, measured where it fails, and built an
improved detector on top of it.

| System | Folder | Decides on |
| --- | --- | --- |
| A, ID whitelist (industry reference, like USBGuard) | `system_a_baseline/` | VID:PID against a whitelist, once at plug-in |
| B, USBlock (the base paper) | `system_b_timing/`, `common/usblock.py` | 3 keypresses in a row, each under 20 ms after the one before, on every keypress of every connected keyboard; YubiKeys must type MODHEX |
| C, ours | `system_c_proposed/` | USBlock's rule unchanged, plus descriptor checks and the typed content in a new keyboard's first 30 s; alert at 30, block or hold at 70 |

USBlock's reaction is implemented as in the paper: the device's drivers are unbound, its USB port is
powered off for 10 s, and if the same port attacks again the whole hub is switched off.

System C blocks at once only when USBlock's rule fires, which is proof: no person types that fast. Other
suspicious keyboards reaching 70 points are held (their keys stop reaching the computer) and a 4-digit
code is shown on the dashboard and in the detector's terminal. A person types the code on the new keyboard
and it is unlocked; an injection device cannot see the screen and stays blocked. USBlock's rule keeps
running for as long as a keyboard is connected, so an attack that waits before typing is still caught.

## Results (1,116 automated runs, 17 scenarios)

| | A: ID whitelist | B: USBlock | C: ours |
| --- | --- | --- | --- |
| Attack runs blocked | 25% (60 of 240) | 42% (100 of 240) | 67% (160 of 240) |
| Attack runs blocked or alerted | 25% | 42% | 100% |
| Legitimate runs wrongly blocked | 20 of 132 (new keyboard) | 20 of 132 (barcode scanner) | 0 of 132 |
| Keystrokes leaked before a fast attack was stopped (median) | not stopped (spoofed ID) | 4 | 4 |
| Average CPU / peak memory | 0.10% / 28 MB | 0.27% / 29 MB | 0.35% / 32 MB |

Tested with real hardware too: a USB wireless keyboard was held after its user typed "powershell" and
unlocked by typing the code shown; without the code it was blocked and switched off.

Typing recorded from 11 people never contained two gaps under 20 ms in a row, so USBlock's rule never
fired on a person; the simulated attack typed at a median of 3.3 ms per key. Full tables:
`experiments/summary_table.csv`; graphs: `experiments/fig_*.png`. The full write-up is in the project
report, submitted separately.

## Project layout

```
common/              shared code: key reading, safe blocking, logging, USBlock's rule and reaction
                     (usblock.py); config.json holds every threshold and weight
system_a_baseline/   System A (identity whitelist)
system_b_timing/     System B (USBlock re-implementation)
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

# the whole experiment (about 5 hours) and its graphs
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
