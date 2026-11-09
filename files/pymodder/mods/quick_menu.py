# Example: your own menu on a key. Press F4 anywhere - in a level it pauses the game and shows
# quick actions (restart, practice, speed). The key can be changed in the mod settings.
import gd

NAME = "Quick menu"
VERSION = "1.0"
AUTHOR = "PyModder"
DESCRIPTION = "F4 - a small menu with quick actions (an example of gd.mod_menu + MENU_KEY)."
MENU_KEY = "F4"           # opens the function marked with @gd.mod_menu
ICON = "keyboard"         # a built-in icon (see gd.icons())

SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)


@gd.mod_menu
def menu():
    p = gd.Popup("Quick menu", 340)
    lv = gd.level
    if lv:
        p.text(lv.name or "Level", 0.6, font="goldFont.fnt")
        p.text(f"{lv.percent:.0f}%   attempt {lv.attempts}   deaths {lv.deaths}", 0.45, (200, 200, 200))
        p.space(4)
        with p.row(8):
            p.button("Resume", lambda: run(p, lambda: gd.pause_action("resume")), "green", 0.6)
            p.button("Restart", lambda: run(p, gd.restart), "blue", 0.6)
            p.button("From start", lambda: run(p, lambda: gd.restart(full=True)), "blue", 0.6)
        p.toggle("Practice mode", lv.practice, lambda on: run(p, lambda: set_practice(on)))
        p.line()
    p.text("Game speed", 0.45, align="left")
    now = gd.speed()
    with p.row(5):
        for v in SPEEDS:
            color = "green" if abs(now - v) < 0.001 else "grey"
            p.button(f"{v:g}x", lambda v=v: set_speed(p, v), color, 0.5)
    p.line()
    with p.row(8):
        p.button("Mods", lambda: run(p, gd.open_mods_menu), "pink", 0.6)
        if lv:
            p.button("Exit level", lambda: run(p, lambda: gd.confirm("Leave the level?", gd.quit_level)),
                     "red", 0.6)
        p.button("Close", p.close, "grey", 0.6)
    p.show()


def run(popup, action):
    popup.close()
    gd.later(action)


def set_practice(on):
    if not gd.pause_action("practice" if on else "normal"):     # the pause menu buttons (also resume)
        if gd.level:
            gd.level.practice = on


def set_speed(popup, v):
    gd.speed(v)
    gd.notify(f"Speed {v:g}x", 1.2)
    popup.close()
    gd.later(menu)          # reopen: the current speed is highlighted
