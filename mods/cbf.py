# Click Between Frames (experimental): a click counts at the moment you pressed, not at the next frame.
import gd

NAME = "Click between frames"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Experimental: clicks are applied at the exact moment (between frames). Helps on low FPS."
ICON = "mouse"

enabled = gd.setting("enabled", False, "Enabled")


@enabled.on_change
def changed(value):
    gd.click_between_frames(value)
    gd.notify("Click between frames: " + ("on" if value else "off"), 1.2)


@gd.on_load
def loaded():
    if enabled.value:
        gd.click_between_frames(True)


@gd.on_unload
def unload():
    gd.click_between_frames(False)
