# A "BetterInfo"-like button on the level page: every stat of the level, your progress, copy the ID.
# Shows gd.on_layer (run code when a GD screen is built), node.add_button and the GD-style widgets.
import gd

NAME = "Level info+"
AUTHOR = "PyModder"
VERSION = "1.0"
DESCRIPTION = "A button on the level page: all level stats, your progress, GDDL tier, copy the ID / info."
ICON = "chart"

RATING_COLORS = {'mythic': (255, 120, 255), 'legendary': (255, 90, 90), 'epic': (255, 200, 60),
                 'featured': (255, 230, 120), 'rated': (120, 255, 120), 'unrated': (200, 200, 200)}


@gd.on_layer("LevelInfoLayer")       # the level page was built: layer is a gd.Node, level a gd.LevelData
def page(layer, level, *rest):
    if not level or not level.valid:
        return
    w, h = gd.screen()
    layer.add_button("GJ_infoIcon_001.png", lambda: show(level), x=30, y=h / 2 - 40, size=28,
                     id="level-info-plus-button")


def time_text(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 3600}h {seconds // 60 % 60}m" if seconds >= 3600 else f"{seconds // 60}m {seconds % 60}s"


def show(level):
    p = gd.Popup(level.name or "Level", 380, 270)
    p.text(f"by {level.creator or '?'}   ID {level.id}", 0.45, (200, 200, 200))
    with p.row(14):
        p.stat("downloads", level.downloads or 0)
        p.stat("likes", (level.likes or 0) - (level.dislikes or 0))
        p.stat("stars", level.stars or 0)
        p.stat("coins", level.coins or 0)
        p.stat("objects", level.object_count or 0)
    p.text(f"{level.difficulty} · {level.length} · {level.rating}", 0.45,
           RATING_COLORS.get(level.rating, (255, 255, 255)))
    if level.demon and level.id:
        gddl(p, p.text("GDDL tier: loading...", 0.42, (255, 150, 150)), level.id)
    p.line()
    p.text("Normal", 0.4, align="left")
    p.progress((level.normal_percent or 0) / 100, (0, 255, 0), 300, f"{level.normal_percent or 0}%")
    p.text("Practice", 0.4, align="left")
    p.progress((level.practice_percent or 0) / 100, (0, 200, 255), 300, f"{level.practice_percent or 0}%")
    p.text(f"Attempts {level.attempts or 0}   Jumps {level.jumps or 0}   Clicks {level.clicks or 0}", 0.4)
    p.line()
    song = f"song {level.song_id}" if level.song_id else f"official song {(level.official_song or 0) + 1}"
    lines = [
        f"Uploaded {level.upload_date or '?'} ago, updated {level.update_date or '?'} ago",
        f"Version {level.level_version or 0}, game version {level.game_version or 0}, {song}",
        f"Original ID {level.original_id or 0}   Requested stars {level.requested_stars or 0}",
        f"Editor time {time_text(level.edit_time)}   Copy password {level.password or 0}",
    ]
    for line in lines:
        p.text(line, 0.38, (220, 220, 220))
    if level.description:
        p.text(level.description, 0.38, (255, 255, 200))
    with p.row(10):
        p.button("Copy ID", lambda: copied(level.id), "blue", 0.55)
        p.button("Copy info", lambda: copied("\n".join(f"{k}: {v}" for k, v in level.info().items())),
                 "blue", 0.55)
        p.button("OK", p.close, size=0.55)
    p.show()


def gddl(p, label, level_id):
    """The Demon Difficulty List tier from gdladder.com (in the background)."""
    def got(r):
        if not p.is_open:
            return
        try:
            rating = r.json().get("Rating") if r.ok else None
        except Exception:
            rating = None
        label.text = f"GDDL tier {round(rating)} ({rating:.2f})" if rating else "GDDL: not rated yet"
    gd.http.get(f"https://gdladder.com/api/level/{level_id}", got)


def copied(text):
    gd.copy(str(text))
    gd.notify("Copied", 1.2)
