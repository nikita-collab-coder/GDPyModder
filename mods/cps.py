# Clicks per second counter (CPS).
import time
import gd

NAME = "CPS counter"
VERSION = "1.1"
AUTHOR = "PyModder"

show = gd.setting("show", True, "Show CPS")
label = gd.Label("", x=8, y=-28, size=0.35, anchor=(0, 0.5))
label.hide()
clicks = []
best = 0


@gd.on_jump
def jump(player):
    clicks.append(time.perf_counter())


@gd.on_frame
def frame(dt):
    global best
    now = time.perf_counter()
    while clicks and now - clicks[0] > 1:
        clicks.pop(0)
    best = max(best, len(clicks))
    label.text = f"CPS: {len(clicks)}  max {best}"
    label.show(show.value)


@gd.on_exit
def leave(level):
    label.hide()
