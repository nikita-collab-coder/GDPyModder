# Icon stealer: a button on other players' profiles that copies their icons and colors to you.
# Shows gd.on_layer on a GD popup, gd.servers (GD servers in the background) and gd.set_icons.
import gd

NAME = "Icon stealer"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Copy the icons and colors of any player: a button on profiles, or search by name."
ICON = "ghost"

KINDS = ("cube", "ship", "ball", "ufo", "wave", "robot", "spider", "swing", "jetpack")


@gd.on_layer("ProfilePage")          # ProfilePage::init(accountID, ownProfile)
def profile(layer, account_id=None, own=False, *rest):
    if own or not account_id:
        return
    menu = layer.find(cls="CCMenu")   # the popup's own menu (a new menu would not get clicks in a popup)
    if not menu:
        return
    w, h = gd.screen()
    x, y = menu.to_local(w / 2 - 190, h / 2 + 95)
    menu.add_button("ghost", lambda: fetch(account_id), x=x, y=y, size=26, id="icon-stealer-button")


def fetch(account_id):
    gd.notify("Loading the profile...", 1.0)
    gd.servers.get_user_info(account_id, got)


def got(user, error):
    if error or not user:
        gd.alert(f"Could not load the profile: {error}")
        return
    p = gd.Popup(f"Icons of {user.get('name', '?')}", 380)
    with p.row(6):
        for kind in KINDS[:5]:
            p.icon(user.get(kind) or 1, kind, user.get("color1"), user.get("color2"),
                   user.get("glow_color") if user.get("glow") else None, size=0.8)
    with p.row(6):
        for kind in KINDS[5:]:
            p.icon(user.get(kind) or 1, kind, user.get("color1"), user.get("color2"),
                   user.get("glow_color") if user.get("glow") else None, size=0.8)
    keep_colors = p.toggle("Keep my colors", False)
    with p.row(10):
        p.button("Use these icons", lambda: (p.close(), steal(user, keep_colors.value)), "green", 0.6)
        p.button("Cancel", p.close, "grey", 0.6)
    p.show()


def steal(user, keep_colors=False):
    old = gd.my_icons()
    gd.save("before", old)                       # for "Undo"
    icons = {k: user[k] for k in KINDS + ("death",) if user.get(k)}
    if not keep_colors:
        for k in ("color1", "color2", "glow_color"):
            if user.get(k) is not None:
                icons[k] = user[k]
        icons["glow"] = bool(user.get("glow"))
    gd.set_icons(**icons)
    gd.notify(f"Icons of {user.get('name', '?')} applied!")


@gd.mod_menu
def menu():
    p = gd.Popup("Icon stealer", 320)
    p.text("Steal the icons of a player by name", 0.45)
    with p.row(10):
        p.button("Search", lambda: (p.close(), ask()), "green", 0.6)
        p.button("Undo", lambda: (p.close(), undo()), "red", 0.6)
    p.show()


def ask():
    def found(user, error):
        if error or not user or not user.get("account_id"):
            gd.alert(f"Player not found ({error or 'no account'})")
        else:
            fetch(user["account_id"])
    gd.prompt("Player name:", lambda name: name and gd.servers.get_user(name, found), "Icon stealer")


def undo():
    before = gd.load("before")
    if not before:
        gd.alert("Nothing to undo")
        return
    gd.set_icons(**before)
    gd.notify("Your old icons are back")
