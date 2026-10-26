#!/bin/sh
set -eu
EVAL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$EVAL_DIR/build.sh"
cd "$EVAL_DIR/../submission"
. ./java-env.sh
exec "$JAVA" -cp "out:$EVAL_DIR/out" evaluation.app.UiServer --web "$EVAL_DIR/web" "$@"
