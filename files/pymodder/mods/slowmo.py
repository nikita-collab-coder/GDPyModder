# Slow motion to practice hard parts. Turn on "Active" in the settings or press the key (F2).
# The music and sounds slow down too, and "SLOW 50%" is shown in the corner while it is on.
# It uses GD's own time speed (like the testmode speed slider): the physics really slows down,
# and an attempt in slow motion does not save progress (GD shows its testmode label).
import gd

NAME = "Slow motion"
VERSION = "2.1"
AUTHOR = "PyModder"
DESCRIPTION = "Slows the game down (F2), physics too. Slow attempts don't save progress."

active = gd.setting("active", False, "Active", "Slow motion is on (the key turns it on / off)")
slow = gd.setting("speed", 0.5, "Speed", "Game speed while slow motion is on", min=0.1, max=1.0, step=0.05)
key = gd.setting("key", "F2", "Key", "Turns slow motion on / off", kind="key")
gd.setting_header("Options")
audio = gd.setting("audio", True, "Slow down the music", "Music and sounds play at the game speed")
levels_only = gd.setting("levels_only", True, "Only in levels", "Normal speed in the menus")
badge_on = gd.setting("badge", True, "Show the indicator", '"SLOW 50%" in the bottom left corner')

badge = gd.Label("", x=8, y=14, size=0.4, color=(120, 220, 255), anchor=(0, 0.5))
badge.hide()


def working():
    return bool(active.value) and (gd.in_level or not levels_only.value)


def apply():
    on = working()
    gd.speed(slow.value if on else 1.0, audio=audio.value)
    badge.text = f"SLOW {slow.value:.0%}"
    badge.show(on and badge_on.value)


def set_active(on, tell=True):
    active.value = bool(on)          # -> apply() through on_change
    if tell:
        gd.notify(f"Slow motion {slow.value:.0%}" if on else "Slow motion off", 1.5)


for s in (active, slow, audio, levels_only, badge_on):
    s.on_change(lambda v: apply())


@gd.on_key(key)
def toggle():
    set_active(not active.value)


@gd.on_load
def loaded():
    apply()


@gd.on_level_start
def level_start(level):
    apply()


@gd.on_attempt
def attempt(level):
    if working() and abs(gd.speed() - slow.value) > 0.001:
        apply()


@gd.on_exit
def left(level):
    gd.after(0.1, apply)     # back to the menu -> normal speed (if "Only in levels")


@gd.on_unload
def unload():
    gd.speed(1.0)
    badge.hide()


@gd.mod_menu
def menu():
    p = gd.Popup("Slow motion", 330)
    t = p.toggle("Active", active.value, lambda v: set_active(v, False))
    sl = p.slider("Speed", slow.value, 0.1, 1.0, slow.set, step=0.05, fmt=lambda v: f"{v:.0%}")

    def preset(v):
        slow.value = v
        sl.value = slow.value
        if not active.value:
            set_active(True, False)
            t.value = True

    with p.row(6):
        for v in (0.25, 0.5, 0.75):
            p.button(f"{v:.0%}", lambda v=v: preset(v), "blue", 0.55)
    p.toggle("Slow down the music", audio.value, audio.set)
    p.space(2)
    with p.row(10):
        p.button("Settings", lambda: (p.close(), gd.open_settings()), "grey", 0.6)
        p.button("OK", p.close, size=0.6)
    p.show()
