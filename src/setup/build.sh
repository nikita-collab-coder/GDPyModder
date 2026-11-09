#!/bin/sh
# Builds "PyModder Setup.exe" (needs zig). gen_stock.py needs the older builds in ../../build.
set -e
cd "$(dirname "$0")"
ZIG=${ZIG:-zig}
[ -d ../../build ] && python3 gen_stock.py || true
$ZIG cc -target x86_64-windows-gnu -O2 -s -municode -Wl,--subsystem,windows -Wall -Wextra -Wno-unused-parameter \
  setup.c setup.rc -o "PyModder Setup.exe" -lcomctl32 -lole32 -lshell32 -luser32 -lgdi32 -ladvapi32
rm -f "PyModder Setup.lib" "PyModder Setup.pdb"
ls -la "PyModder Setup.exe"
