#!/bin/bash
# Re-runs the scenarios where B or C block WHILE the attack types, after the final
# stuck-key fix (keys the desktop may still see as pressed are released at the block).
# Usage: sudo ./rerun_blocked_final.sh      (runs as root, so it asks for the password only once)
if [ "$(id -u)" -ne 0 ]; then echo "Run with: sudo ./rerun_blocked_final.sh"; exit 1; fi
cd /home/rehan/usb-hid-guard || exit 1

# Keep the previous results and logs for comparison.
cp experiments/results.csv experiments/results_before_stuckkey_final.csv
cp experiments/raw_logs/B_final_blocked.log experiments/raw_logs/B_before_stuckkey_final.log
cp experiments/raw_logs/C_final_blocked.log experiments/raw_logs/C_before_stuckkey_final.log

# Remove the rows that are run again below.
sed -i -E '/^B,S(2|3|4|9|11),/d; /^C,S(2|3|4|8),/d' experiments/results.csv

# systemd-inhibit stops Ubuntu from sleeping while the experiment runs.
RUN="systemd-inhibit --what=sleep:idle --why=experiment venv/bin/python experiments/run_experiments.py --runs 20"

$RUN --systems B --scenarios S2,S3,S4,S9,S11 || exit 1
cp experiments/raw_logs/B.log experiments/raw_logs/B_final_blocked.log

$RUN --systems C --scenarios S2,S3,S4,S8 || exit 1
cp experiments/raw_logs/C.log experiments/raw_logs/C_final_blocked.log

echo
echo "ALL PARTS DONE."
