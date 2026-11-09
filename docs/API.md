# PyModder: Geometry Dash mods in Python

A mod is a `.py` file in `Geometry Dash/pymodder/mods` (or a folder with a `main.py`).
Files whose names start with `_` are not loaded (e.g. `_template.py`, a template to copy).

- **F6** or the PyModder button in the main menu opens the mods menu (on/off, settings, errors).
- **F5** reloads all mods without restarting the game.
- API version: 0.7-beta (`gd.__version__` = `"0.7.0-beta"`).
- Logs: `pymodder/logs/python.log` and `loader.log`. Errors in mods show up in game as a red message.

```python
import gd

NAME = "Death counter"        # shown in the mods menu (optional)
VERSION = "1.0"
AUTHOR = "Me"
DESCRIPTION = "Shows the percent you died at."
ICON = "skull.png"            # optional, see "Mod icon"
MENU_KEY = "F9"               # optional, see "Mod menu and menu key"

@gd.on_death
def died(player):
    gd.notify(f"Died at {gd.level.percent:.0f}%")
```

## Text in other languages

Strings can be in any language: `gd.Label`, `gd.notify` and popups switch to the Arial font
automatically when the text has characters the GD fonts don't have (Cyrillic, etc.):

```python
gd.notify("Привет! Мод загружен")
```

Save your `.py` files as UTF-8.

## Mod icon

The mods menu shows an icon next to every mod. PyModder looks for it in this order:

1. `ICON = "my_icon.png"` at the top of the mod: a `.png` next to the mod, a built-in icon name (`ICON = "skull"`,
   see below) or a GD frame name (`"GJ_infoIcon_001.png"`).
2. `icon.png` inside a folder mod (`mods/my_mod/icon.png`).
3. `<mod name>.png` next to a single-file mod (`mods/noclip.py` + `mods/noclip.png`).
4. Otherwise the default puzzle icon.

Any square picture works; 128×128 looks good.

**Built-in icons** (`pymodder/res/icons`, preview: `docs/icons.png`): `ICON = "name"`, also in `gd.menu_button("name")`
and `gd.pause_button("name")`; `gd.icon_path("name")` gives the `.png` path (for `gd.Sprite`, `p.image`),
`gd.icons()` lists them:

`skull`, `star`, `heart`, `clock`, `bolt`, `eye`, `gear`, `flag`, `trophy`, `music`, `shield`, `fire`, `crown`,
`target`, `play`, `ghost`, `mouse`, `palette`, `chart`, `wrench`, `door`, `chat`, `unlock`, `rainbow`, `speed`,
`puzzle`, `keyboard`, `bug`, `rocket`.

## Events

| Decorator | When | Arguments |
|---|---|---|
| `@gd.on_load` | the game started / the mod was reloaded | none |
| `@gd.on_menu` | the main menu opened | none |
| `@gd.on_level_start` | a level was opened | `level` |
| `@gd.on_attempt` | a new attempt | `level` |
| `@gd.on_death` | the player died | `player` |
| `@gd.on_complete` | the level was completed | `level` |
| `@gd.on_exit` | left the level | `level` |
| `@gd.on_jump` | click / jump (`return False` cancels it) | `player` |
| `@gd.on_release` | the button was released | `player` |
| `@gd.on_pause` / `@gd.on_resume` | paused / resumed | none |
| `@gd.on_quit` | the exit button of the pause menu (`return False` stays in the level) | none |
| `@gd.on_pause_button("restart")` | a pause menu button (`return False` cancels it) | none |
| `@gd.on_frame` | every frame in a level | `dt` (seconds) |
| `@gd.on_tick` | every frame everywhere | `dt` |
| `@gd.on_key("F1")` | a key was pressed (`return False` hides it from the game) | none |
| `@gd.on_key(setting)` | the key from a setting (the player can change it in the menu) | none |
| `@gd.on_key` | any key | `key` (string) |
| `@gd.on_unload` | the mod is being unloaded (before F5 or when switched off) | none |

Keys: `A`–`Z`, `0`–`9`, `F1`–`F12`, `NUM0`–`NUM9`, `SPACE`, `ENTER`, `ESC`, `TAB`, `BACKSPACE`,
`SHIFT`, `CTRL`, `ALT`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `DELETE`, `INSERT`, `HOME`, `END`, `PAGEUP`, `PAGEDOWN`.

If a handler raises an error, PyModder shows it once; after 100 errors in a row the handler is switched off.

## Game state

- `gd.in_level`, `gd.paused`: is a level running, is it paused.
- `gd.level`: the current level (or `None`):
  `name`, `id`, `creator`, `percent` (0–100), `attempts`, `deaths`, `best_run`, `completed`,
  `practice` (can be set: `gd.level.practice = True`), `platformer`.
- `gd.player`, `gd.player2`: the players (or `None`):
  - `x`, `y`, `rotation`, `is_player2`, `on_ground`, `gravity_flipped`
  - `dead` (can be set), `y_velocity` (can be set)
  - `mode`: `"cube"`, `"ship"`, `"ball"`, `"ufo"`, `"wave"`, `"robot"`, `"spider"`, `"swing"` (can be set)
  - `color`, `color2`: `(r, g, b)` (can be set), `visible`, `scale` (can be set)
  - `flip_gravity()` flips gravity (`flip_gravity(True/False)` sets it)
- `gd.screen()`: screen size `(width, height)`, usually about 569×320.
- `gd.fps()`: the current FPS.
- `gd.mods()`: list of mods: `name`, `title`, `version`, `author`, `ok`, `enabled`, `error`, `icon`.
- `gd.attempt_time`: seconds since the attempt started (level time, follows `gd.speed`).
- `gd.mouse_pos()`: mouse position `(x, y)` in game screen coordinates.
- `gd.gd_version`: the game version, `gd.__version__`: the API version.
- `gd.popups_open()`: is a PyModder popup open.
- `gd.pause_layer`: the pause menu layer while it is open (or `None`).

## Controlling the game

- `gd.speed(0.5)` slows the game down 2×, `gd.speed(1)` is normal, `gd.speed()` returns the current speed.
  The music and sounds follow the speed (lower pitch); `gd.speed(0.5, audio=False)` changes only the game.
  In a level (and in the editor playtest) this is GD's own time speed, the one of the testmode speed slider:
  the physics really slows down, GD shows its testmode label and **an attempt with a changed speed does not
  save progress** (same as GD's own speed control). In the menus it slows down the whole game (animations).
  The speed stays when you open another level. `gd.audio_speed(0.8)` changes only the music / sounds.
- `gd.press(button="jump")`, `gd.release(...)`, `gd.click(...)`: hold / release / click a player button.
  `button`: `"jump"`, `"left"`, `"right"` (platformer); `player2=True` for the second player.
- `gd.hold(0.5, "right")`: hold a button for 0.5 seconds.
- `gd.pause()`, `gd.restart()`, `gd.restart(full=True)` (from the very start, even in practice).
- `gd.quit_level()`: leave the level right now (no confirmation, `gd.on_quit` handlers are skipped).
- `gd.pause_action("restart")`: press a pause menu button from code (handlers are skipped), see below.
- `gd.game_var("0024")` reads a GD option, `gd.game_var("0024", True)` changes it.
- `gd.open("file.txt")` opens a file / folder (relative to the mod folder) or a `https://...` link.
- `gd.sound("ding.wav")` plays a `.wav` from the mod folder.

## Pause menu buttons (Confirm Exit)

`gd.on_quit` runs when the player presses the exit button in the pause menu.
Return `False` to stay in the level, and leave later with `gd.quit_level()`:

```python
@gd.on_quit
def ask():
    gd.confirm("Leave the level?", on_yes=gd.quit_level, title="Confirm exit",
               yes="Leave", yes_color="red")
    return False             # don't leave yet
```

The same works for other buttons with `gd.on_pause_button(button)`:

| `button` | Pause menu button |
|---|---|
| `"quit"` | exit (same as `gd.on_quit`) |
| `"restart"` | restart |
| `"restart_full"` | full restart (practice mode) |
| `"practice"` / `"normal"` | enter / leave practice mode |
| `"resume"` | resume |
| `"edit"` | edit the level (own levels) |

```python
@gd.on_pause_button("restart")
def ask_restart():
    gd.confirm("Restart the level?", lambda: gd.pause_action("restart"))
    return False
```

`gd.pause_action(button)` presses the button without running the handlers again (returns `True` if done).
A complete example is the `confirm_exit.py` mod.

## Unlock all icons

```python
gd.unlock_icons()          # every icon, color, trail, death effect... is unlocked in the garage
gd.unlock_icons(False)     # locks come back
```

Nothing is written to the save: when the mod is switched off the locks come back
(icons you selected stay selected). Example: the `icon_unlock.py` mod.

## Mouse and keyboard simulation

Input goes through the normal game path: GD buttons, menus and PyModder popups react to it.

```python
gd.tap(284, 160)               # mouse click at a screen point (gd.screen() is the screen size)
gd.tap(30, 30, hold=0.2)       # click and hold for 0.2 s
gd.touch_down(100, 100)        # drag: press...
gd.touch_move(200, 100)        # ...move...
gd.touch_up(200, 100)          # ...release
gd.key_tap("SPACE")            # press and release a key
gd.key_down("RIGHT"); gd.after(1, lambda: gd.key_up("RIGHT"))
```

Keys pressed with `key_down` / `key_tap` reach the game, but `@gd.on_key` handlers don't see them
(so a mod can't loop on itself).

## Macros (.macro)

`gd.Macro` records and replays player input (jump, left, right, both players) **by physics ticks**:
GD 2.2 moves the game in fixed steps (240 per second) and a click is stored with the step it was handled in,
so a replay is exact at any FPS and any `gd.speed`. GD counts 2 ticks per step: 480 ticks = 1 second.

```python
m = gd.Macro()
m.record()                      # the level restarts, input is recorded
# ... play ...
m.stop()
m.save("my_run.macro")          # pymodder/saves/<mod>/my_run.macro

m = gd.Macro.load("my_run.macro")
m.on_finish = lambda m: gd.notify("Done")
m.play()                        # the level restarts and the input is replayed
```

- `record(restart=True)`: on every death the recording starts again (the last attempt stays),
  it stops by itself at the end of the level. `restart=False` starts on the next attempt.
  Practice mode works: going back to a checkpoint drops the clicks after it. Start positions work too.
- `play(restart=True, loop=False)`: `loop=True` replays on every attempt. If the level restarts from the start
  the macro stops; at a practice checkpoint it goes on from that point.
  While it plays, your own clicks are ignored (`m.block_input = False` before `play()` lets them through).
- While a macro records or plays, GD's "click between steps" and PyModder's `gd.click_between_frames`
  are off (so every step is a full step and the replay is exact).
- `stop()`, `recording`, `playing`, `duration` (seconds), `ticks`, `clicks`, `position` (inputs already played),
  `len(m)` (number of inputs), `inputs`.
- Build a macro in code: `m.add(1.5, True)` / `m.add(1.6, False)` (seconds), `m.add_tick(720, True)` (ticks)
  or `m.click(1.5, length=0.1, button="jump")`.
- `gd.physics_tick()`: GD's tick counter in the running level (0 at the start of an attempt).
- File format (JSON): `{"format": "pymodder-macro", "version": 2, "tps": 240,
  "inputs": [[tick, pressed 1/0, button 1-3, player2 0/1], ...]}`. Old 0.6 files (`version` 1, by time)
  still load - their times are converted to ticks.

A ready example is the `macro_bot.py` mod (F7 records, F8 replays, list in the pause menu).

## Mod files (.json and .macro)

`gd.storage` keeps the mod's own files on disk, in `Geometry Dash/pymodder/saves/<mod>/`.
Only `.json` and `.macro`, only inside that folder (subfolders are fine: `"runs/1.macro"`).

```python
gd.storage.save("stats.json", {"best": 87, "names": ["a", "b"]})
data = gd.storage.load("stats.json", {})        # {} if the file is missing or broken

stats = gd.storage.file("stats.json", {"runs": 0})   # a dict that saves itself
stats["runs"] += 1
stats["names"].append("c"); stats.save()              # nested changes: save by hand
```

| Function | What it does |
|---|---|
| `gd.storage.save(name, data)` | write (dict, list, number, string or `gd.Macro`) |
| `gd.storage.load(name, default=None)` | read |
| `gd.storage.file(name, default)` | a dict bound to a `.json` file (saves automatically) |
| `gd.storage.exists(name)`, `gd.storage.delete(name)` | does the file exist / delete it |
| `gd.storage.files(".macro")` | the mod's files (no argument: all) |
| `gd.storage.path(name)` | full path to a file (no name: to the folder) |
| `gd.storage.open_folder()` | open the folder in Explorer |

`gd.save` / `gd.load` still work: they use one shared file per mod, `mods/data/<mod>.json`.

## Pictures and textures

```python
star = gd.Sprite("star.png", x=100, y=200)        # .png/.jpg from the mod folder, a GD frame or a Resources file
star.scale = 2; star.rotation = 45; star.opacity = 128; star.color = (255, 100, 100)
star.move_to(300, 200, 0.5)                       # animations: move_to, scale_to, fade_to, rotate_by, spin
star.on_click = lambda: gd.notify("Click!")
star.image = "GJ_infoIcon_001.png"                # change the picture
star.remove()

follow = gd.Sprite("star.png", world=True)        # in the level (moves with the camera)
@gd.on_frame
def f(dt):
    if gd.player:
        follow.move(gd.player.x, gd.player.y + 40)
```

`gd.Sprite(image, x, y, scale=1, world=False, z=None, rotation=0, opacity=255, color=None, visible=True,
smooth=True, width=None, height=None, flip_x=False, anchor=None, on_click=None)`

- Properties: `x`, `y`, `scale`, `rotation`, `opacity`, `color`, `visible`, `flip_x`, `image`, `size`, `on_click`;
  methods `move(x, y)`, `contains(x, y)`, `stop()`, `remove()`.
- Pictures from files are shown like GD `-hd` textures: 2 pixels = 1 screen point.
  `width=` / `height=` set the size in points. `smooth=False` turns off smoothing (pixel art).
- Screen sprites stay when the scene changes; `world=True` sprites disappear when you leave the level
  (and come back the next time they are used).

Textures and frames:

- `gd.texture("bg.png", smooth=True)` loads a picture (`.width`, `.height` in pixels, `.smooth`).
- `gd.add_frame("my_icon.png", "icon.png")` makes a picture a frame with that name: use it
  in `gd.Sprite`, `p.image`, `gd.menu_button`, buttons.
- `gd.add_frame("GJ_infoIcon_001.png", "my_info.png")` **replaces** a GD frame (like a texture pack) for everything
  created after that. For the exact size use a picture as big as the `-uhd` version.
  `gd.restore_frame(name)` brings the original back (done automatically when the mod is switched off / reloaded).
- `gd.load_frames("sheet.plist")` loads your own sprite sheet (`.plist` + `.png`).
- `gd.frame_exists("name.png")`: does such a frame exist.

## Messages and labels

- `gd.notify(text, seconds=2.5, color=(r, g, b))`: a message at the top of the screen.
- `gd.log(...)` writes to `python.log` (`print` does too).
- `gd.Label(text, x, y, size=0.5, color=(r, g, b), font=None, anchor=None)`: a label that stays on screen
  when the scene changes. Negative `x` / `y` count from the right / top edge. `anchor=(0, 1)` pins the top left corner.
  - `lb.text = "..."`, `lb.color = (r, g, b)`, `lb.move(x, y)`, `lb.show()`, `lb.hide()`, `lb.remove()`
  - Fonts: `None` (bigFont), `"goldFont.fnt"`, `"chatFont.fnt"`, or a TTF name (`"Arial"`).
    Text with Cyrillic and other non-Latin letters uses Arial automatically.

```python
fps_label = gd.Label("", x=5, y=-5, size=0.4, anchor=(0, 1))

@gd.every(0.5)            # or gd.every(0.5, func)
def upd():
    fps_label.text = f"FPS {gd.fps():.0f}"
```

## Quick popups

```python
gd.alert("Done!", title="Info")

gd.confirm("Delete the save?", on_yes=lambda: gd.save("best", 0))
gd.confirm("Leave?", on_yes=gd.quit_level, on_no=lambda: gd.notify("Staying"),
           yes="Leave", no="Stay", yes_color="red")

gd.prompt("Your name:", on_done=lambda name: gd.notify("Hi, " + name), placeholder="Name")
gd.prompt("Speed:", on_done=gd.speed, default="1", numeric=True)

gd.choose(["Easy", "Normal", "Hard"], on_pick=lambda i, name: gd.notify(name), title="Difficulty")
```

| Function | What it shows |
|---|---|
| `gd.alert(text, title="Info", button="OK", on_close=None)` | a message with an OK button |
| `gd.confirm(text, on_yes, title="Are you sure?", yes="Yes", no="No", on_no=None, yes_color="green", no_color="grey")` | Yes / No; ESC and the X count as "No" |
| `gd.prompt(text, on_done, title="", default="", placeholder="", button="OK", numeric=False, on_cancel=None)` | a text box; `on_done(text)` after OK / Enter (`numeric=True` gives a number) |
| `gd.choose(options, on_pick, title="Choose", text="", cancel="Cancel")` | one button per option; `on_pick(index, option)` |

All of them return the `gd.Popup`, so you can close it from code: `p = gd.alert(...); p.close()`.

## Popups (gd.Popup)

```python
p = gd.Popup("My mod", width=320)          # height=None fits the content; long popups scroll
p.text("Hello!", size=0.5)
name = p.input("", placeholder="Name")
p.toggle("Enabled", True, lambda v: gd.log(v))
p.slider("Volume", 50, 0, 100, lambda v: gd.log(v))
p.choice("Mode", ["easy", "hard"], "easy", lambda v: gd.log(v))
with p.row():                                 # items in one row
    p.button("OK", lambda: gd.notify("Hi, " + name.text))
    p.button("Close", p.close, color="grey")
p.show()
```

`gd.Popup(title, width=320, height=None, on_close=None, dim=120, close_button=True, footer=0)`

| Method | What it adds |
|---|---|
| `p.text(text, size=0.5, color, align="center", font=None, width=None, wrap=True)` | wrapped text |
| `p.button(text, callback, color="green", size=0.8, width=None, image=None)` | a GD button; `color`: `"green"`, `"grey"`, `"red"`, `"blue"`, `"pink"`, `"dark"` |
| `p.image(name, callback=None, size=None)` | a picture (GD frame or `.png` from the mod folder); with `callback` it's a button |
| `p.toggle(text, value=False, callback)` | a checkbox, `callback(bool)` |
| `p.slider(text, value, min, max, callback, step=None, fmt=None, on_move=None)` | a slider; `callback` on release, `on_move` while dragging |
| `p.input(value="", placeholder="", callback, on_change=None, numeric=False, max_len=100)` | a text box; `callback(text)` on Enter, Ctrl+V pastes |
| `p.choice(text, options, value, callback)` | a button that cycles through options |
| `p.keybind(text, value="F1", callback)` | key picker (press the button, then a key) |
| `p.color(text, value=(255, 255, 255), callback)` | a color row: a click opens the color picker, `callback((r, g, b))` |
| `p.swatch(value, height=30)` | a color sample (`.value = (r, g, b)` changes it) |
| `p.space(8)`, `p.line()` | spacing, a separator |
| `with p.row(gap=8):` | everything inside goes in one row |

Every method returns the item: `toggle` / `slider` / `choice` / `keybind` / `color` have `.value`, `input` and `text` have `.text`.
Sliders look and work like GD's own (`slidergroove.png`, `sliderBar.png`, `sliderthumb.png`).

`gd.pick_color((255, 0, 0), on_done, title="Color")`: a color picker popup (red / green / blue sliders, a preview,
a `#RRGGBB` field); `on_done((r, g, b))` after OK.
Custom items: `p.add(gd.Button(...))`; any item takes `x=`, `y=` (position inside the popup, from the center).

Also: `p.show()`, `p.close()`, `p.refresh()` (rebuild after changes), `p.clear()`, `p.scroll_to(0..1)`, `p.is_open`.
ESC closes the top popup. The mouse wheel scrolls (direction: `invert_scroll` in `config.json`).

## Mod settings

Settings are shown in the mods menu (gear button) and saved automatically.

```python
power = gd.setting("power", 5, "Power", min=1, max=10)        # number -> slider
enabled = gd.setting("enabled", True, "Enabled")              # bool -> checkbox
mode = gd.setting("mode", "easy", "Mode", options=["easy", "hard"])
key = gd.setting("key", "F3", "Key", kind="key")
nick = gd.setting("nick", "", "Nick", kind="text")

@gd.on_key(key)            # the key the player picked in the settings
def pressed():
    if enabled.value:
        gd.notify(f"power {power.value}")

@power.on_change
def changed(v):
    gd.log("new power", v)
```

`kind`: `"bool"`, `"int"`, `"float"`, `"text"`, `"choice"`, `"key"`, `"color"` (usually detected by itself;
a default like `(255, 0, 0)` is a color: `color.value` is an `(r, g, b)` tuple).
`s.value` reads / changes it (`s.set(v)` does the same, handy as a callback), `s.reset()` restores the default. Also `description=`, `step=`.

Headers, text and buttons between the settings (they are shown in the order they are created):

```python
gd.setting_header("Visual")                              # a section title
color = gd.setting("color", (0, 255, 255), "Trail color")
gd.setting_text("Colors are saved per mod.")             # a hint line
gd.setting_space()

@gd.setting_button("Reset stats", color="red", description="Sets everything back to 0")
def reset():
    gd.confirm("Reset?", lambda: gd.save("stats", {}))
# or: gd.setting_button("Open folder", lambda: gd.open("."), color="blue")
```

`gd.open_settings()` opens the mod settings from code (also when the mod has its own `gd.mod_menu`).

## Mod menu and menu key

A mod can have a key that opens its menu anywhere in the game (in a level the game pauses first).
Pressing the key again closes the menu.

```python
MENU_KEY = "F9"            # at the top of the mod...
gd.menu_key("F9")          # ...or from code (same thing)
```

The player can change the key: it appears in the mod settings as "Menu key".
By default the menu is the mod settings. Your own menu:

```python
@gd.mod_menu
def menu():
    p = gd.Popup("Rainbow")
    p.slider("Speed", speed.value, 0.1, 5, speed.set)
    p.button("Reset", reset)
    p.show()
```

The gear button in the mods list opens the same menu. `gd.open_menu()` opens it from code.
Examples: `quick_menu.py` (F4: restart, practice, game speed), `slowmo.py` (its own menu with speed presets),
`rainbow.py` (F9 opens its settings).

## Buttons in the game menus

```python
@gd.menu_button("my_icon.png")     # bottom row of the main menu; a GD frame, a .png from the mod folder or short text
def clicked():
    gd.alert("Hello from the menu!")

@gd.pause_button("GJ_infoIcon_001.png")   # bottom left of the pause menu
def info():
    gd.notify(f"Attempt {gd.level.attempts}")

gd.open_mods_menu()                # open the mods menu (like F6)
```

### Buttons on other screens

```python
@gd.level_button("my_icon.png")                 # the page of an online level
def on_level(layer, level):                      # layer - gd.Node, level - gd.LevelData
    gd.copy(str(level.id))

@gd.end_button(text="Share", position="bottom-right")   # the level complete screen, a GD text button
def share(layer):
    gd.copy(f"I beat {gd.level.name} in {gd.level.attempts} attempts!")

@gd.editor_button("wrench", position="right")   # the level editor (a built-in icon)
def tool(editor_ui):
    gd.notify(f"{gd.editor().object_count} objects")

@gd.level_cell_button("GJ_infoIcon_001.png")    # every level in level lists (left of the View button)
def cell(cell, level):
    gd.notify(level.name)
```

| Decorator | Where |
|---|---|
| `gd.level_button` | online level page (`LevelInfoLayer`), `f(layer, level)` |
| `gd.my_level_button` | the page of your own level (`EditLevelLayer`), `f(layer, level)` |
| `gd.levels_button` | level lists / search results (`LevelBrowserLayer`) |
| `gd.creator_button` | the Create screen (`CreatorLayer`) |
| `gd.garage_button` | the icon kit (`GJGarageLayer`) |
| `gd.editor_button` | the level editor (`EditorUI`), `f(editor_ui)` |
| `gd.editor_pause_button` | the editor pause menu |
| `gd.end_button` | the level complete screen (`EndLevelLayer`) |
| `gd.profile_button` | a player profile (`ProfilePage`) |
| `gd.options_button` | the GD options (`OptionsLayer`) |
| `gd.level_cell_button` | every level cell in lists, `f(cell, level)` |

All of them are `gd.screen_button(place, image, position=..., offset=(dx, dy), size=..., text=..., color=...)`
with a place name: `"level"`, `"my_level"`, `"levels"`, `"main_levels"`, `"search"`, `"level_list"`,
`"creator"`, `"garage"`, `"editor"`, `"editor_pause"`, `"pause"`, `"end"`, `"profile"`, `"options"`, `"menu"`,
`"level_cell"`, or any layer class name (`gd.screen_button("SecretLayer2", ...)`).

- `position`: `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"`, `"left"`, `"right"`, `"top"`,
  `"bottom"`. On popups (end screen, profile, options) it is a corner / side of the popup window.
  Several buttons at one place are stacked. If a GD button is in the way, pick another position or
  move it with `offset=(dx, dy)`.
- `gd.screen_button("menu", ...)` / `("pause", ...)` without `position` is the same as `gd.menu_button` /
  `gd.pause_button`.
- The function gets the layer (`gd.Node`) and the arguments of the layer's init (a `GJGameLevel` becomes
  `gd.LevelData`); it can take fewer arguments (`def f():` works).
- The buttons work on popups too: PyModder gets the click before GD.
- For exact placement next to a GD button use `gd.on_layer` + `node.add_button` (see below).

## Drawing (Draw)

```python
d = gd.Draw()              # on screen; gd.Draw(world=True) uses level coordinates (next to the player)
d.line(0, 0, 100, 100, color=(255, 0, 0), width=2)
d.dot(50, 50, radius=3)
d.rect(10, 10, 40, 20, color=(0, 255, 0), fill=False, border=1)
d.circle(200, 150, 30, color=(0, 0, 255))
d.polygon([(0, 0), (30, 0), (15, 25)], color=(255, 255, 0))
d.clear()                  # erase everything (usually at the start of every frame)
d.visible = False
d.remove()
```

Colors are `(r, g, b)` or `(r, g, b, a)` from 0 to 255. World drawings disappear when you leave the level.

## Time and threads

- `gd.after(seconds, func)`: call after N seconds (or as a decorator `@gd.after(1)`).
- `gd.every(seconds, func)`: call every N seconds (or `@gd.every(0.5)`).
- `gd.later(func)`: call on the next frame on the game thread.
- `gd.background(func, *args)`: run in the background (internet, big files).
  **Don't touch the game from a background thread**: pass the result with `gd.later(...)`.

```python
import urllib.request

def fetch():
    text = urllib.request.urlopen("https://example.com").read().decode()
    gd.later(lambda: gd.alert(text[:200]))

gd.background(fetch)
```

## Saving

- `gd.save("best", 87)` / `gd.load("best", 0)`: the value survives a game restart
  (`pymodder/mods/data/<mod>.json`).
- `MOD_DIR`: the mod folder (for your own files).

## Game screens and their buttons (nodes and IDs)

Every GD screen is a tree of cocos2d nodes. `gd.on_layer` runs your code when a screen / popup is built,
so you can add buttons and labels to it or hide / move what is there.

```python
@gd.on_layer("LevelInfoLayer")             # the level page; arguments are those of LevelInfoLayer::init
def page(layer, level, *rest):             # layer: gd.Node, level: gd.LevelData
    layer.add_button("GJ_infoIcon_001.png", lambda: gd.alert(level.name), x=30, y=160)
    layer.add_label(f"ID {level.id}", x=284, y=20, size=0.4, color=(255, 255, 0))

@gd.on_layer("MenuLayer")
def menu(layer):
    btn = layer.find(id="newgrounds-button")
    if btn:
        btn.visible = False
```

- Works for any class with `Class::init` in the bindings; popups like `PauseLayer`, `ProfilePage`
  (`(layer, account_id, own_profile)`) are known too. Other classes: `gd.on_layer("X", entry="X::setup")`.
  If the screen is already open when the mod loads (F5), the handler runs for it right away.
- `gd.scene()`, `gd.current_layer()` (the main layer on screen), `gd.node(ptr)`.
- Search: `node.find(id=..., cls="CCMenu", base="CCSprite", selector="onPlay", frame="GJ_playBtn_001.png",
  text="Play", tag=5, where=lambda n: n.x > 100)` and `node.find_all(...)`; `gd.find(...)` searches the scene.
- **IDs** like in Geode's Node IDs: buttons get one from their action (`MenuLayer::onPlay` ->
  `play-button`, `onGarage` -> `icon-kit-button`, others `onFooBar` -> `foo-bar-button`), menus that hold
  them get `main-menu`, `bottom-menu`, ... Set your own: `node.id = "my-thing"`.
- A node: `x`, `y`, `pos`, `move(x, y)`, `scale`, `rotation`, `visible`, `z`, `tag`, `anchor`, `size`,
  `world_pos`, `color`, `opacity`, `text` (labels), `parent`, `children`, `add(child)`, `remove()`,
  `cls`, `is_a("CCMenu")`, `to_local(x, y)`.
- Buttons: `btn.click()`, `btn.enabled`, `btn.selector`, `@btn.on_click def f(original, button): ...`
  (call `original()` to keep the game's action). Removed / restored when the mod is reloaded.
- `node.add_button(image or text=..., callback, x, y, size)` adds a GD button (with the GD click animation);
  `node.add_label(text, x, y, size, color, font)` adds text. In a GD popup add buttons to its menu:
  `layer.find(cls="CCMenu").add_button(...)` (a new menu does not get clicks inside a popup).
- Sprites / actions: `node.set_frame("name.png")`, `node.animate(["a.png", "b.png"], fps=12)`,
  `move_to(x, y, t)`, `scale_to`, `fade_to`, `rotate_to`, `tint_to`, `spin(speed)`, `stop()`.
- `gd.open_screen("menu" | "creator" | "search" | "icon_kit" | "main_levels")`,
  `gd.open_screen("levels", "Bloodbath")` / `gd.open_screen("levels", "10565740")` (search results / by ID).

## Level information (gd.LevelData)

`gd.level.data` in a level, the `level` argument of `on_layer("LevelInfoLayer")`, `gd.level_data(ptr)`:

`id`, `name`, `creator`, `description`, `difficulty` (`"Easy"` ... `"Extreme Demon"`, `"Auto"`, `"N/A"`),
`stars`, `length` (`"Tiny"` ... `"XL"`, `"Platformer"`), `rating` (`"unrated"`, `"rated"`, `"featured"`,
`"epic"`, `"legendary"`, `"mythic"`), `demon`, `likes`, `dislikes`, `downloads`, `coins`, `coins_verified`,
`song_id`, `official_song`, `object_count`, `game_version`, `level_version`, `attempts`, `jumps`, `clicks`,
`normal_percent`, `practice_percent`, `account_id`, `user_id`, `original_id`, `password`, `upload_date`,
`update_date`, `edit_time`, `two_player`, `requested_stars`, `level_string` (decoded objects),
`objects()` (a list of dicts), `info()` (a dict with all of it).
`gd.decode_level(data)` turns GD level data (`H4sI...`) into the object string, `gd.parse_level(text)` -> `(header, objects)`.

## Your icons

```python
icons = gd.my_icons()              # {'cube': 12, 'ship': 3, ..., 'color1': 0, 'color2': 3, 'glow': True}
gd.set_icons(cube=35, color1=12, color2=5, glow=True)
gd.color(12)                       # (r, g, b) of the GD color 12
p.icon(kind="ship", icon=5, color1=3, color2=12)    # a player icon in a popup; p.icon(mine=True)
```

## Objects and hitboxes

- `gd.objects()` / `gd.objects(1)` / `gd.objects(where=lambda o: o.x > 500)`: objects in the level
  (`gd.GameObject`: `object_id`, `x`, `y`, `rotation`, `scale`, `visible`, `color`, `rect`, ...).
- `gd.object_count()`, `gd.start_positions()`, `gd.world_layer()`,
  `gd.add_to_world(node, x=..., y=...)` (a node that moves with the level, like the "Animated fire" mods).
- `gd.show_hitboxes(True)` shows hitboxes (like practice mode's option, but always).

## Level editor

```python
@gd.on_editor_open
def opened(editor):                # gd.Editor
    gd.notify(f"{len(editor.objects())} objects")

@gd.on_object_added
def added(obj):                    # gd.GameObject
    gd.log("placed", obj.object_id, obj.x, obj.y)
```

Events: `on_editor_open`, `on_editor_exit`, `on_playtest`, `on_stop_playtest`, `on_object_added`,
`on_object_removed`, `on_object_moved`, `on_paste`. `gd.editor()` (None outside the editor):
`objects()`, `add_object(id, x, y)`, `remove_object(obj)`, `move_object(obj, dx, dy)`, `selected()`,
`select(objs)`, `deselect()`, `paste(level_string)`, `level_string`, `playtest()`, `save()`, `undo()`,
`redo()`, `level`. `gd.in_editor`. With `gd.http` this is enough for shared editing (send the objects you
place to a server, `paste` what others placed).

## Internet and the GD servers

```python
@gd.on_load
def loaded():
    gd.http.get("https://api.github.com", got)      # in the background, got() runs on the game thread

def got(r):                        # r.ok, r.status, r.text, r.json(), r.data, r.error
    if r.ok:
        gd.notify(r.json()["current_user_url"])

gd.servers.get_user("RobTop", lambda user, error: gd.log(user))          # {'name', 'account_id', 'stars', ...}
gd.servers.get_user_info(71, on_done)          # a full profile with every icon id and color
gd.servers.search_levels("Bloodbath", on_done) # [dict] (also kind=1 most downloaded, 3 trending, ...)
gd.servers.get_level(128, on_done) / gd.servers.download_level(128, on_done)   # with 'level_string'
gd.servers.request("getGJScores20.php", {"type": "top"}, on_done)              # any endpoint -> text
```

`gd.http.post(url, data, on_done)`, `gd.http.download(url, path, on_done)`. Without `on_done` the call
blocks (use it only in `gd.background`). Don't spam the GD servers: they ban IPs that send too much.

## Pictures from files and links (also animated GIF)

```python
pic = gd.image("cat.gif")                  # PNG / JPG / GIF from the mod folder or bytes
spr = pic.sprite(width=60)                 # a gd.Node; GIFs play
layer.add(spr, x=100, y=100)
gd.image("https://example.com/a.png", lambda pic, error: pic and layer.add(pic.sprite(width=80)))
pic.add_frame("myFrame.png")               # use it as a sprite frame (replace a GD texture)
```

Links load in the background and are cached in `pymodder/cache/images`.

## Texture packs

Put a pack folder into `pymodder/packs/<name>` (files named like in `Geometry Dash/Resources`).

```python
gd.packs.available()               # ['MyPack', ...]
gd.packs.apply(["MyPack"])         # first = highest priority; reloads the textures (back to the menu)
gd.packs.apply([])                 # the original textures
gd.packs.active(), gd.packs.open_folder()
```

The **Texture packs** mod does this from a menu and remembers the choice.

## Music

```python
gd.music.replace_song(467339, "my_song.mp3")   # levels with this Newgrounds song play your file
gd.music.replace_official(0, "sm.mp3")         # 0 = Stereo Madness, 1 = Back On Track, ...
gd.music.menu("menu.mp3")                      # menu music (None = the original)
gd.music.play("a.mp3"), gd.music.stop(), gd.music.effect("click.ogg")
gd.music.position, gd.music.length, gd.music.playing, gd.music.song_path(467339)
gd.pick_file(lambda path: gd.log(path), "audio")   # the Windows "Open" dialog ("audio", "image", "any")
```

## GD-style popups and widgets

```python
gd.gd_alert("<cg>Green</c> and <cr>red</c> text", "Title", "OK", "Cancel", lambda second: ...)
gd.list_popup("Levels", [{"title": "Bloodbath", "subtitle": "by Riot", "button": "View"}, "Just text"],
              lambda item, index: gd.log(item))

p = gd.Popup("Stats", 380, 260)
p.cell("Row", "subtitle", icon="star", button="View", on_button=lambda: ...)  # a brown GD list row
bar = p.progress(0.5, text="50%")          # bar.value = 0.75
with p.row(12):
    p.stat("downloads", 12345)             # an icon + a number: stars, likes, coins, time, objects ...
    p.stat("likes", 678)
p.tabs(["Info", "Settings"], build)        # build(popup, index) adds the page after the tabs
p.show()
```

## Clipboard, clicks between frames, FPS

- `gd.copy("text")` / `gd.paste()`.
- `gd.click_between_frames(True)`: experimental - a click is applied at the moment you pressed, not at the
  next frame (the **Click between frames** mod).
- `gd.fps_cap(240)` sets the FPS limit, `gd.fps_cap()` returns it; `gd.fps()` - the real FPS.

## Example mods

`level_info_plus` (level page stats, like BetterInfo), `hitboxes`, `icon_stealer`, `jukebox`,
`texture_packs`, `menu_plus` (main menu tweaks), `cbf` (click between frames), and the older ones:
`death_counter`, `noclip`, `slowmo`, `macro_bot`, `quick_menu`, `trail`, `rainbow`, `cps`, `confirm_exit`,
`icon_unlock`, `sprite_demo`. They are short: open them to see how things are done.

## Advanced: hooks

- `@gd.hook("PlayLayer::destroyPlayer")` hooks any game function by its name from the Geode bindings
  (`pymodder/bindings`). The handler gets `original` and the arguments; `return original()` runs the game code.
- `gd.function("PlayLayer::resetLevel")(gd.layer)` calls a game function, `gd.address(name)` returns its address.
- `gd.mem` reads / writes memory, `gd.cocos` wraps cocos2d (nodes, sprites, labels), `gd.layer` is the PlayLayer.
- Arguments: pointers are ints; `CCPoint` / `CCSize` / `CCRect` passed by value are pointers to a copy
  (`gd.cocos.point(x, y)`); `std::string` - `s = gd.mem.StdString("text")`, pass `s.addr`, then `s.free()`;
  a returned `std::string`: `gd.mem.returned_string(lambda r: f(this, r))`; `std::vector` -
  `gd.mem.std_vector(addr)`. `gd.mem.bases(obj)` / `gd.mem.is_a(obj, "CCMenu")` read the C++ class info.

```python
@gd.hook("PlayLayer::destroyPlayer")
def no_death(original, this, player, obj):
    if gd.load("god", False):
        return             # original is not called: the player doesn't die
    return original()
```

## Native code (C++)

When Python is too slow (or you already have C++ code), put a 64-bit `.dll` next to the mod and load it:

```python
import ctypes, gd

lib = gd.load_dll("mymod.dll")                       # path relative to the mod
add = lib.func("add", ctypes.c_int, ctypes.c_int, ctypes.c_int)
gd.log(add(2, 3))
lib.reset_jumps()                                    # quick call: int result, no type checks

@lib.on("jump")                                      # api->emit("jump", "...") from C++
def jumped(data):
    gd.notify("C++ says: " + data)

lib.expose("percent", lambda arg: gd.level.percent if gd.level else 0)   # api->call("percent", "")
```

The C++ side includes `pymodder/sdk/pymodder.h`. PyModder calls your exported
`pymodder_init(const PyModderAPI* api)` after loading (return 0 = ok) and `pymodder_unload()` before the
mod is unloaded (F5, mod switched off). The DLL is copied to `pymodder/cache/native/` before loading,
so you can rebuild it while the game runs and press F5.
`pymodder_init` runs inside `gd.load_dll`, before your `lib.on` / `lib.expose` lines, so `api->emit` /
`api->call` work only after that (e.g. from a hook or from `api->later`).

```cpp
#include "pymodder.h"

static const PyModderAPI* api;
typedef bool (*PushButton)(void* self, int button);
static PushButton original_push;

static bool my_push(void* self, int button) {
    api->emit("jump", "hi");
    return original_push(self, button);       // run the game code
}

PYMODDER_EXPORT int pymodder_init(const PyModderAPI* a) {
    api = a;
    void* target = api->address("PlayerObject::pushButton");
    return target ? api->hook(target, (void*)my_push, (void**)&original_push) : 1;
}

PYMODDER_EXPORT int add(int a, int b) { return a + b; }
```

| `api->...` | What it does |
|---|---|
| `gd_base`, `cocos_base`, `mod_dir`, `mod_name` | base addresses, the DLL folder (UTF-8), the mod name |
| `log(text)`, `notify(text, seconds)` | write to `python.log` / show a message |
| `address(name)` | a GD function from the bindings (`"PlayLayer::resetLevel"`) or a `libcocos2d.dll` export; 0 = not found |
| `hook(target, detour, &original)` | hook a function; works together with Python hooks on the same function. Removed automatically |
| `hook_raw(target, detour, &original)` | the fastest hook (plain MinHook); fails if the function is already hooked |
| `unhook(target)` | remove your hook |
| `later(func, arg)` | run `func(arg)` on the game thread on the next frame (safe from your threads) |
| `emit(event, data)` | send an event to Python (`@lib.on(event)`) |
| `call(name, arg)` | call a Python function from `lib.expose`; returns text or `NULL` |

GD 2.2 for Windows uses the MSVC x64 calling convention: member functions take `this` as the first argument
(`bool PlayerObject::pushButton(PlayerButton)` is `bool (*)(void* self, int button)`).
Names and signatures: `pymodder/bindings/*.json` or the Geode bindings.

Build:

```
cl /LD /O2 mymod.cpp                                               (Visual Studio, x64 prompt)
g++ -shared -O2 -static mymod.cpp -o mymod.dll                     (MinGW-w64)
zig c++ -target x86_64-windows-gnu -shared -O2 mymod.cpp -o mymod.dll
```

A complete example: `pymodder/sdk/native_demo` (copy the folder into `pymodder/mods` to try it).

## Loader DLL

PyModder starts through a proxy DLL in the game folder. The installer picks a free name:
`XInput1_4.dll` (default), or `opengl32.dll` if `XInput1_4.dll` is already used by another mod loader
(Mega Hack, Geode...). `version.dll` can be chosen by hand. The real system DLL is still used, so nothing breaks.
Only one PyModder loader runs even if there are several copies.

## config.json

```json
{
  "reload_key": "F5",
  "menu_key": "F6",
  "console": false,
  "disabled_mods": [],
  "menu_button": true,
  "pause_button": true,
  "invert_scroll": false
}
```

- `console` opens a console window with the log.
- `menu_button` / `pause_button`: the PyModder buttons in the main menu and the pause menu.
- To switch PyModder off completely for a while, create an empty file `pymodder/disabled`.
