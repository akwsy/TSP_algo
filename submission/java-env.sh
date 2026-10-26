#!/bin/sh
# Portable JDK discovery: no machine-specific installation paths.
if [ -n "${JAVA_HOME:-}" ]; then
    JAVA="$JAVA_HOME/bin/java"
    JAVAC="$JAVA_HOME/bin/javac"
else
    JAVA=java
    JAVAC=javac
fi
if ! "$JAVA" -version >/dev/null 2>&1 || ! "$JAVAC" -version >/dev/null 2>&1; then
    echo "A JDK 17 or newer is required. Configure JAVA_HOME or put java and javac on PATH." >&2
    exit 1
fi
export JAVA JAVAC
