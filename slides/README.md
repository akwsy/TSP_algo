# G4T1 presentation slides

`index.html` is our CS201 project deck. It is one self-contained file: no install, build step or internet needed.

## View it

Open `index.html` in a browser.

| Key | Action |
|---|---|
| Left / Right / Space | Previous or next slide |
| Enter / Backspace | Step an interactive forward or back |
| N | Speaker notes |
| F | Fullscreen |
| T | Switch a chart to its table |

## Export the PDF

Press Ctrl+P, choose **Save as PDF** and tick **Background graphics**. You get one slide per page. The live sandbox on the last slide is left out on purpose.

## Where the numbers come from

- **Charts and results:** our full suite run on 8 Nov 2026 (2,550 runs, no failures), from `results/aggregates-*.json`. Run `python3 start.py --suite` from the repo root to regenerate them. Runtimes will differ by machine; visit counts should not.
- **Multi-day figures (slide 20):** the "until every place is visited" part of the same run.
- **Worked example (slides 7, 9, 10, 13):** the real instance in `docs/ALGORITHM_SPEC.md`, section 8.
- **ILS replay (slide 11):** instance `n5-seed17` from our run, stepped through by the JavaScript port.
- **Cache speed-ups (slide 10):** from our earlier comparison of the original and cached greedy insertion. They were not re-measured in the run above. Reproduce them with `python3 algorithms/greedy-insertion/compare.py`.
- **Screenshots:** real captures of the results site from our own run, embedded in the HTML.

## How it was made

The deck was built with Claude Code from the team's handoff notes and checked against the saved results. It is plain HTML, CSS and JavaScript, with charts drawn as inline SVG. Our AI usage is declared on slide 21.

The live sandbox and step-through demos use JavaScript ports of the three algorithms, for illustration only. Their routes were identical to the Python programs on all 2,250 distinct first-day runs we compared, but every reported result comes from the Python harness. The sandbox's numbers are not experimental evidence.
