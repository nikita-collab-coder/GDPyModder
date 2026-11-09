# Your own pictures: a star from star.png spins above the player, and a clickable picture shows up
# in the pause menu. Turn it on in the mod settings.
import gd

NAME = "Sprite demo"
VERSION = "1.1"
AUTHOR = "PyModder"
DESCRIPTION = "Your own picture (star.png) above the player. Turn it on in the settings."
# the icon in the mods list is icon.png from this folder (or set ICON = "star.png" / a built-in name)

enabled = gd.setting("enabled", False, "Star above the player")
size = gd.setting("size", 1.0, "Size", min=0.3, max=3.0)

star = None
clicks = gd.storage.file("clicks.json", {"count": 0})     # saves itself


@gd.on_level_start
def start(level):
    global star
    if enabled.value:
        star = gd.Sprite("star.png", world=True, scale=size.value, opacity=220)
        star.spin(120)


@gd.on_frame
def follow(dt):
    if star and gd.player:
        star.move(gd.player.x, gd.player.y + 45)


@gd.on_exit
def left(level):
    global star
    if star:
        star.remove()
        star = None


@gd.on_pause
def paused():
    def clicked():
        clicks["count"] += 1
        gd.notify("The star was clicked %d times" % clicks["count"])
        badge.remove()
    if enabled.value:
        w, h = gd.screen()
        badge = gd.Sprite("star.png", x=w - 40, y=40, scale=0.8, on_click=clicked, z=200)
        gd.after(5, badge.remove)
