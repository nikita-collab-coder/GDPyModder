# "Are you sure?" before leaving a level or restarting it from the pause menu.
import gd

NAME = "Confirm exit"
VERSION = "1.0"
AUTHOR = "PyModder"
DESCRIPTION = "Asks before you leave a level (and, if you want, before a restart) from the pause menu."

ask_exit = gd.setting("exit", True, "Ask before exit")
ask_restart = gd.setting("restart", False, "Ask before restart")
min_percent = gd.setting("percent", 0, "Only after this %", "Do not ask before you get this far", min=0, max=100)


def worth_asking():
    lv = gd.level
    return lv is not None and lv.percent >= min_percent.value


@gd.on_quit
def leaving():
    if not ask_exit.value or not worth_asking():
        return None                       # leave as usual
    gd.confirm("Leave the level?", gd.quit_level, title="Exit", yes="Exit", no="Stay", yes_color="red")
    return False                          # stay for now - the popup decides


@gd.on_pause_button("restart")
def restarting():
    if not ask_restart.value:
        return None
    gd.confirm("Restart the level?", lambda: gd.pause_action("restart"), title="Restart")
    return False
