#!/bin/bash
# Usage: ./tools/record_friend.sh 1      (records friend1: 2 normal + 2 fast runs)
if [ -z "$1" ]; then echo "Usage: ./tools/record_friend.sh NUMBER"; exit 1; fi
cd ~/usb-hid-guard || exit 1
sudo -v
for kind in normal normal fast fast; do
  echo
  echo "=== friend$1: $kind run ==="
  if [ "$kind" = "normal" ]; then
    echo "Type at your USUAL speed."
  else
    echo "Type as FAST as you comfortably can."
  fi
  read -p "Press Enter when ready... " _
  sudo venv/bin/python attack_sim/record_human.py --label "friend$1_$kind"
done
echo
echo "Done with friend$1. Thank you!"
