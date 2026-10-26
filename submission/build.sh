#!/bin/sh
set -eu
cd "$(dirname "$0")"
. ./java-env.sh
mkdir -p out
"$JAVAC" --release 17 -d out src/graph/*.java src/algorithms/*.java src/app/*.java
