#!/bin/sh
set -eu
cd "$(dirname "$0")"
. ./java-env.sh
./build.sh
exec "$JAVA" -cp out app.Main "$@"
