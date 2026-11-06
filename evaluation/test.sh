#!/bin/sh
set -eu
EVAL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$EVAL_DIR/build.sh"
cd "$EVAL_DIR/../submission"
. ./java-env.sh
"$JAVAC" --release 17 -cp "out:$EVAL_DIR/out" -d "$EVAL_DIR/out" "$EVAL_DIR"/tests/*.java
"$JAVA" -cp "out:$EVAL_DIR/out" tests.TestSuite
"$JAVA" -cp "out:$EVAL_DIR/out" tests.BoundaryCases
exec "$JAVA" -cp "out:$EVAL_DIR/out" tests.UiServerTest
