#!/bin/bash
# Finishes the full experiment after the sleep interruptions.
# Re-runs the human-replay scenarios (S1, S6, S10) for A, B, C with the fixed replay,
# then runs the rest of System C. Usage: ./resume_experiment.sh
cd ~/usb-hid-guard || exit 1
sudo -v || exit 1

# Keep the main-run logs (the runner overwrites A.log, B.log, C.log).
for s in A B C; do
  [ -f experiments/raw_logs/$s.log ] && sudo cp experiments/raw_logs/$s.log experiments/raw_logs/${s}_main.log
done

# Remove the old replay rows (made with the buggy replay) and the unfinished C S6 rows.
sudo sed -i -E '/^[ABC],S(1|6|10),/d' experiments/results.csv

# systemd-inhibit stops Ubuntu from sleeping while the experiment runs.
RUN="sudo systemd-inhibit --what=sleep:idle --why=experiment venv/bin/python experiments/run_experiments.py --runs 20"
$RUN --systems A,B,C --scenarios S1,S6,S10 && \
$RUN --systems C --scenarios S7,S8,S9,S11,S12,S13,S14
