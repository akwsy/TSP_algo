# Black-box simulations

Written by a tester who saw only `SPEC.md`, never the source, so the tests are not fitted to any algorithm.

```sh
./evaluation/build.sh                        # compile solvers
cd evaluation/simulation
python3 gen.py                               # write scenarios/ (gitignored)
python3 run_sims.py                          # pass/fail checks against a brute-force oracle -> REPORT.md
python3 collect.py ../web/evaluation-data.json   # quality metrics shown on /evaluation
```
Python 3 standard library only. Run `./evaluation/ui.sh` and open `/evaluation` to see the results.
