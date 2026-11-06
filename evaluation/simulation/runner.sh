#!/bin/sh
# Black-box runner for the simulations. Run ./evaluation/build.sh first so the classes exist.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec java -cp "$ROOT/submission/out:$ROOT/evaluation/out" evaluation.app.ComparisonMain "$@"
