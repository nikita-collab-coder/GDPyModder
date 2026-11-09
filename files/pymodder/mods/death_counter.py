# Death counter in the corner + a total that is saved.
import gd

NAME = "Death counter"
VERSION = "1.3"
AUTHOR = "PyModder"

show = gd.setting("show", True, "Show in levels")
color = gd.setting("color", (255, 255, 255), "Text color")       # an (r, g, b) default -> a color setting
label = gd.Label("", x=8, y=-12, size=0.35, anchor=(0, 0.5))   # y < 0 - offset from the top
label.hide()


def update():
    lv = gd.level
    if lv:
        label.text = f"Deaths: {lv.deaths}  Total: {gd.load('total', 0)}"
    label.show(bool(lv) and show.value)


@show.on_change
def changed(value):
    update()


@color.on_change
def recolor(rgb):
    label.color = rgb


@gd.setting_button("Reset the total", color="red", description="Sets the saved total back to 0")
def reset_total():
    def yes():
        gd.save("total", 0)
        update()
        gd.notify("Total deaths: 0")
    gd.confirm("Reset the total death count?", yes, yes="Reset", yes_color="red")


@gd.on_load
def loaded():
    label.color = color.value


@gd.on_level_start
def start(level):
    update()


@gd.on_death
def died(player):
    gd.save("total", gd.load("total", 0) + 1)
    update()


@gd.on_exit
def leave(level):
    label.hide()
