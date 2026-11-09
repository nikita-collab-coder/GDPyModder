# A trail behind the player - a drawing example (gd.Draw). Turn it on in the mod settings.
import gd

NAME = "Trail"
VERSION = "1.2"
AUTHOR = "PyModder"

enabled = gd.setting("enabled", False, "Trail behind the player")
length = gd.setting("length", 60, "Length", min=10, max=300)
width = gd.setting("width", 3.0, "Width", min=1.0, max=10.0)
gd.setting_header("Look")
color = gd.setting("rgb", (0, 255, 255), "Color", kind="color")
fade = gd.setting("fade", True, "Fade out", "The old part of the trail is more transparent")

draw = gd.Draw(world=True)     # level coordinates - the same as gd.player.x / .y
points = []


@gd.on_attempt
def attempt(level):
    points.clear()


@gd.on_frame
def frame(dt):
    p = gd.player
    if not enabled.value or not p:
        if points:
            points.clear()
            draw.clear()
        return
    points.append((p.x, p.y))
    del points[:-length.value]
    draw.clear()
    r, g, b = color.value
    n = len(points)
    for i in range(1, n):
        a = int(255 * i / n) if fade.value else 255
        draw.line(*points[i - 1], *points[i], color=(r, g, b, a), width=width.value)
