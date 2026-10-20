#!/bin/bash
# Measures the code check added to System C (one-off; delete after use).
#  - C: S5, S8, S13 again (these now go through the code check instead of an outright block)
#  - A, B, C: the two new scenarios S15 (new keyboard, a person answers the code) and
#    S16 (slow attack with an unknown ID, cannot answer)
# Usage: sudo ./rerun_codecheck.sh      (runs as root, so it asks for the password only once)
if [ "$(id -u)" -ne 0 ]; then echo "Run with: sudo ./rerun_codecheck.sh"; exit 1; fi
cd /home/rehan/usb-hid-guard || exit 1

cp experiments/results.csv experiments/history/results_before_codecheck.csv
sed -i -E '/^C,S(5|8|13),/d; /^[ABC],S(15|16),/d' experiments/results.csv

RUN="systemd-inhibit --what=sleep:idle --why=experiment venv/bin/python experiments/run_experiments.py --runs 20"
$RUN --systems C --scenarios S5,S8,S13,S15,S16 || exit 1
cp experiments/raw_logs/C.log experiments/raw_logs/C_codecheck.log
$RUN --systems A,B --scenarios S15,S16 || exit 1
cp experiments/raw_logs/A.log experiments/raw_logs/A_codecheck.log
cp experiments/raw_logs/B.log experiments/raw_logs/B_codecheck.log

echo
echo "ALL PARTS DONE."
