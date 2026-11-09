"""gd - a simple API for Geometry Dash mods (the PyModder loader).

A mod is a .py file in the folder Geometry Dash/pymodder/mods. Example:

    import gd

    @gd.on_death
    def died(player):
        gd.notify(f"Died at {gd.level.percent:.0f}%")

F5 - reload mods, F6 - mods menu. Docs: pymodder/docs/API.md
Text can be in any language (Russian too): non-latin text is drawn with Arial automatically.
"""
import os
import sys

from . import _core
from . import _ui
from . import _menu
from . import _mem as mem
from . import _native as _N
from . import _storage as _S
from . import _input as _I
from . import _media as _MD
from . import _cocos as cocos
from . import _plugins as _PL
from . import _audio as _AU
from . import _nodes as _ND
from . import _levels as _LV
from . import _objects as _OB
from . import _editor as _ED
from . import _net as _NET
from . import _images as _IMG
from . import _packs as _PK
from . import _music as _MU
from . import _subframe as _SF
from . import _gdui as _GU
from . import _speed as _SP
from . import _places as _PLC

__version__ = '0.7.0-beta'

Label = _core.Label
Player = _core.Player
Level = _core.Level
Draw = _core.Draw
Setting = _core.Setting
MODES = _core.MODES
Macro = _I.Macro
Sprite = _MD.Sprite
Texture = _MD.Texture

# UI elements (for gd.Popup.add)
Widget, Text, Button, Toggle, Slider, Input, Choice, KeyBind, Image = (
    _ui.Widget, _ui.Text, _ui.Button, _ui.Toggle, _ui.Slider, _ui.Input, _ui.Choice, _ui.KeyBind, _ui.Image)
ColorButton, Swatch = _ui.ColorButton, _ui.Swatch
Cell, ProgressBar, Stat, Icon, Tabs = _GU.Cell, _GU.ProgressBar, _GU.Stat, _GU.Icon, _GU.Tabs

# game nodes, levels, objects
Node = _ND.Node
LevelData = _LV.LevelData
GameObject = _OB.GameObject
PlayerIcon = _LV.PlayerIcon
Editor = _ED.Editor
Picture = _IMG.Picture
http = _NET.http
servers = _NET.servers


def _owner():
    return _core.caller_owner(3)


def _base_dir(owner):
    m = sys.modules.get(owner)
    return getattr(m, 'MOD_DIR', None) or os.path.join(_core.ROOT or '.', 'mods')


def _event(name, doc):
    def decorator(func):
        _core.add_handler(name, func, _core.caller_owner())
        return func
    decorator.__name__ = 'on_' + name
    decorator.__doc__ = doc
    return decorator


on_load = _event('load', 'The game started (also after the mod is reloaded). func()')
on_menu = _event('menu', 'The main menu opened. func()')
on_level_start = _event('level_start', 'A level opened. func(level)')
on_attempt = _event('attempt', 'A new attempt (restart after a death or R). func(level)')
on_death = _event('death', 'The player died. func(player)')
on_complete = _event('complete', 'The level is complete! func(level)')
on_exit = _event('exit', 'Left the level. func(level)')
on_jump = _event('jump', 'A click (jump). func(player). Return False and the click is ignored.')
on_release = _event('release', 'The button was released. func(player)')
on_frame = _event('frame', 'Every frame while a level is running. func(dt)')
on_tick = _event('tick', 'Every frame everywhere (menus too). func(dt)')
on_pause = _event('pause', 'The game was paused. func()')
on_resume = _event('resume', 'The game was resumed. func()')
on_unload = _event('unload', 'The mod is being unloaded (before a reload with F5). func()')


def on_key(key=None):
    """A key press.

    @gd.on_key("F1")         - only F1, func()
    @gd.on_key(my_setting)   - the key from a setting (kind="key"), the player can change it in the menu
    @gd.on_key               - any key, func(key)  (key is a string, e.g. "A" or "F1")
    Return False from a handler of a specific key so the game does not see it.
    """
    if callable(key) and not isinstance(key, Setting):
        _core.add_handler('key', key, _core.caller_owner())
        return key
    if not isinstance(key, Setting):
        key = _core.key_code(key)
    owner = _core.caller_owner()

    def decorator(func):
        _core.handlers.setdefault('key_one', []).append((func, owner, key))
        return func
    return decorator


# ---------------------------------------------------------------- messages / UI
def notify(text, seconds=2.5, color=(255, 255, 255)):
    """Show a message at the top of the screen."""
    _core.notify(text, seconds, color)


def log(*args):
    """Write to the log (pymodder/logs/python.log)."""
    print('[%s]' % _core.mod_name(_core.caller_owner()), *args)


class Popup(_ui.Popup):
    """A window on top of the game. See docs/API.md, section "Popups"."""

    def __init__(self, title='', width=320, height=None, on_close=None, **kw):
        owner = _core.caller_owner()
        kw.setdefault('owner', owner)
        kw.setdefault('base_dir', _base_dir(owner))
        super().__init__(title, width, height, on_close, **kw)

    def cell(self, title, subtitle='', icon=None, button=None, callback=None, on_button=None, **kw):
        """A GD list row (brown): icon, title, subtitle, a button on the right."""
        kw.setdefault('base_dir', self.base_dir)
        return self.add(Cell(title, subtitle, icon, button, callback, on_button, **kw))

    def progress(self, value=0.0, color=(0, 255, 0), width=200, text=None, **kw):
        """A GD progress bar, value 0..1 (change it later: bar.value = 0.5)."""
        return self.add(ProgressBar(value, color, width, text, **kw))

    def stat(self, icon, value, **kw):
        """An icon + a number like on the level page: p.stat("downloads", 12345)."""
        return self.add(Stat(icon, value, **kw))

    def icon(self, icon=1, kind='cube', color1=None, color2=None, glow=None, mine=False, size=1.0, **kw):
        """A GD player icon: p.icon(kind="ship", icon=5, color1=3, color2=12) or p.icon(mine=True)."""
        return self.add(Icon(icon, kind, color1, color2, glow, mine, size, **kw))

    def tabs(self, names, build, value=0):
        """Tabs: build(popup, index) adds the page (everything after the tabs) - called now and on switch."""
        t = self.add(Tabs(names, build, value))
        _ui.flex_call(self.owner, build, self, value)
        return t


def alert(text, title='Info', button='OK', on_close=None):
    """A message with an OK button."""
    return _ui.alert(text, title, button, on_close, _core.caller_owner())


def confirm(text, on_yes=None, title='Are you sure?', yes='Yes', no='No', on_no=None, yes_color='green',
            no_color='grey'):
    """A Yes / No popup. on_yes() if "Yes" was pressed, on_no() otherwise (also ESC / X)."""
    return _ui.confirm(text, on_yes, title, yes, no, on_no, _core.caller_owner(), yes_color=yes_color,
                       no_color=no_color)


def prompt(text, on_done=None, title='', default='', placeholder='', button='OK', numeric=False, on_cancel=None):
    """A popup with a text box: on_done(text) after OK / Enter (numeric=True -> a number)."""
    return _ui.prompt(text, on_done, title, default, placeholder, button, numeric, on_cancel,
                      _core.caller_owner())


def choose(options, on_pick=None, title='Choose', text='', cancel='Cancel'):
    """A popup with one button per option: on_pick(index, option)."""
    return _ui.choose(list(options), on_pick, title, text, _core.caller_owner(), cancel=cancel)


def pick_color(value=(255, 255, 255), on_done=None, title='Color', on_cancel=None):
    """A color picker popup (red / green / blue sliders + #hex): on_done((r, g, b)) after OK."""
    return _ui.pick_color(value, on_done, title, _core.caller_owner(), on_cancel)


def popups_open():
    """Is any PyModder popup open right now."""
    return bool(_ui.stack)


def setting(key, default, title=None, description='', min=None, max=None, step=None, options=None, kind=None):
    """A mod setting (shown in the mods menu behind the gear button). Saved automatically.

    speed = gd.setting("speed", 0.5, "Speed", min=0.1, max=2)
    if speed.value > 1: ...
    kind: "bool", "int", "float", "text", "choice" (needs options=[...]), "key" (a keyboard key),
          "color" (an (r, g, b) tuple; a default like (255, 0, 0) is a color automatically)
    """
    return _core.add_setting(_core.caller_owner(), key, default, title=title, description=description,
                             min=min, max=max, step=step, options=options, kind=kind)


def setting_header(title):
    """A section title in the mod settings (between gd.setting(...) lines): gd.setting_header("Visual")."""
    return _core.add_setting_item(_core.caller_owner(), 'header', title)


def setting_text(text, color=(220, 220, 220)):
    """A line of text (a hint) in the mod settings."""
    return _core.add_setting_item(_core.caller_owner(), 'label', text, color=tuple(color))


def setting_space():
    """Empty space in the mod settings."""
    return _core.add_setting_item(_core.caller_owner(), 'space', '')


def setting_button(title, callback=None, color='green', description=''):
    """A button in the mod settings: gd.setting_button("Reset stats", reset, color="red").
    Also a decorator: @gd.setting_button("Clear")."""
    owner = _core.caller_owner()
    if callback is None:
        def decorator(func):
            _core.add_setting_item(owner, 'button', title, callback=func, color=color, description=description)
            return func
        return decorator
    return _core.add_setting_item(owner, 'button', title, callback=callback, color=color, description=description)


def open_settings():
    """Open this mod's settings popup (also when the mod has its own gd.mod_menu)."""
    owner = _core.caller_owner()
    _core.later(lambda: _menu.open_settings(owner))


def menu_button(image='GJ_infoIcon_001.png', callback=None):
    """A button in the bottom row of the main menu. image - a GD frame, a .png next to the mod or short text.

    @gd.menu_button("my_icon.png")
    def clicked(): ...
    """
    owner = _core.caller_owner()

    def decorator(func):
        _menu.add_menu_button(image, func, owner, _base_dir(owner))
        return func
    return decorator(callback) if callback else decorator


def pause_button(image='GJ_infoIcon_001.png', callback=None):
    """A button at the bottom left of the pause menu (same as gd.menu_button)."""
    owner = _core.caller_owner()

    def decorator(func):
        _menu.add_pause_button(image, func, owner, _base_dir(owner))
        return func
    return decorator(callback) if callback else decorator


def _screen_button(owner, place, image, callback, position, offset, size, text, color):
    p = str(place).lower().replace('-', '_').replace(' ', '_')

    def decorator(func):
        simple = position is None and text is None
        if p in ('menu', 'main_menu') and simple:
            _menu.add_menu_button(image, func, owner, _base_dir(owner))
        elif p == 'pause' and simple:
            _menu.add_pause_button(image, func, owner, _base_dir(owner))
        elif p in ('level_cell', 'cell', 'levelcell'):
            _PLC.add_cell_button(image, func, owner, _base_dir(owner), size, text, color)
        else:
            _PLC.add(place, image, func, owner, _base_dir(owner), position, offset, size, text, color)
        return func
    return decorator(callback) if callback else decorator


def screen_button(place, image='GJ_infoIcon_001.png', callback=None, position=None, offset=(0, 0), size=None,
                  text=None, color='green'):
    """A button on a game screen. place: "level" (online level page), "my_level" (your level page),
    "levels" (level lists / search results), "main_levels", "search", "level_list", "creator", "garage",
    "editor", "editor_pause", "pause", "end" (level complete), "profile", "options", "menu",
    "level_cell" (every level in lists) or any layer class name ("SecretLayer2").
    position: "top-left", "top-right", "bottom-left", "bottom-right", "left", "right", "top", "bottom"
    (on popups - of the popup window). offset=(dx, dy) moves it. text="Go" - a GD text button instead of an image.
    The function gets (layer, *the layer's init arguments) - e.g. def f(layer, level) on the level page.

        @gd.screen_button("level", "my_icon.png", position="bottom-right")
        def clicked(layer, level):
            gd.notify(level.name)
    """
    return _screen_button(_core.caller_owner(), place, image, callback, position, offset, size, text, color)


def _shortcut(place, what):
    def button(image='GJ_infoIcon_001.png', callback=None, position=None, offset=(0, 0), size=None, text=None,
               color='green'):
        return _screen_button(_core.caller_owner(), place, image, callback, position, offset, size, text, color)
    button.__name__ = place + '_button'
    button.__doc__ = 'A button %s (gd.screen_button("%s", ...)). The function gets (layer, ...).' % (what, place)
    return button


level_button = _shortcut('level', 'on the page of an online level; def f(layer, level)')
my_level_button = _shortcut('my_level', 'on the page of your own (editor) level; def f(layer, level)')
levels_button = _shortcut('levels', 'on level lists and search results')
creator_button = _shortcut('creator', 'on the Create screen')
garage_button = _shortcut('garage', 'in the icon kit (garage)')
editor_button = _shortcut('editor', 'in the level editor; def f(editor_ui)')
editor_pause_button = _shortcut('editor_pause', 'in the editor pause menu')
end_button = _shortcut('end', 'on the level complete screen')
profile_button = _shortcut('profile', 'on a player profile')
options_button = _shortcut('options', 'in the GD options')
level_cell_button = _shortcut('level_cell', 'on every level in level lists; def f(cell, level)')


def open_mods_menu():
    """Open the PyModder mods menu (like F6)."""
    _core.later(_menu.open_menu)


def menu_key(key='F7', title='Menu key'):
    """Let the player open this mod's menu with a key anywhere in the game (the key can be changed
    in the mod settings). The menu is the gd.mod_menu function, or the mod settings.

        gd.menu_key("F7")            # or MENU_KEY = "F7" at the top of the mod
    """
    return _core.set_menu_key(_core.caller_owner(), key, title)


def mod_menu(func):
    """Decorator: this function opens the mod's own menu (gear button in the mods list and gd.menu_key).

        @gd.mod_menu
        def menu():
            p = gd.Popup("My mod"); p.toggle("Enabled", on.value, on.set); p.show()
    """
    _core.mod_menus[_core.caller_owner()] = func
    return func


def open_menu():
    """Open this mod's menu (the same as its menu key)."""
    owner = _core.caller_owner()
    _core.later(lambda: _menu.open_mod_menu(owner))


# ---------------------------------------------------------------- time / threads
def after(seconds, func=None):
    """Call func() after `seconds` seconds. Also works as a decorator: @gd.after(1)."""
    owner = _core.caller_owner()

    def decorator(f):
        _core.after(seconds, f, owner)
        return f
    return decorator(func) if func else decorator


def every(seconds, func=None):
    """Call func() every `seconds` seconds. Also works as a decorator: @gd.every(0.5)."""
    owner = _core.caller_owner()

    def decorator(f):
        _core.every(seconds, f, owner)
        return f
    return decorator(func) if func else decorator


def later(func):
    """Call func() on the game thread on the next frame (safe from a background thread)."""
    _core.later(func)


def background(func, *args):
    """Run func(*args) in a background thread (for slow work: internet, files).
    Do NOT touch the game from a background thread - hand the result back with gd.later(...)."""
    return _core.background(func, *args, owner=_core.caller_owner())


def fps():
    """The current FPS of the game."""
    return _core.fps()


# ---------------------------------------------------------------- storage
def save(key, value):
    """Save a value (it stays after the game restarts)."""
    _core.save(key, value, _core.caller_owner())


def load(key, default=None):
    """Load a saved value."""
    return _core.load(key, default, _core.caller_owner())


# ---------------------------------------------------------------- files on disk (.json / .macro)
class _Storage:
    """Mod files on disk: Geometry Dash/pymodder/saves/<mod>/. Only .json and .macro are allowed.

        gd.storage.save("stats.json", {"best": 87})
        data = gd.storage.load("stats.json", {})
        cfg = gd.storage.file("config.json", {"volume": 5})   # a dict that saves itself
    """
    ALLOWED = _S.ALLOWED

    def save(self, name, data):
        """Write data (dict/list/number/string or a gd.Macro) to a file. Returns the full path."""
        return _S.save(_core.caller_owner(), name, data)

    def load(self, name, default=None):
        """Read a file; if it is missing or broken, return default."""
        return _S.load(_core.caller_owner(), name, default)

    def file(self, name, default=None):
        """A dict linked to a .json file: changes are saved automatically."""
        return _S.JsonFile(_core.caller_owner(), name, default)

    def exists(self, name):
        return _S.exists(_core.caller_owner(), name)

    def delete(self, name):
        """Delete a file. True if it existed."""
        return _S.delete(_core.caller_owner(), name)

    def files(self, ext=None):
        """The mod's files: ["a.json", "runs/1.macro", ...]; ext=".macro" - only macros."""
        return _S.list_files(_core.caller_owner(), ext)

    def path(self, name=None):
        """The full path of a file (or of the mod folder if name is not given)."""
        owner = _core.caller_owner()
        return _S.path(owner, name) if name else _S.folder(owner)

    def open_folder(self):
        """Open the folder with the mod's files in Explorer."""
        os.startfile(_S.folder(_core.caller_owner()))


storage = _Storage()


# ---------------------------------------------------------------- pictures
def texture(path, smooth=True):
    """Load a picture (.png/.jpg) from the mod folder. smooth=False - no smoothing (pixel art)."""
    return _MD.texture(path, smooth, _core.caller_owner())


def add_frame(name, image, smooth=True):
    """Make a picture a GD frame called name (usable in Sprite, Popup.image, buttons).
    If GD already has a frame with that name it is replaced, like a texture pack (for new objects)."""
    return _MD.add_frame(name, image, smooth, _core.caller_owner())


def restore_frame(name):
    """Bring back the original GD frame after add_frame (done automatically when the mod unloads)."""
    _MD.restore_frame(name)


def load_frames(plist):
    """Load a sprite sheet .plist (+ the .png next to it) from the mod folder."""
    _MD.load_frames(plist, _core.caller_owner())


def icons():
    """Names of the built-in icons: ICON = "skull" in a mod, gd.menu_button("star"), gd.icon_path("gear")."""
    return _core.builtin_icons()


def icon_path(name):
    """Full path of a built-in icon .png (usable in gd.Sprite, Popup.image) or None."""
    return _core.builtin_icon(name)


def frame_exists(name):
    """Is there a frame with this name (e.g. "GJ_infoIcon_001.png")."""
    return _MD.frame_exists(name)


# ---------------------------------------------------------------- game control
def speed(value=None, audio=True):
    """Game speed: gd.speed(0.5) - 2x slower, gd.speed(1) - normal. Without an argument - get it.
    audio=True also slows down the music and sounds; audio=False - only the game.
    In a level this is GD's own time speed (like the testmode speed slider): the physics really slows
    down, and an attempt with a changed speed doesn't save progress (GD shows the testmode label)."""
    return _SP.speed(value, audio)


def audio_speed(value=None):
    """Music + sound speed (pitch) only: gd.audio_speed(0.8). Without an argument - get it."""
    return _AU.speed(value)


def _btn(button, player2):
    if isinstance(button, bool):          # old style: gd.press(True) = player 2
        return 'jump', button
    return button, player2


def press(button='jump', player2=False):
    """Hold a player button: "jump", "left", "right" (platformer). Works only in a level."""
    _core.press(*_btn(button, player2))


def release(button='jump', player2=False):
    """Release a player button."""
    _core.release(*_btn(button, player2))


def click(button='jump', player2=False):
    """Press and release right away."""
    b, p2 = _btn(button, player2)
    _core.press(b, p2)
    _core.release(b, p2)


def physics_tick():
    """GD's physics step counter in the running level: 480 per second of level time (2 per step,
    240 steps per second), 0 at the start of an attempt. Macros use it."""
    return _I.current_tick()


def hold(seconds, button='jump', player2=False):
    """Hold the button for `seconds` seconds."""
    b, p2 = _btn(button, player2)
    _I.hold(seconds, b, p2, _core.caller_owner())


def tap(x, y, hold=0.0):
    """A mouse click at screen point (x, y) - presses GD buttons, menus and popups. hold - how long to hold."""
    _I.tap(x, y, hold, _core.caller_owner())


def touch_down(x, y):
    """Press the mouse at a screen point (for dragging: then touch_move and touch_up)."""
    _I.touch_down(x, y)


def touch_move(x, y):
    _I.touch_move(x, y)


def touch_up(x, y):
    _I.touch_up(x, y)


def mouse_pos():
    """Where the mouse is: (x, y) in game screen coordinates."""
    return _I.mouse_pos()


def key_down(key):
    """Press a keyboard key for the game, e.g. gd.key_down("SPACE"). PyModder mods do not see it."""
    return _I.key_down(key)


def key_up(key):
    """Release a key."""
    return _I.key_up(key)


def key_tap(key, hold=0.0):
    """Press and release a key (hold - how long to hold it, in seconds)."""
    _I.key_tap(key, hold, _core.caller_owner())


def pause():
    """Pause the level."""
    _core.pause_game()


def on_pause_button(button):
    """A button of the pause menu was pressed: "quit", "restart", "restart_full", "practice", "normal",
    "resume", "edit". Return False to cancel it; later you can do it with gd.pause_action(button).

        @gd.on_pause_button("restart")
        def ask():
            gd.confirm("Restart the level?", lambda: gd.pause_action("restart"))
            return False
    """
    if button not in _core.PAUSE_ACTIONS:
        raise ValueError('pause button must be one of: ' + ', '.join(_core.PAUSE_ACTIONS))
    owner = _core.caller_owner()

    def decorator(func):
        _core.add_handler('pause_button', func, owner, arg=button)
        return func
    return decorator


def on_quit(func):
    """The exit button of the pause menu was pressed. Return False to stay in the level
    (e.g. to ask "Are you sure?"), then leave with gd.quit_level()."""
    _core.add_handler('pause_button', func, _core.caller_owner(), arg='quit')
    return func


def pause_action(button):
    """Press a pause menu button from code (gd.on_pause_button handlers are skipped). True if done."""
    return _core.pause_action(button)


def quit_level():
    """Leave the level right away (no confirmation, gd.on_quit handlers are skipped)."""
    return _core.quit_level()


def unlock_icons(on=True):
    """Unlock every icon, color, trail, death effect... in the garage while this mod is on
    (nothing is written to your save: turn it off and the locks come back)."""
    _core.unlock_icons(_core.caller_owner(), on)


def restart(full=False):
    """Start the attempt again (full=True - from the very start, even in practice mode)."""
    _core.restart(full)


def copy(text):
    """Copy text to the clipboard (Ctrl+V pastes it)."""
    return _ui.set_clipboard(text)


def paste():
    """The text in the clipboard."""
    return _ui.clipboard()


def game_var(key, value=None):
    """A GD option by number (GameManager::getGameVariable), e.g. gd.game_var("0024") - show FPS."""
    return _core.game_var(key, value)


def screen():
    """Screen size in game coordinates: (width, height)."""
    return cocos.win_size()


def mods():
    """The list of mods: [{'name', 'title', 'version', 'author', 'ok', 'enabled', 'error', ...}]."""
    return [dict(v) for v in _core.mods.values()]


def open(path):
    """Open a file, folder or link (https://...) in Windows."""
    owner = _core.caller_owner()
    if not str(path).startswith(('http://', 'https://')) and not os.path.isabs(path):
        path = os.path.join(_base_dir(owner), path)
    os.startfile(path)


def sound(path):
    """Play a .wav (path relative to the mod folder). Does not wait for the end."""
    import winsound
    owner = _core.caller_owner()
    if not os.path.isabs(path):
        path = os.path.join(_base_dir(owner), path)
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


# ---------------------------------------------------------------- advanced
def hook(name, restype=None, argtypes=None):
    """Advanced: hook any game function by its name from the Geode bindings.

    @gd.hook("PlayLayer::destroyPlayer")
    def my(original, this, player, obj):
        return original()     # run the game code
    """
    owner = _core.caller_owner()

    def decorator(func):
        _N.hook(name, func, owner, restype, argtypes)
        return func
    return decorator


def function(name):
    """Advanced: a game function, e.g. gd.function("PlayLayer::getCurrentPercent")(layer)."""
    return _N.function(name)


def address(name):
    """The address of a game function by name."""
    return _N.resolve(name)[0]


def load_dll(path):
    """Advanced: load your own native code (a C/C++ .dll next to the mod) and call it from Python.
    See docs/API.md, section "Native code (C++)" and pymodder/sdk/pymodder.h.

        lib = gd.load_dll("mymod.dll")
        lib.func("add", ctypes.c_int, ctypes.c_int, ctypes.c_int)(2, 3)
    """
    owner = _core.caller_owner()
    p = path if os.path.isabs(path) else os.path.join(_base_dir(owner), path)
    return _PL.load(owner, p)


# ---------------------------------------------------------------- nodes (layers, buttons) and node IDs
def on_layer(cls, entry=None):
    """A game screen / popup was built: @gd.on_layer("LevelInfoLayer") def f(layer, level): ...
    layer is a gd.Node; next arguments are those of the layer's init (a GJGameLevel becomes gd.LevelData).
    Works for any class with "Class::init" in the bindings (or pass entry="Class::function")."""
    owner = _core.caller_owner()

    def decorator(func):
        _ND.on_layer(cls, func, owner, entry)
        return func
    return decorator


def scene():
    """The running scene (gd.Node)."""
    return _ND.scene()


def current_layer():
    """The main layer on the screen (MenuLayer, LevelInfoLayer, PlayLayer...) as gd.Node."""
    return _ND.current_layer()


def find(id=None, **kw):
    """Find a node in the whole scene: gd.find(id="play-button"), gd.find(cls="CCMenu"), gd.find(text="Play")."""
    return _ND.find(id=id, **kw)


def find_all(id=None, **kw):
    return _ND.find_all(id=id, **kw)


def node(ptr):
    """gd.Node for a pointer (e.g. from a hook)."""
    return _ND.Node(ptr)


# ---------------------------------------------------------------- levels, icons
def level_data(ptr):
    """gd.LevelData for a GJGameLevel* pointer."""
    return _LV.LevelData(ptr)


def my_icons():
    """The player's icons and colors: {'cube': 12, 'ship': 3, ..., 'color1': 0, 'color2': 3, 'glow': False}."""
    return _LV.my_icons()


def set_icons(**icons):
    """gd.set_icons(cube=35, ship=10, color1=12, color2=5, glow=True). Kinds: cube ship ball ufo wave robot
    spider swing jetpack trail ship_fire death color1 color2 glow_color glow."""
    _LV.set_icons(**icons)


def color(index):
    """RGB of a GD player color index."""
    return _LV.color(index)


def decode_level(level_string):
    """GD level data ("H4sI...") -> plain object string."""
    return _LV.decode_level_string(level_string)


def parse_level(level_string):
    """Level string (encoded or plain) -> (header dict, [object dicts])."""
    return _LV.parse_objects(_LV.decode_level_string(level_string))


# ---------------------------------------------------------------- objects, hitboxes
def objects(object_id=None, where=None):
    """Objects of the open level / editor (gd.GameObject list). gd.objects(31) = start positions."""
    return _OB.objects(object_id, where=where)


def object_count():
    return _OB.object_count()


def start_positions():
    return _OB.start_positions()


def world_layer():
    """The node with the level objects: nodes added to it move with the level."""
    return _OB.world_layer()


def add_to_world(node_, z=100, x=None, y=None):
    """Put a node (gd.Node / pointer) into the level at level coordinates."""
    return _OB.add_to_world(node_, z, x, y)


def show_hitboxes(on=True):
    """Show hitboxes outside practice mode too."""
    _OB.show_hitboxes(on, _core.caller_owner())


# ---------------------------------------------------------------- editor
def editor():
    """The open level editor (gd.Editor) or None."""
    return _ED.editor()


def _flex(func):
    import inspect
    try:
        ps = inspect.signature(func).parameters.values()
        n = 99 if any(p.kind == p.VAR_POSITIONAL for p in ps) else \
            sum(1 for p in ps if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))
    except (TypeError, ValueError):
        n = 99

    def call(*a):
        return func(*a[:n])
    call.__name__ = getattr(func, '__name__', 'handler')
    return call


def _editor_event(name, doc):
    def decorator(func):
        _ED.need(name)
        _core.add_handler(name, _flex(func), _core.caller_owner())
        return func
    decorator.__name__ = 'on_' + name
    decorator.__doc__ = doc
    return decorator


on_editor_open = _editor_event('editor_open', 'The editor opened. func(editor, level)')
on_editor_exit = _editor_event('editor_exit', 'Leaving the editor. func(level)')
on_playtest = _editor_event('editor_playtest', 'Playtest started in the editor. func()')
on_stop_playtest = _editor_event('editor_stop_playtest', 'Playtest stopped. func()')
on_object_added = _editor_event('editor_object_added', 'An object was placed in the editor. func(obj)')
on_object_removed = _editor_event('editor_object_removed', 'An object is being deleted. func(obj)')
on_object_moved = _editor_event('editor_object_moved', 'An object was moved. func(obj, dx, dy)')
on_paste = _editor_event('editor_paste', 'Objects were pasted. func(objects)')


# ---------------------------------------------------------------- pictures, internet
def image(source, on_done=None, smooth=True):
    """A picture (PNG / JPG / animated GIF) from a file, bytes or an https:// link -> gd.Picture.
    Links load in the background: gd.image(url, on_done) -> on_done(picture, error).
    picture.sprite(width=60) makes a node (GIFs play)."""
    owner = _core.caller_owner()
    if isinstance(source, (bytes, bytearray)):
        pic = _IMG.load_bytes(bytes(source), smooth=smooth)
    elif str(source).startswith(('http://', 'https://')):
        return _IMG.load_url(str(source), on_done, owner=owner, smooth=smooth)
    else:
        p = str(source)
        if not os.path.isabs(p):
            p = os.path.join(_base_dir(owner), p)
        pic = _IMG.load_file(p, smooth)
    if on_done:
        _ui.flex_call(owner, on_done, pic, None)
    return pic


# ---------------------------------------------------------------- texture packs, music
class _Packs:
    """Texture packs: folders in pymodder/packs with files named like in Geometry Dash/Resources."""
    available = staticmethod(_PK.available)
    active = staticmethod(_PK.active)
    apply = staticmethod(_PK.apply)
    reload = staticmethod(_PK.reload_textures)
    search_paths = staticmethod(_PK.search_paths)

    @property
    def folder(self):
        return _PK.packs_dir()

    def open_folder(self):
        os.startfile(_PK.packs_dir())


packs = _Packs()


class _Music:
    """Music: gd.music.replace_song(id, "file.mp3"), gd.music.menu("menu.mp3"), gd.music.play("a.mp3")."""

    def replace_song(self, song_id, path):
        _MU.replace_song(song_id, path, _core.caller_owner())

    def replace_official(self, index, path):
        _MU.replace_official(index, path, _core.caller_owner())

    def menu(self, path):
        """Your main menu music (None = the original)."""
        _MU.set_menu_music(path, _core.caller_owner())

    def restore(self, song_id=None):
        _MU.restore(song_id, _core.caller_owner())

    def play(self, path, loop=True, fade=0.0):
        _MU.play(path, loop, fade, 0, _core.caller_owner())

    def stop(self):
        _MU.stop()

    def effect(self, path):
        _MU.effect(path, _core.caller_owner())

    @property
    def playing(self):
        return _MU.playing()

    @property
    def position(self):
        return _MU.position()

    @position.setter
    def position(self, seconds):
        _MU.position(seconds)

    @property
    def length(self):
        return _MU.length()

    def song_path(self, song_id):
        return _MU.song_path(song_id)


music = _Music()


def pick_file(on_done, kind='any', title='Choose a file', save=False):
    """Windows file dialog: on_done(path or None). kind: 'audio', 'image', 'any'."""
    _MU.pick_file(on_done, kind, title, None, save, _core.caller_owner())


# ---------------------------------------------------------------- GD popups, input, fps
def gd_alert(text, title='Info', button='OK', button2=None, on_close=None, width=360):
    """A real GD alert (FLAlertLayer). Colors: <cg>green</c> <cr>red</c> <cy>yellow</c> <cl>blue</c>.
    on_close(second_button) - True if button2 was pressed."""
    return _GU.gd_alert(text, title, button, button2, on_close, width, _core.caller_owner())


def list_popup(title, items, on_pick=None, width=380, height=260, button=None):
    """A GD-style list: items = strings or dicts {title, subtitle, icon, button}. on_pick(item, index)."""
    owner = _core.caller_owner()
    return _GU.list_popup(title, items, on_pick, width, height, owner, _base_dir(owner), button)


def click_between_frames(on=True):
    """Experimental: presses are applied at the moment they happened, not at the next frame."""
    _SF.enable(on, _core.caller_owner())


def fps_cap(value=None):
    """Set the FPS limit (e.g. 240). Returns the current limit."""
    import ctypes
    app = _N.cocos_fn('?sharedApplication@CCApplication@cocos2d@@SAPEAV12@XZ', ctypes.c_void_p)()
    if value:
        _N.cocos_fn('?setAnimationInterval@CCApplication@cocos2d@@UEAAXN@Z', None, ctypes.c_void_p,
                    ctypes.c_double)(app, 1.0 / float(value))
        return float(value)
    d = _N.cocos_fn('?sharedDirector@CCDirector@cocos2d@@SAPEAV12@XZ', ctypes.c_void_p)()
    iv = _N.cocos_fn('?getAnimationInterval@CCDirector@cocos2d@@QEAANXZ', ctypes.c_double, ctypes.c_void_p)(d)
    return 1.0 / iv if iv else 0.0



_SCREENS = {'menu': ('MenuLayer::scene', (False,)), 'creator': ('CreatorLayer::scene', ()),
            'search': ('LevelSearchLayer::scene', (0,)), 'icon_kit': ('GJGarageLayer::scene', ()),
            'main_levels': ('LevelSelectLayer::scene', (0,))}


def open_screen(screen='menu', query=None, fade=0.5):
    """Go to a GD screen: 'menu', 'creator', 'search', 'icon_kit', 'main_levels',
    or 'levels' + a search text / level ID: gd.open_screen('levels', '128') shows the search results."""
    import ctypes

    def go():
        if isinstance(screen, int):
            sc = screen
        elif screen == 'levels':
            s = mem.StdString(str(query or ''))
            try:
                obj = _N.function('GJSearchObject::create(SearchType, std::string)')(0, s.addr)
            finally:
                s.free()
            sc = _N.function('LevelBrowserLayer::scene')(obj)
        else:
            if screen not in _SCREENS:
                raise KeyError('unknown screen %r (%s, levels)' % (screen, ', '.join(_SCREENS)))
            name, args = _SCREENS[screen]
            sc = _N.function(name)(*args)
        if not sc:
            raise RuntimeError('could not create the screen %r' % (screen,))
        if fade:
            sc = _N.cocos_fn('?create@CCTransitionFade@cocos2d@@SAPEAV12@MPEAVCCScene@2@@Z', ctypes.c_void_p,
                             ctypes.c_float, ctypes.c_void_p)(float(fade), sc)
        d = _N.cocos_fn('?sharedDirector@CCDirector@cocos2d@@SAPEAV12@XZ', ctypes.c_void_p)()
        _N.cocos_fn('?replaceScene@CCDirector@cocos2d@@QEAA_NPEAVCCScene@2@@Z', ctypes.c_bool, ctypes.c_void_p,
                    ctypes.c_void_p)(d, sc)
    _core.later(go)


def __getattr__(name):
    s = _core.state
    if name == 'level':
        return s.level if s.started else None
    if name == 'player':
        return s.player if s.started else None
    if name == 'player2':
        return s.player2 if s.started else None
    if name == 'in_level':
        return bool(s.started)
    if name == 'paused':
        return bool(s.started and s.paused)
    if name == 'layer':
        return s.layer
    if name == 'gd_version':
        return _N.version
    if name == 'pause_layer':
        return _core.pause_layer()
    if name == 'in_editor':
        return _ED.editor_ptr() is not None
    if name == 'attempt_time':
        return _core.state.attempt_time if s.started else 0.0
    raise AttributeError(name)
