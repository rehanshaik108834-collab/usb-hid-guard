#!/bin/bash
# Viva demo: walks through the project's story one act at a time (Linux VM only).
#
# Usage:   ./demo/viva_demo.sh          (all acts)
#          ./demo/viva_demo.sh 5        (start from act 5)
#
# Before starting: open Text Editor, and a browser on http://127.0.0.1:5000 -> Live monitor.
# Each act starts ONE detector with --enforce, plugs in a simulated keyboard that types into
# whatever window has focus, prints the detector's decision, then stops the detector.
# Press Enter to run an act, then click inside the Text Editor; do not touch the keyboard while it types.

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
# Stop processes whose command line contains $1. The first character goes in brackets so the
# pattern does not match the "sudo pkill ..." command line itself (which also contains $1).
stop() { sudo pkill -f -- "[${1:0:1}]${1:1}" 2>/dev/null; sleep 0.5; }
cleanup() { stop "--enforce"; [ -n "$DASH" ] && kill "$DASH" 2>/dev/null; }
trap cleanup EXIT

# act NUMBER DETECTOR TITLE -- device arguments...
act() {
  local n=$1 det=$2 title=$3; shift 4
  [ "$n" -lt "$START" ] && return
  bold "Act $n: $title"
  read -rp "  Press Enter, then click inside the Text Editor (typing starts in about 6 s)... " _
  sudo -v || return
  stop "--enforce"
  : > "$LOG"
  sudo $PY -u "$det" --enforce >> "$LOG" 2>&1 &
  sleep 3
  show_live
  sudo $PY "$@" --wait 3
  sleep 3
  kill "$LIVE" 2>/dev/null
  stop "$det"
}

# Print the detector's decisions (and any code it shows) while the act runs.
show_live() {
  echo "  Detector says:"
  tail -n +1 -f "$LOG" > >(grep --line-buffered -E -- "-> (ALLOW|ALERT|BLOCK|WOULD-BLOCK|CHALLENGE|INFO|NO-DATA)|>>>" \
    | grep --line-buffered -v "connected before" | sed -u 's/^ */    /; s/$/\r/') &
  LIVE=$!
}


bold "HID Guard viva demo"
say "Three detectors, the same attacks: A = identity whitelist (like USBGuard), B = USBlock (the base paper),"
say "C = proposed (descriptor + timing + content -> risk score; alert at 30, block at 70)."

# ---- Part 1: the existing approach -------------------------------------------------------
act 1 "$A" "System A blocks an unknown device" -- \
  attack_sim/fake_keyboard.py --name "Unknown Board" --vid dead --pid beef --mode fast
say "Say: the whitelist works when the attacker's ID is unknown; it is blocked at plug-in, 0 keys typed."

act 2 "$A" "System A lets a spoofed ID through" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: the same board claiming a trusted VID:PID types its whole payload. The ID is just a claim."

# ---- Part 2: the base paper, USBlock --------------------------------------------------------------
act 3 "$B" "USBlock (System B) blocks the fast spoofed attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: USBlock's rule: 3 gaps in a row under 20 ms. The attack types ~3 ms apart, so it is cut off after"
say "     4 keystrokes. No human ever made even 2 such gaps in a row (11 people, 46 recordings)."

act 4 "$B" "USBlock misses a slow attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode slow
say "Say: the attacker just slows down to human speed and USBlock, which uses timing alone, sees nothing."

act 5 "$B" "USBlock blocks a legitimate barcode scanner" -- \
  attack_sim/fake_keyboard.py --name "Barcode Scanner" --vid 05e0 --pid 1200 --mode fast --text 4006381333931
say "Say: scanners type as fast as attacks. USBlock blocked the scanner in every run, and its user has no way back."

# ---- Part 3: the proposed detector -------------------------------------------------------
say ""
say "Now switch the browser to Live monitor: each System C card shows the score and its warning signs."

act 6 "$C" "System C blocks the fast spoofed attack" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode fast --payload shellish
say "Say: ID collision +30, then USBlock's rapid sequence +50 = 80 >= 70. That is proof, so it is blocked at once."

act 7 "$C" "System C blocks a slow attack by what it types" -- \
  attack_sim/fake_keyboard.py --name "Spoofed KB" --vid 0001 --pid 0001 --mode slow --payload shellish
say "Say: timing looks human, but the content layer sees 'powershell' (+50): score 80. Without machine-speed"
say "     proof, C holds the keyboard and shows a code. An attack board cannot see the screen, so it stays blocked."

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

# Act 11 uses a real USB keyboard instead of the simulator: System C runs until Enter is pressed,
# and its decisions are shown here as they happen.
if [ 11 -ge "$START" ]; then
  bold "Act 11: System C and a real new keyboard"
  say "The keyboard's receiver must NOT be attached to the VM yet (VirtualBox: Devices > USB)."
  read -rp "  Press Enter to start System C... " _
  sudo -v || exit 1
  stop "--enforce"
  : > "$LOG"
  sudo $PY -u "$C" --enforce >> "$LOG" 2>&1 &
  sleep 3
  say "Now attach the receiver (VirtualBox: Devices > USB > the receiver), click in the Text Editor,"
  say "type powershell on the real keyboard, then type the code shown below on that same keyboard."
  say "Press Enter here when you are done."
  tail -n +1 -f "$LOG" > >(grep --line-buffered -E -- "-> (WATCHING|ALLOW|ALERT|BLOCK|CHALLENGE|INFO)|>>>" | grep --line-buffered -v "connected before" | sed -u 's/^/    /; s/$/\r/') &
  TAIL=$!
  read -rp "" _
  kill "$TAIL" 2>/dev/null
  stop "$C"
  say "Say: unknown ID +30, no serial +10, 'powershell' +50 = 90, but typed at human speed, so no proof."
  say "     It is held and a code is shown; a person can type it, an attack board cannot see the screen."
fi

# ---- Wrap-up -----------------------------------------------------------------------------
bold "Results (1,116 runs, 17 scenarios): open the dashboard's Results page"
say "A blocked 25% of attack runs (and a new real keyboard), B 42% (and the scanner), C 67%."
say "C blocked or alerted 100% of attack runs and wrongly blocked 0 legitimate devices."
echo
read -rp "Demo finished. Press Enter to stop the dashboard and exit. " _
