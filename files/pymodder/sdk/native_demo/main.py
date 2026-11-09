"""Native code demo: a C++ dll (demo.cpp) counts jumps, Python shows the number.
To try it, copy this folder into pymodder/mods."""
import ctypes

import gd

NAME = "Native (C++) demo"
VERSION = "1.0"
AUTHOR = "PyModder"

lib = gd.load_dll("demo.dll")
add = lib.func("add", ctypes.c_int, ctypes.c_int, ctypes.c_int)
gd.log("2 + 3 computed in C++ =", add(2, 3))

label = gd.Label("", x=-8, y=-44, size=0.35, anchor=(1, 0.5))   # top right


@gd.on_level_start
def started(level):
    lib.reset_jumps()


@gd.on_frame
def update(dt):
    label.text = "C++ jumps: %d" % lib.jump_count()


@gd.on_exit
def left(level):
    label.text = ""
