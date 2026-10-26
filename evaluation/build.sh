#!/bin/sh
set -eu
EVAL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$EVAL_DIR/../submission"
. ./java-env.sh
./build.sh
mkdir -p "$EVAL_DIR/out"
"$JAVAC" --release 17 -cp out -d "$EVAL_DIR/out" \
    "$EVAL_DIR"/src/evaluation/algorithms/*.java "$EVAL_DIR"/src/evaluation/app/*.java
