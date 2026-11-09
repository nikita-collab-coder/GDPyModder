# A mod template. Files that start with "_" are not loaded.
# Copy this file, name it e.g. my_mod.py and write your code. In game: F5 - reload mods, F6 - mods menu.
# Text can be in any language: gd.notify("Привет!") works too (non-latin text uses Arial).
import gd

NAME = "My mod"
AUTHOR = "Me"
VERSION = "1.0"
DESCRIPTION = "What the mod does (shown in the mods menu)."
# ICON = "icon.png"      # icon in the mods menu (or my_mod.png next to my_mod.py, or a built-in one: "skull")
# MENU_KEY = "F8"        # opens this mod's menu (its settings or gd.mod_menu) anywhere in the game

# settings show up in the mods menu (gear button) and are saved automatically
enabled = gd.setting("enabled", True, "Enabled")
power = gd.setting("power", 5, "Power", min=1, max=10)
# gd.setting_header("Look")                               # a section title
# color = gd.setting("color", (255, 255, 0), "Color")     # an (r, g, b) default -> a color picker
# gd.setting_button("Reset", lambda: gd.save("stats", {}), color="red")


@gd.on_load            # the game started / the mod was reloaded
def loaded():
    gd.log("mod loaded")


@gd.on_menu            # main menu
def menu():
    pass


# buttons on game screens (position: "top-left", "top-right", "bottom-left", "bottom-right", "left", "right"...)
# @gd.level_button("GJ_infoIcon_001.png")        # online level page: def f(layer, level)
# @gd.end_button(text="Hi", position="top")      # level complete screen
# @gd.editor_button("wrench")                    # level editor
# @gd.screen_button("garage", "chart", position="left")


@gd.on_level_start     # a level opened: level.name, level.id, level.attempts
def start(level):
    pass


@gd.on_attempt         # a new attempt
def attempt(level):
    pass


@gd.on_jump            # a click / jump (return False - cancel the click)
def jump(player):
    pass


@gd.on_death           # death: player.x, player.y, gd.level.percent
def death(player):
    pass


@gd.on_complete        # the level is complete
def complete(level):
    pass


@gd.on_frame           # every frame in a level (dt - seconds since the last frame)
def frame(dt):
    pass


@gd.on_quit            # the exit button of the pause menu (return False - stay in the level)
def leaving():
    pass


@gd.on_key("F4")       # a key
def f4():
    if not enabled.value:
        return
    p = gd.Popup("My mod")
    p.text(f"Power: {power.value}")
    p.slider("Power", power.value, 1, 10, lambda v: setattr(power, "value", v))
    p.button("OK", p.close)
    p.show()


# your own files on disk (only .json and .macro): pymodder/saves/<mod>/
stats = gd.storage.file("stats.json", {"jumps": 0})     # a dict that saves itself


@gd.on_key("F10")      # input simulation and pictures
def f10():
    stats["jumps"] += 1
    gd.click()                                   # a jump (in a level)
    star = gd.Sprite("GJ_starsIcon_001.png", x=50, y=50, scale=1.5)
    star.spin(180)
    gd.after(2, star.remove)
