# I love version control!
Maximum destinations within a time period

A Java 17-compatible routing project: start at a depot at a specified time, visit
as many customer destinations as possible within their time windows, and return
within the trip period. Distance breaks ties between routes with the same visit
count. Waiting counts toward the period; service time is zero.

## Quick start

Install JDK 17 or newer and configure `JAVA_HOME` or put `java` and `javac` on PATH.
No external libraries or internet access are needed. From the repository root:

```sh
./submission/run.sh --start-time 08:00 --duration-minutes 120
./evaluation/test.sh
./evaluation/compare.sh --start-time 08:00 --duration-minutes 60
```

The shell scripts target a POSIX environment such as Linux, macOS or WSL. See `submission/README.md` for manual Java commands.

## Simple HTML comparison UI

```sh
./evaluation/ui.sh
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The page calls the actual Java
solvers and shows plain output rows, expandable route tables and a location graph.
Change departure, trip duration, speed or customer windows and compare again.
Press Ctrl+C in the server terminal to stop. See [evaluation/UI.md](evaluation/UI.md).

## Documentation and layout

- [PROJECT_GUIDE.md](PROJECT_GUIDE.md): project requirements, every repository
  file, inputs, outputs, algorithm design, limitations and collaboration workflow.
- [submission/](submission/): graph, greedy insertion and branch-and-bound source,
  standalone CLI and scenario inputs; no baseline or UI dependencies.
- [evaluation/](evaluation/): nearest-neighbour baseline, HTML UI/server, tests and
  comparison tools that reuse the submission algorithms rather than copying them.
- [docs/](docs/): original project brief, dataset metadata and original Read Me;
  [SOURCE_FILES.md](docs/SOURCE_FILES.md) inventories and verifies these copies.
- [submission/inputs/](submission/inputs/): full GeoNames text dataset and the
  original header-added Excel workbook.

Geographic coordinates come from the provided GeoNames records. Travel times
and appointment windows are explicitly simulated. The default scenario has a
depot plus nine potential visits; the depot does not contribute to the visit count.

The default 120-minute demonstration returns 5 visits for nearest neighbour,
8 for greedy insertion and 9 for exact search. These results concern the supplied simulated scenario only.
Nearest neighbour is the baseline, greedy insertion is the redesigned heuristic,
and branch and bound is the exact reference solver.

Generated `out/` directories and `.class` files are ignored by Git. There are no
hard-coded workstation paths, bundled dependencies or compiled artifacts to push.

## Replace the destination selection

The full GeoNames file is included at `submission/inputs/MY.txt`. Run:

```sh
./submission/run.sh --generate inputs/MY.txt --count 25 --selection random --seed 42
./submission/run.sh --algorithm greedy --duration-minutes 180
```

This replaces the existing `submission/data/` scenario and generates windows for
every selected customer. The count includes the depot. No expanded data folder is
created, and the original MY.txt is unchanged. See the Project Guide for region,
feature-class, depot, clock and window controls.
