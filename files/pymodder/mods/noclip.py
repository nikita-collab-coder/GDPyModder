# Noclip: the player does not die. It is a cheat - for practice. Turn it on in the settings or with a key.
import gd

NAME = "Noclip"
VERSION = "1.1"
AUTHOR = "PyModder"
DESCRIPTION = "The player goes through spikes and blocks. For practice only!"

enabled = gd.setting("enabled", False, "Noclip on")
key = gd.setting("key", "F3", "On / off key", kind="key")
label = gd.Label("NOCLIP", x=-8, y=-12, size=0.35, color=(255, 90, 90), anchor=(1, 0.5))
label.hide()
OFF_ANTICHEAT_SPIKE = 0x38E0   # PlayLayer: the check object at the start of a level (2.2091)


def update():
    label.show(gd.in_level and enabled.value)


@enabled.on_change
def changed(value):
    update()


@gd.on_key(key)
def toggle():
    enabled.value = not enabled.value
    gd.notify("Noclip: " + ("ON" if enabled.value else "OFF"))


@gd.on_level_start
def start(level):
    update()


@gd.on_exit
def leave(level):
    label.hide()


@gd.hook("PlayLayer::destroyPlayer")
def destroy(original, this, player, obj):
    if not enabled.value:
        return original()
    if obj and obj == gd.mem.ptr(this + OFF_ANTICHEAT_SPIKE):
        return original()       # let the game's own check pass as usual
    return None                 # do not call the game -> the player does not die
