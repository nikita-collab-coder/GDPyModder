# Texture packs: put a pack folder (with files like GJ_GameSheet03-uhd.png) into pymodder/packs/
# and turn it on here. Shows gd.packs.
import gd

NAME = "Texture packs"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Use texture packs from the pymodder/packs folder. The higher in the list, the higher the priority."
ICON = "palette"


@gd.on_load
def loaded():
    saved = [p for p in gd.load("packs", []) if p in gd.packs.available()]
    if saved != gd.packs.active():
        gd.packs.apply(saved, reload=bool(saved or gd.packs.active()))


@gd.mod_menu
def menu():
    chosen = [p for p in gd.load("packs", []) if p in gd.packs.available()]
    rest = [p for p in gd.packs.available() if p not in chosen]
    p = gd.Popup("Texture packs", 380, 270)
    if not chosen and not rest:
        p.text("No packs yet. Put a pack folder into pymodder/packs\n"
               "(it holds files named like in Geometry Dash/Resources).", 0.42, (220, 220, 220))

    def order_changed(new):
        gd.save("packs", new)
        p.close()
        gd.later(menu)

    for i, name in enumerate(chosen):
        up = (lambda i=i: order_changed(chosen[:i - 1] + [chosen[i], chosen[i - 1]] + chosen[i + 1:])) if i else None
        p.cell(name, f"on, priority {i + 1}" + ("  (click: move up)" if i else ""), "palette", "Off",
               callback=up, on_button=lambda name=name: order_changed([c for c in chosen if c != name]),
               button_color="red")
    for name in rest:
        p.cell(name, "off", None, "On", on_button=lambda name=name: order_changed(chosen + [name]))
    with p.row(8):
        p.button("Apply", lambda: (p.close(), apply()), "green", 0.55)
        p.button("Open folder", gd.packs.open_folder, "blue", 0.55)
    p.show()


def apply():
    packs = [p for p in gd.load("packs", []) if p in gd.packs.available()]
    if packs == gd.packs.active():
        gd.notify("Nothing changed", 1.2)
        return
    gd.packs.apply(packs)          # reloads the textures (the game goes back to the menu)
