# Main menu tweaks: hide buttons, add your own text and a button. Shows gd.on_layer("MenuLayer"),
# node IDs (gd.find(id=...)) and node.add_label / node.add_button.
import gd

NAME = "Main menu+"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Hide main menu buttons, show your own text and a quick button to the online levels."
ICON = "wrench"

text = gd.setting("text", "", "Text at the top", description="For example: Have fun!")
text_color = gd.setting("text_color", (255, 220, 80), "Text color")
gd.setting_header("Hide")
hide = {
    ("facebook-button", "twitter-button", "youtube-button", "twitch-button", "discord-button"):
        gd.setting("hide_social", False, "Social media buttons"),
    ("newgrounds-button",): gd.setting("hide_newgrounds", False, "Newgrounds"),
    ("daily-chest-button",): gd.setting("hide_daily_chest", False, "Daily chest"),
    ("achievements-button",): gd.setting("hide_achievements", False, "Achievements"),
    ("stats-button",): gd.setting("hide_stats", False, "Stats"),
    ("robtop-button",): gd.setting("hide_robtop", False, "RobTop logo"),
}
search_button = gd.setting("search_button", True, "Online levels button",
                           description="Takes effect the next time the menu opens")


@gd.on_layer("MenuLayer")
def menu(layer):
    apply_hidden(layer)
    w, h = gd.screen()
    layer.add_label(text.value, w / 2, h - 12, 0.4, text_color.value, "goldFont.fnt", id="menu-plus-text")
    if search_button.value:
        try:
            layer.add_button("gj_findBtn_001.png", open_search, x=28, y=h / 2 + 30, size=30, id="search-button")
        except ValueError:          # no such sprite frame -> a built-in icon
            layer.add_button("rocket", open_search, x=28, y=h / 2 + 30, size=30, id="search-button")


def apply_hidden(layer):
    for ids, setting in hide.items():
        for node_id in ids:
            btn = layer.find(id=node_id)
            if btn:
                btn.visible = not setting.value


def open_search():
    gd.open_screen("search")                 # also: "creator", "icon_kit", "main_levels", "levels" + text


def refresh(*_):
    lay = gd.current_layer()
    if lay is None or lay.cls != "MenuLayer":
        return
    apply_hidden(lay)
    lb = lay.find(id="menu-plus-text")
    if lb:
        lb.text = text.value
        lb.color = text_color.value


for _s in list(hide.values()) + [text, text_color]:
    _s.on_change(refresh)
