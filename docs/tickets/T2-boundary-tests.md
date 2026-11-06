# T2: Boundary-case test suite
Scope: NEW files `evaluation/tests/BoundaryCases.java`, `evaluation/boundary.sh`; edit `evaluation/test.sh` to run it. Do not edit solver source.

Hand-built scenarios (equator coordinates so distances are easy) with expected results written as LITERALS you derived by hand, never recomputed by the code under test. Assert for all three solvers (nearest, greedy, exact) and document in a comment which algorithm is expected to be suboptimal and why. Cover at least:
1. The only open location is very far away (nearer ones are closed): must be chosen if reachable in the period.
2. Only reachable customer is exactly at the deadline (return arrives exactly at start+period) and one just beyond it.
3. Nearest-neighbour trap: the closest customer leads to fewer total visits than a farther first choice.
4. Greedy-insertion trap: a case where insertion order loses a visit exact finds.
5. Waiting trap: an early arrival must wait for a window; visiting in the other order allows one more visit.
6. Window closes exactly at arrival time; window closes just before.
7. All customers closed/unreachable (depot-only route is optimal); zero period; single customer.
8. Distance tie-break: equal visit counts, shortest distance wins; equal distances.
9. Customers at identical coordinates; collinear points.
10. Four-block style windows (00-06, 06-12, 12-18, 18-24 as offsets from a 08:00 start with a long period).
Where an algorithm is expected to fail to reach the optimum, assert its actual (suboptimal) count so the test documents the weakness. `evaluation/boundary.sh` runs the suite and, with `--emit <file>`, writes a JSON list of {name, description, expected{nearest,greedy,exact}, actual{...}} for the web page. Print a readable table too.
