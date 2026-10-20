#!/bin/bash
# Final re-run with all fixes applied:
#  1. S1, S6, S10 (human replays) for A, B, C - now every recording is replayed once
#  2. B: S2, S3, S4, S9, S11 and C: S2, S3, S4, S8 - the runs that blocked while keys were
#     typed, now with the stuck-key fix
# Usage: sudo ./final_rerun.sh      (runs as root, so it asks for the password only once)
if [ "$(id -u)" -ne 0 ]; then echo "Run with: sudo ./final_rerun.sh"; exit 1; fi
cd /home/rehan/usb-hid-guard || exit 1

# Keep the old results and logs.
cp experiments/results.csv experiments/results_before_final_rerun.csv
for s in A B C; do cp experiments/raw_logs/$s.log experiments/raw_logs/${s}_before_final_rerun.log; done

# Remove the rows that are run again below.
sed -i -E '/^[ABC],S(1|6|10),/d; /^B,S(2|3|4|9|11),/d; /^C,S(2|3|4|8),/d' experiments/results.csv

# systemd-inhibit stops Ubuntu from sleeping while the experiment runs.
RUN="systemd-inhibit --what=sleep:idle --why=experiment venv/bin/python experiments/run_experiments.py --runs 20"

$RUN --systems A,B,C --scenarios S1,S6,S10 || exit 1
for s in A B C; do cp experiments/raw_logs/$s.log experiments/raw_logs/${s}_final_replays.log; done

$RUN --systems B --scenarios S2,S3,S4,S9,S11 || exit 1
cp experiments/raw_logs/B.log experiments/raw_logs/B_final_blocked.log

$RUN --systems C --scenarios S2,S3,S4,S8 || exit 1
cp experiments/raw_logs/C.log experiments/raw_logs/C_final_blocked.log

echo
echo "ALL PARTS DONE."
