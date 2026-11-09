# Icon hack: every icon, color, trail and death effect is unlocked in the garage while this is on.
import gd

NAME = "Unlock all icons"
VERSION = "1.0"
AUTHOR = "PyModder"
DESCRIPTION = "Lets you pick any icon and color in the garage. Your save is not changed."

enabled = gd.setting("enabled", False, "Unlock all icons")


@enabled.on_change
def changed(value):
    gd.unlock_icons(value)
    gd.notify("All icons " + ("unlocked" if value else "locked again (as in your save)"))


gd.unlock_icons(enabled.value)
