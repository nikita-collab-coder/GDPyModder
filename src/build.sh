#!/bin/sh
# Builds the PyModder loader DLLs (needs zig and minhook: git clone https://github.com/TsudaKageyu/minhook)
set -e
cd "$(dirname "$0")"
ZIG=${ZIG:-zig}
M=minhook/src
python3 gen_proxy.py
mkdir -p out
for P in XInput1_4 opengl32 version; do
  $ZIG cc -target x86_64-windows-gnu -O2 -shared -s -Iminhook/include -DPROXY_FILE="\"proxy/$P.inc\"" \
    loader.c $M/buffer.c $M/hook.c $M/trampoline.c $M/hde/hde64.c proxy/$P.def -o out/$P.dll -static
done
ls -la out
