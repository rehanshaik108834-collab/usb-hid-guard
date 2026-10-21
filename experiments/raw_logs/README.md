# Detector logs behind results.csv

Each file is the console log of one detector during one experiment session. The 1,116 rows of
`../results.csv` come from these sessions:

| System | Scenarios | Log |
| --- | --- | --- |
| A | S2, S3, S4, S5, S7, S8 | `A_part1.log` |
| A | S9, S11, S12, S13, S14 | `A_part2.log` |
| A | S1, S6, S10 (every recording replayed once) | `A_final_replays.log` |
| A | S15, S16 | `A_codecheck.log` |
| A | S17 | `A_delayed.log` |
| B | S1 to S17 (the full USBlock re-implementation) | `B_usblock.log` |
| C | S7, S12, S14 | `C_part2.log` |
| C | S1, S6, S10 | `C_final_replays.log` |
| C | S5, S8, S13, S15, S16 (with the code check for held keyboards) | `C_codecheck.log` |
| C | S2, S3, S4, S9, S11, S17 (timing layer = USBlock's rule, kept running while connected) | `C_usblock.log` |

Runs of other scenarios that appear in these logs were repeated later and replaced in `results.csv`:
the human-replay scenarios after the replay timing fix, the scenarios where a detector blocks while
keys are typed after the stuck-key fix, System C's S5, S8 and S13 after the code check was added, and
every System B run plus System C's fast scenarios after the USBlock rebuild.

- `superseded/`: logs of replaced runs, kept for reference.
- `A.log`, `B.log`, `C.log`: the experiment runner's working files, overwritten on every run.
- `../history/`: results files saved before each re-run, and the logs of the first 2-run trial.
