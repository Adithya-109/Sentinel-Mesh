#!/usr/bin/env bash
# Builds and runs the host-side sentinel_proto unit tests with a plain g++
# invocation (no PlatformIO needed). Use `pio test -e native` instead once
# PlatformIO is installed on your machine.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=/tmp/sentinel_tests
g++ -std=gnu++17 -Wall -Wextra -Ilib/sentinel_proto/include \
    test/test_native/test_main.cpp lib/sentinel_proto/src/*.cpp \
    -o "$OUT"
"$OUT"
