# Show hitboxes in levels (like the practice mode "show hitboxes" option, but anywhere).
import gd

NAME = "Hitboxes"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Shows the hitboxes of the player and objects. Can show them only after a death."
ICON = "target"

show = gd.setting("show", False, "Show hitboxes")
on_death = gd.setting("on_death", False, "Only after a death", description="Shows them when you die")


def apply(dead=False):
    gd.show_hitboxes(show.value and (dead or not on_death.value))


@show.on_change
def changed(value):
    apply()


@on_death.on_change
def changed2(value):
    apply()


@gd.on_load
def loaded():
    apply()


@gd.on_attempt
def attempt(level):
    apply()


@gd.on_death
def died(player):
    if on_death.value:
        apply(dead=True)


@gd.on_unload
def unload():
    gd.show_hitboxes(False)
