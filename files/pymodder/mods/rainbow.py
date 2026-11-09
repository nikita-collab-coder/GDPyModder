# Rainbow player icon (turn it on in the mod settings or press F9 for the mod menu).
import colorsys
import gd

NAME = "Rainbow icon"
VERSION = "1.1"
AUTHOR = "PyModder"
MENU_KEY = "F9"          # opens this mod's settings anywhere in the game

enabled = gd.setting("enabled", False, "Rainbow icon")
speed = gd.setting("speed", 1.0, "Speed", min=0.1, max=5.0)
both = gd.setting("both", True, "Second color too")
t = 0.0


def rgb(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1, 1)
    return int(r * 255), int(g * 255), int(b * 255)


@gd.on_frame
def frame(dt):
    global t
    if not enabled.value:
        return
    t += dt * speed.value * 0.5
    for p in (gd.player, gd.player2):
        if p:
            p.color = rgb(t)
            if both.value:
                p.color2 = rgb(t + 0.5)
