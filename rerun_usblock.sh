#!/bin/bash
# Re-runs the experiments after the USBlock rebuild (one-off; delete after use).
#  - System B (now the full USBlock re-implementation): every scenario, S1 to S17
#  - System C (timing layer now USBlock's rule, kept running while a device is connected):
#    the fast scenarios S2, S3, S4, S9, S11 and the new delayed attack S17
#  - System A: the new delayed attack S17
# Usage: sudo ./rerun_usblock.sh      (runs as root, so it asks for the password only once)
if [ "$(id -u)" -ne 0 ]; then echo "Run with: sudo ./rerun_usblock.sh"; exit 1; fi
cd /home/rehan/usb-hid-guard || exit 1

cp experiments/results.csv experiments/history/results_before_usblock.csv
sed -i -E '/^B,/d; /^C,S(2|3|4|9|11|17),/d; /^A,S17,/d' experiments/results.csv

RUN="systemd-inhibit --what=sleep:idle --why=experiment venv/bin/python experiments/run_experiments.py --runs 20"
$RUN --systems B || exit 1
cp experiments/raw_logs/B.log experiments/raw_logs/B_usblock.log
$RUN --systems C --scenarios S2,S3,S4,S9,S11,S17 || exit 1
cp experiments/raw_logs/C.log experiments/raw_logs/C_usblock.log
$RUN --systems A --scenarios S17 || exit 1
cp experiments/raw_logs/A.log experiments/raw_logs/A_delayed.log

# Graphs and tables from the new results (as the normal user, so the files stay editable)
chown -R rehan:rehan /home/rehan/usb-hid-guard
sudo -u rehan venv/bin/python experiments/make_graphs.py > /dev/null
sudo -u rehan venv/bin/python experiments/analyze_traces.py > /dev/null

echo
echo "ALL PARTS DONE."
