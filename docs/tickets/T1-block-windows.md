# T1: Fixed 6-hour block windows option
Scope: `submission/src/app/GenerationOptions.java`, `ScenarioFiles.java`, `Main.java`, `submission/README.md`, `evaluation/src/evaluation/app/UiServer.java` (the `/api/generate` handler only), `evaluation/tests/TestSuite.java`.

Add an alternative window mode where each non-depot location is assigned ONE of four fixed blocks of the clock day: 00:00-06:00, 06:00-12:00, 12:00-18:00, 18:00-24:00, chosen by the seeded RNG (same seed => same assignment). The depot stays always open.
- Setting: `windowMode=slack` (current default, unchanged) or `blocks`. CLI `--window-mode slack|blocks`, property `windowMode` in scenario.properties, form field `windowMode` in `/api/generate`. Invalid value is rejected.
- Windows in `windows.tsv` are minutes relative to `startClock`: open = blockStart - clock, close = blockEnd - clock. If the block ends at or before the start clock, add 1440 to both (next day). If open would be negative, clip open to 0 (close stays). Closing end is inclusive.
- Default output for existing options must be byte-identical to today (the committed golden outputs must not change).
- Document in `submission/README.md` and DATA_NOTES generation text: with 08:00 start and 120 min, blocks give mostly all-open or all-unreachable locations, so blocks suit longer periods or other start times.
Tests: determinism by seed; all four blocks occur with a large enough sample; depot open; correct offsets for startClock 08:00 and 22:00; rejected invalid mode; default mode unchanged.
