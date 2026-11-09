# Record and replay clicks (macros). F7 - record / stop, F8 - play the macro of this level.
# Macros are saved in pymodder/saves/macro_bot/*.macro. The list is behind a button in the pause menu.
# Clicks are stored by physics ticks, so a replay is exact at any FPS (old 0.6 macros still load).
import gd

NAME = "Macro bot"
VERSION = "2.0"
AUTHOR = "PyModder"
DESCRIPTION = "F7 - record a run, F8 - replay it. The macro list is in the pause menu."

rec_key = gd.setting("rec_key", "F7", "Record / stop", kind="key")
play_key = gd.setting("play_key", "F8", "Play", kind="key")
loop = gd.setting("loop", False, "Repeat on every attempt")

macro = None
label = gd.Label("", x=8, y=-30, size=0.35, color=(255, 120, 120), anchor=(0, 0.5))


def file_name():
    lv = gd.level
    return "level_%s.macro" % (lv.id or lv.name or "unknown")


def status(text, color=(255, 120, 120)):
    label.text = text
    label.color = color


@gd.every(0.2)
def live():
    if macro and macro.recording:
        status("REC  %d clicks  %.1f s" % (macro.clicks, gd.physics_tick() / 480))
    elif macro and macro.playing:
        status("PLAY  %d / %d" % (macro.position, len(macro)), (120, 200, 255))


@gd.on_key(rec_key)
def toggle_record():
    global macro
    if not gd.in_level:
        return gd.notify("Open a level first")
    if macro and macro.recording:
        macro.stop()
        save(macro)
        return
    macro = gd.Macro()
    macro.record()                # the level starts again
    status("REC")


def save(m):
    if not len(m):
        status("")
        return gd.notify("Nothing to save")
    m.save(file_name())
    status("")
    gd.notify("Macro saved: %d clicks, %.1f s" % (m.clicks, m.duration), color=(120, 255, 120))


@gd.on_complete
def done(level):
    if macro and not macro.recording and macro.inputs and label.text.startswith("REC"):
        save(macro)               # recording stopped by itself at the end of the level


@gd.on_key(play_key)
def play():
    global macro
    if not gd.in_level:
        return gd.notify("Open a level first")
    if macro and macro.playing:
        macro.stop()
        return status("")
    if not gd.storage.exists(file_name()):
        return gd.notify("No macro for this level yet (F7 - record)")
    start(file_name())


def start(name):
    global macro
    macro = gd.Macro.load(name)
    macro.on_finish = lambda m: status("")
    macro.play(loop=loop.value)
    status("PLAY  0 / %d" % len(macro), (120, 200, 255))


@gd.on_exit
def left(level):
    status("")


def delete(name):
    def yes():
        gd.storage.delete(name)
        macro_list()
    gd.confirm("Delete %s?" % name, yes, title="Delete macro", yes="Delete", yes_color="red")


@gd.pause_button("GJ_playBtn2_001.png")
def macro_list():
    files = gd.storage.files(".macro")
    p = gd.Popup("Macros", width=340)
    if not files:
        p.text("Empty for now. Press F7 in a level to record.", 0.45)
    for name in files:
        with p.row():
            p.text(name, 0.4, align="left")
            p.button("Play", lambda n=name: (p.close(), gd.later(lambda: start(n))), size=0.5)
            p.button("X", lambda n=name: (p.close(), delete(n)), color="red", size=0.5)
    p.space(4)
    p.button("Folder", gd.storage.open_folder, color="grey", size=0.6)
    p.show()
