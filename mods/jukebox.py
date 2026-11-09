# Jukebox: play your own music files instead of level songs, and your own main menu music.
# Shows gd.music (song replacement through hooks) and gd.pick_file (the Windows "Open" dialog).
import os
import gd

NAME = "Jukebox"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "Replace any level song (Newgrounds or official) and the menu music with your mp3 / ogg files."
ICON = "music"

OFFICIAL = ["Stereo Madness", "Back On Track", "Polargeist", "Dry Out", "Base After Base", "Cant Let Go",
            "Jumper", "Time Machine", "Cycles", "xStep", "Clutterfunk", "Theory of Everything",
            "Electroman Adventures", "Clubstep", "Electrodynamix", "Hexagon Force", "Blast Processing",
            "Theory of Everything 2", "Geometrical Dominator", "Deadlocked", "Fingerdash", "Dash"]


def data():
    d = gd.load("songs", {})
    d.setdefault("songs", {})
    d.setdefault("official", {})
    d.setdefault("menu", None)
    return d


def apply_all():
    d = data()
    for sid, path in d["songs"].items():
        if os.path.isfile(path):
            gd.music.replace_song(int(sid), path)
        else:
            gd.log(f"jukebox: file not found {path}")
    for idx, path in d["official"].items():
        if os.path.isfile(path):
            gd.music.replace_official(int(idx), path)
    if d["menu"] and os.path.isfile(d["menu"]):
        gd.music.menu(d["menu"])


@gd.on_load
def loaded():
    apply_all()


def pick(kind, key, done=None):
    """kind: "songs" / "official" / "menu"."""
    def got(path):
        if not path:
            return
        d = data()
        if kind == "menu":
            d["menu"] = path
        else:
            d[kind][str(key)] = path
        gd.save("songs", d)
        apply_all()
        gd.notify(f"Now playing {os.path.basename(path)} there", 1.8)
        if done:
            done()
    gd.pick_file(got, "audio", "Choose a music file")


def remove(kind, key):
    d = data()
    if kind == "menu":
        d["menu"] = None
        gd.music.menu(None)
    else:
        d[kind].pop(str(key), None)
        if kind == "songs":
            gd.music.restore(int(key))
    gd.save("songs", d)
    if kind == "official":
        gd.notify("Restart the game to get the original song back", 2.5)


@gd.mod_menu
def menu():
    p = gd.Popup("Jukebox", 380, 270)
    d = data()
    lv = gd.level
    if lv and lv.data:
        sid = lv.data.song_id
        if sid:
            p.button(f"Replace this level's song ({sid})", lambda: (p.close(), pick("songs", sid)), "green", 0.55)
        else:
            idx = lv.data.official_song or 0
            p.button("Replace this level's song", lambda: (p.close(), pick("official", idx)), "green", 0.55)
    with p.row(8):
        p.button("Newgrounds song", lambda: (p.close(), ask_song()), "blue", 0.5)
        p.button("Official song", lambda: (p.close(), ask_official()), "blue", 0.5)
        p.button("Menu music", lambda: (p.close(), pick("menu", None, reopen)), "pink", 0.5)
    p.line()
    if not (d["songs"] or d["official"] or d["menu"]):
        p.text("No replacements yet", 0.45, (200, 200, 200))
    if d["menu"]:
        p.cell("Menu music", os.path.basename(d["menu"]), "music", "Remove",
               on_button=lambda: (remove("menu", None), p.close(), reopen()))
    for sid, path in sorted(d["songs"].items()):
        p.cell(f"Song {sid}", os.path.basename(path), "music", "Remove",
               on_button=lambda sid=sid: (remove("songs", sid), p.close(), reopen()))
    for idx, path in sorted(d["official"].items(), key=lambda kv: int(kv[0])):
        i = int(idx)
        p.cell(OFFICIAL[i] if i < len(OFFICIAL) else f"Official {i + 1}", os.path.basename(path), "music",
               "Remove", on_button=lambda idx=idx: (remove("official", idx), p.close(), reopen()))
    p.show()


def reopen():
    gd.later(menu)


def ask_song():
    gd.prompt("Newgrounds song ID:", lambda sid: sid and pick("songs", int(sid), reopen), "Jukebox", numeric=True)


def ask_official():
    gd.list_popup("Official song", OFFICIAL, lambda name, i: pick("official", i, reopen))
