# Tickets

Common rules for every ticket:
- Work only in the files listed under **Scope**. If you need a file outside it, stop and report instead.
- No external libraries, no internet access at runtime, no inline `<script>`/`style=` (the UI server sends a strict CSP).
- `./evaluation/test.sh` must pass before you finish. Add tests for new behaviour (red first, then green).
- Existing behaviour and default output must stay identical unless the ticket says otherwise.
- Commit on your own branch with a clear message. Do not push. Report what you changed, what you verified and what you could not.

| ID | Title | Depends on |
|---|---|---|
| T1 | Fixed 6-hour block windows option | - |
| T2 | Boundary-case test suite | - |
| T4 | Simplify and restyle the web UI | - |
| T5 | Improve the map | - |
| T3 | Averaged benchmark runner | T1 |
| T6 | Evaluation page for benchmark and boundary data | T2, T3, T4 |
