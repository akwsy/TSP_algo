#!/bin/sh
# Averaged benchmark; writes evaluation/web/benchmark-data.json. Options: --scenarios N --seed S --out file
set -eu
EVAL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$EVAL_DIR/build.sh"
cd "$EVAL_DIR/../submission"
. ./java-env.sh
exec "$JAVA" -cp "out:$EVAL_DIR/out" evaluation.app.BenchmarkMain --out "$EVAL_DIR/web/benchmark-data.json" "$@"
