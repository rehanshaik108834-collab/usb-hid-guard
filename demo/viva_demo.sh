#!/bin/bash
# Viva demo: walks through the project's story one act at a time (Linux VM only).
#
# Usage:   ./demo/viva_demo.sh          (all acts)
#          ./demo/viva_demo.sh 5        (start from act 5)
#
# Before starting: open Text Editor, and a browser on http://127.0.0.1:5000 -> Live monitor.
# Each act starts ONE detector with --enforce, plugs in a simulated keyboard that types into
# whatever window has focus, prints the detector's decision, then stops the detector.
# Press Enter to run an act; while it types, keep the Text Editor focused and do not touch the keyboard.

cd "$(dirname "$0")/.." || exit 1
PY=venv/bin/python
LOG=logs/demo_detector.log
START=${1:-1}
sudo -v || exit 1

A=system_a_baseline/baseline_monitor.py
B=system_b_timing/timing_detector.py
C=system_c_proposed/main_detector.py
LEGIT_TRACE=$(ls attack_sim/human_traces/*normal*.json 2>/dev/null | head -1)

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
say()  { printf '  \033[36m%s\033[0m\n' "$*"; }

# Start the dashboard if it is not already running (it only reads the logs, no sudo).
if ! pgrep -f dashboard/app.py >/dev/null; then
  $PY dashboard/app.py >/dev/null 2>&1 &
  DASH=$!
  echo "Dashboard started on http://127.0.0.1:5000"
fi
cleanup() { sudo pkill -f -- "--enforce" 2>/dev/null; [ -n "$DASH" ] && kill "$DASH" 2>/dev/null; }
trap cleanup EXIT

# act NUMBER DETECTOR TITLE -- device arguments...
act() {
  local n=$1 det=$2 title=$3; shift 4
  [ "$n" -lt "$START" ] && return
  bold "Act $n: $title"
  read -rp "  Click inside Text Editor, then press Enter here... " _
  sudo pkill -f -- "--enforce" 2>/dev/null
  : > "$LOG"
  sudo $PY -u "$det" --enforce >> "$LOG" 2>&1 &
  sleep 3
  sudo $PY "$@" --wait 3
  sleep 3
  sudo pkill -f -- "$det" 2>/dev/null
  echo "  Detector said:"
  grep -E -- "-> (ALLOW|ALERT|BLOCK|WOULD-BLOCK|INFO|NO-DATA)" "$LOG" | sed 's/^/    /'
}


bold "HID Guard viva demo"
say "Three detectors, the same attacks: A = identity whitelist (like USBGuard), B = timing only,"
say "C = proposed (descriptor + timing + content -> risk score; alert at 30, block at 70)."

# ---- Part 1: the existing approach -------------------------------------------------------
act 1 "$A" "System A blocks an unknown device" -- \
  attack_sim/fake_keyboard.py --name "Unknown Board" --vid dead --pid beef --mode fast
say "Say: the whitelist works when the attacker's ID is unknown; it is blocked at plug-in, 0 keys typed."

act 2 "$A" "System A lets a spoofed ID through" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: the same board claiming a trusted VID:PID types its whole payload. The ID is just a claim."

# ---- Part 2: timing alone ----------------------------------------------------------------
act 3 "$B" "System B blocks the fast spoofed attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: ~3 ms between keys; no human is below 20 ms (closest of 11 people: 86 ms). Blocked after 10 keys."

act 4 "$B" "System B misses a slow attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode slow
say "Say: the attacker just slows down to human speed and timing alone sees nothing."

act 5 "$B" "System B blocks a legitimate barcode scanner" -- \
  attack_sim/fake_keyboard.py --name "Barcode Scanner" --vid 05e0 --pid 1200 --mode fast --text 4006381333931
say "Say: scanners type as fast as attacks. B blocked the scanner in every run (a false positive)."

# ---- Part 3: the proposed detector -------------------------------------------------------
say ""
say "Now switch the browser to Live monitor: each System C card shows the score and its warning signs."

act 6 "$C" "System C blocks the fast spoofed attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: ID collision +30, then fast typing or a shell keyword +50 = 80 >= 70. Decided after 6 keys (B needs 10)."

act 7 "$C" "System C blocks a slow attack by what it types" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode slow --payload shellish
say "Say: timing looks human, but the content layer sees 'powershell' (+50). Slowing down does not help."

act 8 "$C" "System C blocks a Digispark board at plug-in" -- \
  attack_sim/fake_keyboard.py --name "Digispark" --vid 16c0 --pid 27db --mode slow
say "Say: known attack-board ID +40 and not whitelisted +30 = 70, blocked before it types anything."

act 9 "$C" "System C only alerts on the barcode scanner" -- \
  attack_sim/fake_keyboard.py --name "Barcode Scanner" --vid 05e0 --pid 1200 --mode fast --text 4006381333931
say "Say: fast typing alone is 50 points, under the 70 block line. Flagged, never cut off."

if [ -n "$LEGIT_TRACE" ]; then
  act 10 "$C" "System C allows a real person's typing" -- \
    attack_sim/replay_trace.py --trace "$LEGIT_TRACE" --name "Legit KB" --vid 046d --pid c31c
  say "Say: a recorded human typing session on a whitelisted keyboard scores 0 and is allowed."
fi

# ---- Wrap-up -----------------------------------------------------------------------------
bold "Results (936 runs, 14 scenarios): open the dashboard's Results page"
say "A blocked 20% of attack runs, B 40% (but blocked the scanner), C 60%; C blocked or alerted 100%."
say "C wrongly blocked 0 legitimate devices."
echo
read -rp "Demo finished. Press Enter to stop the dashboard and exit. " _
