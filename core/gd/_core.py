"""PyModder core: game state, events, hooks, mods, settings, timers, notifications, drawing."""
import ast
import collections
import ctypes
import importlib.util
import json
import os
import struct
import sys
import threading
import time
import traceback
from ctypes import c_void_p, c_bool, c_int, c_float, c_double

from . import _mem as M
from . import _native as N
from . import _cocos as C
from . import _ui as U

ROOT = None
GD_DIR = None
CFG = {'reload_key': 'F5', 'menu_key': 'F6', 'console': False, 'disabled_mods': [],
       'menu_button': True, 'pause_button': True, 'invert_scroll': False}
handlers = {}          # event -> [(func, owner, arg)]
mods = {}              # owner -> info dict
settings = {}          # owner -> [Setting]
_timers = []           # [when, interval|None, func, owner]
_pending = []          # funcs waiting for a stable scene
_later = collections.deque()   # funcs for the next frame (thread safe)
_persistent = []       # objects with .node/.z re-attached to every new scene (labels, screen drawings)
U.is_overlay = lambda node: any(o.node == node for o in _persistent)
_world_draws = []
_notes = []            # [label, until]
_scene = [None, 0]     # last scene, how many ticks it stayed the same
_fps = [60.0]
Z_NOTE = 30000

KEYS = {'SPACE': 0x20, 'ENTER': 0x0D, 'RETURN': 0x0D, 'ESC': 0x1B, 'ESCAPE': 0x1B, 'TAB': 0x09,
        'BACKSPACE': 0x08, 'SHIFT': 0x10, 'CTRL': 0x11, 'CONTROL': 0x11, 'ALT': 0x12,
        'LEFT': 0x25, 'UP': 0x26, 'RIGHT': 0x27, 'DOWN': 0x28, 'DELETE': 0x2E, 'INSERT': 0x2D,
        'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22}
KEYS.update({chr(c): c for c in range(0x41, 0x5B)})
KEYS.update({str(d): 0x30 + d for d in range(10)})
KEYS.update({'F%d' % i: 0x6F + i for i in range(1, 13)})
KEYS.update({'NUM%d' % d: 0x60 + d for d in range(10)})
KEY_NAMES = {v: k for k, v in reversed(list(KEYS.items()))}


def key_code(name):
    if isinstance(name, int):
        return name
    if hasattr(name, 'value'):          # a Setting
        name = name.value
    k = str(name).upper().replace(' ', '')
    if k not in KEYS:
        raise ValueError('unknown key: %r (examples: "F1", "A", "SPACE")' % name)
    return KEYS[k]


def key_name(code):
    return KEY_NAMES.get(code, str(code))


# ---------------------------------------------------------------- owners (which mod is calling)
def caller_owner(depth=2):
    f = sys._getframe(depth)
    while f:
        n = f.f_globals.get('__name__', '')
        if n.startswith('gdmod_'):
            return n
        f = f.f_back
    return 'pymodder'


def mod_name(owner):
    return owner[6:] if owner.startswith('gdmod_') else owner


_err_counts = {}
_fails = {}


def report(owner, where):
    """Print a mod error (only the first few times — per-frame errors would flood the log)."""
    key = (owner, where)
    n = _err_counts[key] = _err_counts.get(key, 0) + 1
    if n <= 3:
        print('[PyModder] error in mod %s (%s):' % (mod_name(owner), where))
        traceback.print_exc()
        info = mods.get(owner)
        if info is not None:
            info['runtime_error'] = '%s\n%s' % (where, traceback.format_exc(limit=-6))
    elif n == 4:
        print('[PyModder] error in mod %s (%s) repeats - not logging it any more' % (mod_name(owner), where))
    if n == 1:
        try:
            notify('Error in mod %s - see the mods menu (%s)' % (mod_name(owner), CFG.get('menu_key') or 'F6'), 4,
                   (255, 90, 90))
        except Exception:
            pass


U.hooks['report'] = report


# ---------------------------------------------------------------- events
def add_handler(event, func, owner=None, arg=None):
    handlers.setdefault(event, []).append((func, owner or func.__module__, arg))
    return func


def _failed(event, entry):
    """A handler raised: after many errors in a row it is switched off."""
    func, owner, _ = entry
    report(owner, event)
    n = _fails[func] = _fails.get(func, 0) + 1
    if n >= 100 and entry in handlers.get(event, ()):
        handlers[event].remove(entry)
        print('[PyModder] %s: handler %s switched off after 100 errors' % (mod_name(owner), func.__name__))


def emit(event, *args, arg=None):
    result = None
    for entry in list(handlers.get(event, ())):
        func, owner, want = entry
        if want is not None and want != arg:
            continue
        try:
            r = func(*args)
            if r is not None:
                result = r
        except Exception:
            _failed(event, entry)
    return result


def emit_key(code):
    """Handlers of a specific key (key may be a Setting -> checked every time)."""
    result = None
    for func, owner, want in list(handlers.get('key_one', ())):
        try:
            if key_code(want) != code:
                continue
            r = func()
            if r is not None:
                result = r
        except Exception:
            report(owner, 'key')
    return result


# ---------------------------------------------------------------- game objects
MODES = ('cube', 'ship', 'ball', 'ufo', 'wave', 'robot', 'spider', 'swing')
_MODE_FLAGS = {'ship': 0x9C1, 'ufo': 0x9C2, 'ball': 0x9C3, 'wave': 0x9C4, 'robot': 0x9C5, 'spider': 0x9C6,
               'swing': 0x9CC}
_MODE_TOGGLE = {'ship': 'toggleFlyMode', 'ufo': 'toggleBirdMode', 'ball': 'toggleRollMode',
                'wave': 'toggleDartMode', 'robot': 'toggleRobotMode', 'spider': 'toggleSpiderMode',
                'swing': 'toggleSwingMode'}
OFF_YVEL, OFF_UPSIDE, OFF_DEAD, OFF_GROUND = 0x9A8, 0x9C7, 0x9C8, 0x9C9


def _call(name, *args):
    return N.function(name)(*args)


class Player:
    """A player (cube/ship/...)."""

    def __init__(self, ptr, second=False):
        self.ptr, self.is_player2 = ptr, second
        self._dead = False
        self._color = self._color2 = None

    @property
    def x(self):
        return C.position(self.ptr)[0]

    @property
    def y(self):
        return C.position(self.ptr)[1]

    @property
    def rotation(self):
        return C.rotation(self.ptr)

    @property
    def dead(self):
        return self._dead or bool(M.u8(self.ptr + OFF_DEAD, 0))

    @dead.setter
    def dead(self, v):
        self._dead = bool(v)

    @property
    def y_velocity(self):
        return M.f64(self.ptr + OFF_YVEL, 0.0)

    @y_velocity.setter
    def y_velocity(self, v):
        _call('PlayerObject::setYVelocity', self.ptr, float(v), 0)

    @property
    def on_ground(self):
        return bool(M.u8(self.ptr + OFF_GROUND, 0))

    @property
    def gravity_flipped(self):
        return bool(M.u8(self.ptr + OFF_UPSIDE, 0))

    def flip_gravity(self, flipped=None):
        """Flip gravity (or set it: True = upside down)."""
        if flipped is None:
            flipped = not self.gravity_flipped
        _call('PlayerObject::flipGravity', self.ptr, bool(flipped), True)

    @property
    def mode(self):
        """'cube', 'ship', 'ball', 'ufo', 'wave', 'robot', 'spider' or 'swing'."""
        for name, off in _MODE_FLAGS.items():
            if M.u8(self.ptr + off, 0):
                return name
        return 'cube'

    @mode.setter
    def mode(self, name):
        name = str(name).lower()
        if name not in MODES:
            raise ValueError('mode must be one of: ' + ', '.join(MODES))
        cur = self.mode
        if cur == name:
            return
        if cur != 'cube':
            _call('PlayerObject::' + _MODE_TOGGLE[cur], self.ptr, False, True)
        if name != 'cube':
            _call('PlayerObject::' + _MODE_TOGGLE[name], self.ptr, True, True)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, rgb):
        self._color = tuple(rgb)[:3]
        # PlayerObject::setColor overrides CCRGBAProtocol::setColor: "this" is the protocol part (+0x140)
        _call('PlayerObject::setColor', self.ptr + 0x140, C.color3(rgb))

    @property
    def color2(self):
        return self._color2

    @color2.setter
    def color2(self, rgb):
        self._color2 = tuple(rgb)[:3]
        _call('PlayerObject::setSecondColor', self.ptr, C.color3(rgb))

    @property
    def visible(self):
        return bool(C.fn('is_visible')(self.ptr))

    @visible.setter
    def visible(self, v):
        _call('PlayerObject::setVisible', self.ptr, bool(v))

    @property
    def scale(self):
        return C.fn('get_scale')(self.ptr)

    @scale.setter
    def scale(self, v):
        _call('PlayerObject::setScale', self.ptr, float(v))

    def __repr__(self):
        return '<Player %s %s x=%.1f y=%.1f>' % ('2' if self.is_player2 else '1', self.mode, self.x, self.y)


_level_name_off = [None]
OFF_PRACTICE, OFF_PLATFORMER = 0x32E0, 0x317E


class Level:
    """The current level."""

    def __init__(self, layer, ptr):
        self.layer, self.ptr = layer, ptr
        self._attempts, self.deaths, self.best_run = 1, 0, 0.0
        self.completed = False
        self._name = self._creator = None

    def _find_name(self):
        if _level_name_off[0] is None:
            for off in range(0x100, 0x800, 8):
                if all(M.std_string(self.ptr + off + 32 * i) is not None for i in range(5)):
                    _level_name_off[0] = off
                    print('[PyModder] GJGameLevel::m_levelName = +0x%x' % off)
                    break
            else:
                _level_name_off[0] = -1
        return _level_name_off[0]

    @property
    def data(self):
        """Everything about the level (gd.LevelData: stars, difficulty, likes, song...) or None."""
        from . import _levels as L
        d = L.LevelData(self.ptr)
        return d if d.valid else None

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        d = self.data
        if d is None:
            raise AttributeError(name)
        return getattr(d, name)

    @property
    def name(self):
        if self._name is None:
            d = self.data
            if d is not None:
                self._name = d.name or '?'
            else:
                off = self._find_name()
                self._name = (M.std_string(self.ptr + off) if off > 0 else None) or '?'
        return self._name

    @property
    def creator(self):
        if self._creator is None:
            d = self.data
            if d is not None:
                self._creator = d.creator or ''
            else:
                off = self._find_name()
                self._creator = (M.std_string(self.ptr + off + 96) if off > 0 else None) or ''
        return self._creator

    @property
    def id(self):
        d = self.data
        if d is not None:
            return d.id or 0
        off = self._find_name()
        if off <= 0:
            return 0
        r, s, v = M.i32(self.ptr + off - 16), M.i32(self.ptr + off - 12), M.i32(self.ptr + off - 8)
        return v if r is not None and r - s == v else 0

    @property
    def attempts(self):
        v = M.i32(self.layer + OFF_ATTEMPTS)
        return v if v is not None and 0 < v < 10 ** 8 else self._attempts

    @property
    def percent(self):
        try:
            return float(state.percent_fn(self.layer))
        except Exception:
            return 0.0

    @property
    def practice(self):
        return bool(M.u8(self.layer + OFF_PRACTICE, 0))

    @practice.setter
    def practice(self, on):
        if bool(on) != self.practice:
            _call('PlayLayer::togglePracticeMode', self.layer, bool(on))

    @property
    def platformer(self):
        return bool(M.u8(self.layer + OFF_PLATFORMER, 0))

    def __repr__(self):
        return '<Level %r id=%s>' % (self.name, self.id)


class State:
    layer = None
    level = None
    player = None
    player2 = None
    started = False
    paused = False
    percent_fn = None
    handle_button = None
    in_press = False
    attempt_time = 0.0     # seconds of the current attempt (level time, follows gd.speed)
    frame = 0              # GJBaseGameLayer::update calls in the current attempt
    key_hook = None        # native hook of CCKeyboardDispatcher::dispatchKeyboardMSG (for simulated keys)
    pause_layer = None     # the open PauseLayer*
    block_input = False    # the player's clicks are ignored (a macro plays)


# extension points for _input / _media / _storage
attempt_listeners = []     # f() when an attempt starts
pre_update = []            # f(dt) before GJBaseGameLayer::update
button_listeners = []      # f(down, button, player2) for real player input
cleanup_hooks = []         # f(owner) when a mod is unloaded
leave_hooks = []           # f() when the level is closed


_attempt_open = [False]


def _attempt_started():
    # a second reset without any frame in between is the same attempt (e.g. init + resetLevel)
    fresh = state.frame > 0 or not _attempt_open[0]
    state.attempt_time, state.frame = 0.0, 0
    _attempt_open[0] = True
    if not fresh:
        return
    for f in list(attempt_listeners):
        try:
            f()
        except Exception:
            traceback.print_exc()


state = State()
OFF_PLAYER1 = 0xDB8   # GJBaseGameLayer::m_player1 in 2.2091 (checked with RTTI at runtime)
OFF_ATTEMPTS = 0x3164  # PlayLayer::m_attempts in 2.2091


def _find_players(layer):
    p1 = M.ptr(layer + OFF_PLAYER1)
    if M.class_name(p1) == 'PlayerObject':
        p2 = M.ptr(layer + OFF_PLAYER1 + 8)
        return p1, (p2 if M.class_name(p2) == 'PlayerObject' else 0)
    off = M.find_pointer_to(layer, 'PlayerObject', 0x200, 0x2000)
    if off is None:
        return 0, 0
    print('[PyModder] m_player1 found by RTTI: +0x%x' % off)
    p2 = M.ptr(layer + off + 8)
    return M.ptr(layer + off), (p2 if M.class_name(p2) == 'PlayerObject' else 0)


def _player_of(ptr):
    for p in (state.player, state.player2):
        if p and p.ptr == ptr:
            return p
    return None


# ---------------------------------------------------------------- hooks: level
def _h_play_init(orig, this, level, *rest):
    state.layer, state.started, state.paused = this, False, False
    ok = orig()
    if ok:
        p1, p2 = _find_players(this)
        state.player = Player(p1) if p1 else None
        state.player2 = Player(p2, True) if p2 else None
        state.level = Level(this, level)
        state.started = True
        _attempt_started()
        print('[PyModder] level:', state.level, state.player)
        emit('level_start', state.level)
    else:
        state.layer = None
    return ok


def _h_reset(orig, this):
    orig()
    if this == state.layer and state.started:
        lv = state.level
        lv._attempts += 1
        for p in (state.player, state.player2):
            if p:
                p._dead = False
        _attempt_started()
        emit('attempt', lv)


def _h_destroyed(orig, this, no_effects):
    p = _player_of(this) if state.started else None
    was = p._dead if p else True
    orig()
    if p and not was:
        p._dead = True
        state.level.deaths += 1
        state.level.best_run = max(state.level.best_run, state.level.percent)
        emit('death', p)


def _h_complete(orig, this):
    orig()
    if this == state.layer and state.level:
        state.level.completed = True
        emit('complete', state.level)


def _leave(this):
    if this == state.layer and state.layer:
        lv = state.level
        state.started = state.paused = False
        state.pause_layer = None
        for d in list(_world_draws):
            d._drop()
        _attempt_open[0] = False
        for f in list(leave_hooks):
            try:
                f()
            except Exception:
                traceback.print_exc()
        try:
            if lv:
                emit('exit', lv)
        finally:
            state.layer = state.level = state.player = state.player2 = None


def _h_quit(orig, this):
    _leave(this)
    orig()


_pausing = [False]


def _h_pause_game(orig, this, *args):
    _pausing[0] = True          # PlayLayer::pauseGame calls this->onExit() (stops its actions) - not a leave
    try:
        return orig()
    finally:
        _pausing[0] = False


def _h_onexit(orig, this):
    if this == state.layer and not _pausing[0]:
        scene = C.running_scene()
        still_here = scene and C.fn('parent')(this) == scene and not C.next_scene()
        if not still_here:      # the scene is really changing (quit, editor, another level)
            _leave(this)
    orig()


def _h_update(orig, this, dt):
    mine = this == state.layer and state.started
    if mine:
        for f in list(pre_update):
            try:
                f(dt)
            except Exception:
                traceback.print_exc()
    orig()
    if mine:
        state.attempt_time += dt
        state.frame += 1
        emit('frame', dt)


def _h_button(orig, this, down, button, is_p1):
    if this == state.layer and state.started and not state.in_press:
        if state.block_input:
            return None
        p = state.player if is_p1 or not state.player2 else state.player2
        if button == 1 and p:
            if emit('jump' if down else 'release', p) is False:
                return None   # a mod said "no" -> the click is ignored
        for f in list(button_listeners):
            try:
                f(bool(down), int(button), not is_p1)
            except Exception:
                traceback.print_exc()
    orig()


def _h_pause(orig, this):
    orig()
    state.paused = True
    state.pause_layer = this
    try:
        from . import _menu
        _menu.on_pause_layer(this)
    except Exception:
        traceback.print_exc()
    emit('pause')


def _h_resume(orig, this, *args):
    orig()
    if state.paused:
        state.paused = False
        state.pause_layer = None
        emit('resume')


# ---------------------------------------------------------------- hooks: menu, frame, input
_first_menu = [True]


def _h_menu(orig, this):
    ok = orig()
    if ok:
        try:
            from . import _menu
            _menu.on_menu_layer(this)
        except Exception:
            traceback.print_exc()

        def later_():
            _first_menu[0] = False
            emit('menu')
        when_scene_ready(later_)
    return ok


_main_thread = [None]
_loaded_event = [False]


def _h_tick(orig, this, dt):
    orig()
    if _main_thread[0] is None:
        _main_thread[0] = M.k32.GetCurrentThreadId()
    try:
        _tick(dt)
    except Exception:
        traceback.print_exc()


def _tick(dt):
    if dt > 0:
        _fps[0] = _fps[0] * 0.92 + (1.0 / dt) * 0.08
    if not _loaded_event[0]:
        _loaded_event[0] = True
        load_mods()             # on the game thread, before the first menu appears
        emit('load')
    for _ in range(len(_later)):
        f = _later.popleft()
        try:
            f()
        except Exception:
            traceback.print_exc()
    now = time.perf_counter()
    for t in list(_timers):
        if now >= t[0]:
            if t[1] is None:
                _timers.remove(t)
            else:
                t[0] = now + t[1]
            try:
                t[2]()
            except Exception:
                report(t[3], 'timer')
    scene = C.running_scene()
    if scene != _scene[0]:
        _scene[0], _scene[1] = scene, 0
    else:
        _scene[1] += 1
    stable = scene and _scene[1] >= 1 and not C.next_scene() \
        and not (M.class_name(scene) or '').startswith('cocos2d::CCTransition')
    if stable:
        while _pending:
            f = _pending.pop(0)
            try:
                f()
            except Exception:
                traceback.print_exc()
        for obj in _persistent:
            node = obj.node
            if node and C.fn('parent')(node) != scene:
                if C.fn('parent')(node):
                    C.fn('remove')(node, False)
                C.fn('add_child')(scene, node, obj.z)
        if _scene[1] == 1:
            try:
                from . import _menu
                _menu.on_stable_scene(scene)
            except Exception:
                traceback.print_exc()
    _notes[:] = [n for n in _notes if n[1] > now]
    U.tick(dt)
    emit('tick', dt)


_codes = {}


def _cfg_code(name):
    v = CFG.get(name)
    if not v:
        return None
    if v not in _codes:
        try:
            _codes[v] = key_code(v)
        except ValueError:
            _codes[v] = None
    return _codes[v]


def open_mods_menu():
    from . import _menu
    _menu.toggle_menu()


def _h_key(orig, this, key, down, repeat, timestamp):
    try:
        if U.busy():
            if down:
                U.key(key, down, repeat, key_name(key))
                return True
            return orig()          # key-ups still reach the game
        if down and key == 0x1B and U.esc_recent():
            return True            # this ESC already closed a popup
        if down and not repeat:
            if key == _cfg_code('menu_key'):
                later(open_mods_menu)
                return True
            if key == _cfg_code('reload_key'):
                when_scene_ready(reload_mods)
                return True
            owner = _menu_key_owner(key)
            if owner:
                later(lambda: _toggle_mod_menu(owner))
                return True
            emit('key', key_name(key))
            if emit_key(key) is False:
                return True
    except Exception:
        traceback.print_exc()
    return orig()


def _h_keypad(orig, this, msg):
    if msg == 1:                    # kTypeBackClicked (ESC)
        if U.esc_recent():
            return True
        if U.busy():
            U.back()
            return True
    return orig()


def _touch_hook(kind):
    def handler(orig, this, touches, event):
        if not (U.stack or U.screen_buttons or U._route):
            return orig()
        t = C.fn('set_any')(touches) if touches else None
        if not t:
            return orig()
        buf = ctypes.create_string_buffer(8)
        C.fn('touch_loc')(t, buf)
        x, y = struct.unpack('<ff', buf.raw)
        if U.touch(kind, t, x, y):
            return None
        return orig()
    return handler


def _h_insert(orig, this, text, length, code):
    if U.stack:
        try:
            raw = ctypes.string_at(text, length) if text and length > 0 else (ctypes.string_at(text) if text else b'')
            U.insert_text(raw.decode('utf-8', 'replace'))
        except Exception:
            traceback.print_exc()
        return None
    return orig()


def _h_delete(orig, this):
    if U.stack:
        U.delete_backward()
        return None
    return orig()


def _h_scroll(orig, this, a, b):
    if U.stack:
        U.scroll(a, b)
        return True
    return orig()


# ---------------------------------------------------------------- pause menu buttons (gd.on_pause_button)
PAUSE_ACTIONS = {'quit': 'PauseLayer::tryQuit', 'restart': 'PauseLayer::onRestart',
                 'restart_full': 'PauseLayer::onRestartFull', 'practice': 'PauseLayer::onPracticeMode',
                 'normal': 'PauseLayer::onNormalMode', 'resume': 'PauseLayer::onResume', 'edit': 'PauseLayer::onEdit'}
_pause_hooks = {}      # action -> Hook


def _pause_hook(action):
    def handler(orig, this, sender):
        state.pause_layer = this
        if emit('pause_button', arg=action) is False:
            return None            # a mod cancelled it (e.g. to show its own "Are you sure?" popup)
        return orig()
    return handler


def pause_layer():
    """The open PauseLayer* (None if the pause menu is closed)."""
    pl = state.pause_layer
    if pl and state.started and state.paused:
        scene = C.running_scene()
        if scene and pl in C.children(scene):
            return pl
    return None


def pause_action(action):
    """Press a pause menu button from code, skipping gd.on_pause_button handlers."""
    if action not in PAUSE_ACTIONS:
        raise ValueError('pause button must be one of: ' + ', '.join(PAUSE_ACTIONS))
    pl = pause_layer()
    h = _pause_hooks.get(action)
    if not pl or not h:
        return False
    h.original(pl, None)
    return True


def quit_level():
    """Leave the level now (as the pause menu exit button, without any confirmation)."""
    if not state.started:
        return False

    def go():
        pl = pause_layer()
        if pl:
            N.function('PauseLayer::onQuit')(pl, None)
    if pause_layer():
        go()
    else:
        pause_game()
        later(lambda: later(go))   # the pause layer appears on the next frame
    return True


# ---------------------------------------------------------------- unlock all icons (gd.unlock_icons)
icon_unlockers = set()     # owners that want every icon / color unlocked
_ICON_UNLOCK_TYPES = set(range(1, 12)) | {13, 14, 15}      # UnlockType without GJItem (12)


def _h_icon_unlocked(orig, this, icon_id, icon_type):
    return True if icon_unlockers else orig()


def _h_color_unlocked(orig, this, color_id, unlock_type):
    return True if icon_unlockers else orig()


def _h_item_unlocked(orig, this, unlock_type, item_id):
    if icon_unlockers and unlock_type in _ICON_UNLOCK_TYPES:
        return True
    return orig()


def unlock_icons(owner, on=True):
    if on:
        icon_unlockers.add(owner)
    else:
        icon_unlockers.discard(owner)


cleanup_hooks.append(lambda owner: icon_unlockers.discard(owner))


# ---------------------------------------------------------------- per-mod menu + hotkey
mod_menus = {}             # owner -> func that opens the mod's own menu (gd.mod_menu)
menu_keys = {}             # owner -> Setting(kind='key') - opens the mod's menu in game


def set_menu_key(owner, key, title='Menu key'):
    key_code(key)                            # validate
    s = add_setting(owner, '_menu_key', str(key).upper(), title=title, kind='key',
                    description="Opens this mod's menu anywhere in the game")
    menu_keys[owner] = s
    return s


def _menu_key_owner(code):
    for owner, s in list(menu_keys.items()):
        info = mods.get(owner)
        if not info or not info['ok']:
            continue
        try:
            if key_code(s.value) == code:
                return owner
        except ValueError:
            pass
    return None


def _toggle_mod_menu(owner):
    from . import _menu
    _menu.toggle_mod_menu(owner)


def _popup_menu_key(code, popup):
    """A key pressed while a popup is open: its mod's menu key closes it."""
    owner = getattr(popup, 'menu_of', None) or popup.owner
    s = menu_keys.get(owner)
    try:
        if s and key_code(s.value) == code:
            popup.close()
            return True
    except ValueError:
        pass
    return False


U.hooks['mod_menu_key'] = _popup_menu_key


def _forget_menu(owner):
    mod_menus.pop(owner, None)
    menu_keys.pop(owner, None)


cleanup_hooks.append(_forget_menu)


def install_hooks():
    v, b, i, f = c_void_p, c_bool, c_int, c_float
    H = N.hook
    H('PlayLayer::init', _h_play_init)
    H('PlayLayer::resetLevel', _h_reset)
    H('PlayLayer::levelComplete', _h_complete)
    H('PlayLayer::onQuit', _h_quit)
    H('PlayLayer::onExit', _h_onexit)
    H('PlayerObject::playerDestroyed', _h_destroyed)
    H('GJBaseGameLayer::update', _h_update)
    H('GJBaseGameLayer::handleButton', _h_button)
    H('MenuLayer::init', _h_menu)
    optional = [
        ('PlayLayer::pauseGame', _h_pause_game, None, None),
        ('PauseLayer::customSetup', _h_pause, None, None),
        ('PlayLayer::resume', _h_resume, None, None),
        ('PlayLayer::resumeAndRestart', _h_resume, None, None),
    ]
    cc = 'cocos2d@@'
    H('?update@CCScheduler@cocos2d@@UEAAXM@Z', _h_tick, restype=None, argtypes=[v, f])
    state.key_hook = H('?dispatchKeyboardMSG@CCKeyboardDispatcher@cocos2d@@QEAA_NW4enumKeyCodes@2@_N1N@Z', _h_key,
                       restype=b, argtypes=[v, i, b, b, c_double])
    for n, kind in (('Began', 0), ('Moved', 1), ('Ended', 2), ('Cancelled', 3)):
        optional.append(('?touches%s@CCTouchDispatcher@%sUEAAXPEAVCCSet@2@PEAVCCEvent@2@@Z' % (n, cc),
                         _touch_hook(kind), None, [v, v, v]))
    optional += [
        ('?dispatchKeypadMSG@CCKeypadDispatcher@cocos2d@@QEAA_NW4ccKeypadMSGType@2@@Z', _h_keypad, b, [v, i]),
        ('?dispatchInsertText@CCIMEDispatcher@cocos2d@@QEAAXPEBDHW4enumKeyCodes@2@@Z', _h_insert, None,
         [v, v, i, i]),
        ('?dispatchDeleteBackward@CCIMEDispatcher@cocos2d@@QEAAXXZ', _h_delete, None, [v]),
        ('?dispatchScrollMSG@CCMouseDispatcher@cocos2d@@QEAA_NMM@Z', _h_scroll, b, [v, f, f]),
    ]
    optional += [
        ('GameManager::isIconUnlocked', _h_icon_unlocked, None, None),
        ('GameManager::isColorUnlocked', _h_color_unlocked, None, None),
        ('GameStatsManager::isItemUnlocked', _h_item_unlocked, None, None),
    ]
    for name, h, rt, at in optional:
        try:
            if at is None:
                H(name, h)
            else:
                H(name, h, restype=rt, argtypes=at)
        except Exception as e:
            print('[PyModder] hook %s not installed: %s' % (name, e))
    for action, name in PAUSE_ACTIONS.items():
        try:
            _pause_hooks[action] = H(name, _pause_hook(action))
        except Exception as e:
            print('[PyModder] hook %s not installed: %s' % (name, e))
    state.percent_fn = N.function('PlayLayer::getCurrentPercent')
    state.handle_button = N.function('GJBaseGameLayer::handleButton')
    for mod in ('_speed', '_input'):
        try:
            __import__(__package__ + '.' + mod, fromlist=['install']).install()
        except Exception:
            traceback.print_exc()


# ---------------------------------------------------------------- public helpers
def on_main_thread():
    return _main_thread[0] is None or M.k32.GetCurrentThreadId() == _main_thread[0]


def when_scene_ready(func):
    _pending.append(func)


def later(func):
    """Run func on the game thread on the next frame (safe from any thread)."""
    _later.append(func)


def background(func, *args, owner=None):
    owner = owner or caller_owner()

    def run():
        try:
            func(*args)
        except Exception:
            report(owner, 'background task')
    t = threading.Thread(target=run, daemon=True, name='pymodder-' + mod_name(owner))
    t.start()
    return t


def fps():
    return _fps[0]


def notify(text, seconds=2.5, color=(255, 255, 255)):
    def show():
        w, h = C.win_size()
        _notes[:] = [n for n in _notes if n[1] > time.perf_counter()]
        y = h - 18 - 20 * len(_notes)
        lb = C.Label(text, w / 2, y, 0.45, color=color, parent=C.running_scene(), z=Z_NOTE)
        lb.fade_and_remove(seconds)
        _notes.append([lb, time.perf_counter() + seconds + 0.4])
    when_scene_ready(show)


class Label:
    """Text on the screen that stays when the scene changes."""

    def __init__(self, text='', x=None, y=None, size=0.5, color=(255, 255, 255), font=None, anchor=None):
        self._args = [str(text), x, y, size, tuple(color), font]
        self._anchor = anchor
        self._lb = None
        self.node, self.z = None, 10000
        self.owner = caller_owner()
        self._visible = True
        when_scene_ready(self._create)

    def _create(self):
        if self._lb:
            return
        text, x, y, size, color, font = self._args
        w, h = C.win_size()
        x = w / 2 if x is None else (w + x if x < 0 else x)      # negative = from the right / top edge
        y = h / 2 if y is None else (h + y if y < 0 else y)
        self._lb = C.Label(text, x, y, size, font, color, anchor_xy=self._anchor)
        C.fn('retain')(self._lb.node)
        self.node = self._lb.node
        if not self._visible:
            self._lb.visible(False)
        _persistent.append(self)

    def _do(self, f):
        if self._lb:
            f(self._lb)
        else:
            when_scene_ready(lambda: self._lb and f(self._lb))

    @property
    def text(self):
        return self._args[0]

    @text.setter
    def text(self, value):
        value = str(value)
        if value == self._args[0]:
            return
        self._args[0] = value

        def upd(lb):
            old = lb.node
            lb.text = value
            if lb.node != old:          # font changed -> new node
                C.fn('retain')(lb.node)
                C.fn('release')(old)
                self.node = lb.node
        self._do(upd)

    def move(self, x, y):
        self._args[1], self._args[2] = x, y

        def mv(lb):
            w, h = C.win_size()
            lb.move(w + x if x < 0 else x, h + y if y < 0 else y)
        self._do(mv)

    @property
    def color(self):
        return self._args[4]

    @color.setter
    def color(self, rgb):
        self._args[4] = tuple(rgb)
        self._do(lambda lb: setattr(lb, 'color', rgb))

    def show(self, visible=True):
        self._visible = bool(visible)
        self._do(lambda lb: lb.visible(visible))

    def hide(self):
        self.show(False)

    def remove(self):
        def rm(lb):
            if self in _persistent:
                _persistent.remove(self)
            C.fn('remove')(lb.node, True)
            C.fn('release')(lb.node)
            self._lb = self.node = None
        self._do(rm)


class Draw:
    """Draw lines/rectangles/circles. world=True - in level coordinates (next to the player)."""

    def __init__(self, world=False, z=None):
        self.world = bool(world)
        self.z = z if z is not None else (9999 if world else 9000)
        self.node = None
        self._visible = True
        self.owner = caller_owner()

    def _ensure(self):
        if self.node:
            return self.node
        if self.world:
            if not (state.started and state.player):
                return None
            parent = C.fn('parent')(state.player.ptr)
            if not parent:
                return None
            self.node = C.draw_node()
            C.fn('retain')(self.node)
            C.fn('add_child')(parent, self.node, self.z)
            _world_draws.append(self)
        else:
            scene = C.running_scene()
            if not scene:
                return None
            self.node = C.draw_node()
            C.fn('retain')(self.node)
            C.fn('add_child')(scene, self.node, self.z)
            _persistent.append(self)
        if not self._visible:
            C.fn('set_visible')(self.node, False)
        return self.node

    def _drop(self):
        for lst in (_world_draws, _persistent):
            if self in lst:
                lst.remove(self)
        if self.node:
            node, self.node = self.node, None
            C.fn('remove')(node, True)
            C.fn('release')(node)

    def line(self, x1, y1, x2, y2, color=(255, 255, 255), width=2):
        n = self._ensure()
        n and C.draw_line(n, x1, y1, x2, y2, color, width)

    def dot(self, x, y, radius=3, color=(255, 255, 255)):
        n = self._ensure()
        n and C.draw_dot(n, x, y, radius, color)

    def polygon(self, points, color=(255, 255, 255), border=0, border_color=None, fill=True):
        n = self._ensure()
        if n and len(points) >= 3:
            fc = color if fill else tuple(color[:3]) + (0,)
            C.draw_poly(n, points, fc, border if (border or fill) else 1, border_color or color)

    def rect(self, x, y, w, h, color=(255, 255, 255), fill=True, border=0, border_color=None):
        """x, y - bottom left corner."""
        self.polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], color, border or (0 if fill else 1.5),
                     border_color, fill)

    def circle(self, x, y, radius, color=(255, 255, 255), fill=True, border=0, border_color=None, segments=32):
        import math
        pts = [(x + radius * math.cos(2 * math.pi * i / segments), y + radius * math.sin(2 * math.pi * i / segments))
               for i in range(segments)]
        self.polygon(pts, color, border or (0 if fill else 1.5), border_color, fill)

    def clear(self):
        if self.node:
            C.fn('dn_clear')(self.node)

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, v):
        self._visible = bool(v)
        if self.node:
            C.fn('set_visible')(self.node, self._visible)

    def remove(self):
        self._drop()


def after(seconds, func, owner=None):
    _timers.append([time.perf_counter() + seconds, None, func, owner or caller_owner()])


def every(seconds, func, owner=None):
    _timers.append([time.perf_counter() + seconds, seconds, func, owner or caller_owner()])


BUTTONS = {'jump': 1, 'left': 2, 'right': 3}


def button_code(button):
    if isinstance(button, str):
        if button.lower() not in BUTTONS:
            raise ValueError('button must be "jump", "left" or "right", not %r' % button)
        return BUTTONS[button.lower()]
    return int(button)


def press(button=1, player2=False):
    button = button_code(button)
    if state.layer and state.started:
        state.in_press = True
        try:
            state.handle_button(state.layer, True, button, not player2)
        finally:
            state.in_press = False


def release(button=1, player2=False):
    button = button_code(button)
    if state.layer and state.started:
        state.in_press = True
        try:
            state.handle_button(state.layer, False, button, not player2)
        finally:
            state.in_press = False


def pause_game():
    if state.started and state.layer and not state.paused:
        _call('PlayLayer::pauseGame', state.layer, False)


def restart(full=False):
    if not (state.started and state.layer):
        return
    if state.paused:
        scene = C.running_scene()
        for pl in C.find_children(scene, 'PauseLayer', 1):
            _call('PauseLayer::onRestartFull' if full else 'PauseLayer::onRestart', pl, None)
            return
    _call('PlayLayer::resetLevelFromStart' if full else 'PlayLayer::resetLevel', state.layer)


def game_var(key, value=None):
    gm = _call('GameManager::sharedState')
    if value is not None:
        _call('GameManager::setGameVariable', gm, str(key).encode(), bool(value))
    return bool(_call('GameManager::getGameVariable', gm, str(key).encode()))


# ---------------------------------------------------------------- storage
def _data_path(owner):
    d = os.path.join(ROOT, 'mods', 'data')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, mod_name(owner) + '.json')


_data = {}


def _data_of(owner):
    if owner not in _data:
        try:
            _data[owner] = json.load(open(_data_path(owner), encoding='utf-8-sig'))
        except Exception:
            _data[owner] = {}
    return _data[owner]


def _write_data(owner):
    tmp = _data_path(owner) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_data_of(owner), f, ensure_ascii=False, indent=1)
    os.replace(tmp, _data_path(owner))


def save(key, value, owner=None):
    owner = owner or caller_owner()
    _data_of(owner)[key] = value
    _write_data(owner)


def load(key, default=None, owner=None):
    return _data_of(owner or caller_owner()).get(key, default)


# ---------------------------------------------------------------- settings
class Setting:
    """A mod setting: shown in the mods menu (gear button), saved automatically."""
    saved = True

    def __init__(self, owner, key, default, title=None, description='', min=None, max=None, step=None,
                 options=None, kind=None):
        self.owner, self.key, self.default = owner, str(key), default
        self.title, self.description = str(title or key), description
        self.min, self.max, self.step, self.options = min, max, step, list(options) if options else None
        if kind is None:
            if isinstance(default, bool):
                kind = 'bool'
            elif _is_rgb(default):
                kind = 'color'
            elif self.options:
                kind = 'choice'
            elif isinstance(default, int):
                kind = 'int'
            elif isinstance(default, float):
                kind = 'float'
            else:
                kind = 'text'
        self.kind = kind
        self._handlers = []
        stored = _data_of(owner).get('_settings', {}).get(self.key, default)
        try:
            self._value = self._coerce(stored)
        except Exception:
            self._value = default

    def _coerce(self, v):
        k = self.kind
        if k == 'bool':
            return bool(v)
        if k in ('int', 'float'):
            v = int(round(float(v))) if k == 'int' else float(v)
            if self.min is not None:
                v = max(self.min, v)
            if self.max is not None:
                v = min(self.max, v)
            return v
        if k == 'choice':
            return v if v in self.options else self.default
        if k == 'key':
            key_code(v)
            return str(v).upper()
        if k == 'color':
            return parse_color(v)
        return str(v)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        v = self._coerce(v)
        if v == self._value:
            return
        self._value = v
        _data_of(self.owner).setdefault('_settings', {})[self.key] = v
        _write_data(self.owner)
        for f in list(self._handlers):
            U.flex_call(self.owner, f, v)

    def on_change(self, func):
        """Decorator: func(value) is called when the setting changes."""
        self._handlers.append(func)
        return func

    def reset(self):
        self.value = self.default

    def set(self, value):
        """The same as s.value = value (handy as a callback: p.toggle("On", s.value, s.set))."""
        self.value = value

    def __bool__(self):
        return bool(self._value)

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)

    def __str__(self):
        return str(self._value)

    def __format__(self, spec):
        return format(self._value, spec)

    def __repr__(self):
        return '<Setting %s=%r>' % (self.key, self._value)


def _is_rgb(v):
    return isinstance(v, (tuple, list)) and len(v) == 3 and all(
        isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in v)


parse_color = U.parse_color      # (r, g, b) from a tuple / list or "#rrggbb"


class SettingItem:
    """Not a saved value: a header, a line of text or a button in the mod settings popup."""
    saved = False

    def __init__(self, owner, kind, title, callback=None, color='green', description=''):
        self.owner, self.kind, self.title = owner, kind, str(title)
        self.callback, self.color, self.description = callback, color, description or ''
        self.key = '_%s_%x' % (kind, id(self))
        self.default = self.value = None

    def reset(self):
        pass

    def __repr__(self):
        return '<%s %r>' % (self.kind, self.title)


def add_setting_item(owner, kind, title, **kw):
    lst = settings.setdefault(owner, [])
    for s in lst:           # the same item again (e.g. the module is imported twice) -> keep one
        if isinstance(s, SettingItem) and s.kind == kind and s.title == str(title) and kind != 'space':
            s.callback = kw.get('callback', s.callback)
            return s
    s = SettingItem(owner, kind, title, **kw)
    lst.append(s)
    return s


def add_setting(owner, key, default, **kw):
    lst = settings.setdefault(owner, [])
    for s in lst:
        if s.key == key:
            return s
    s = Setting(owner, key, default, **kw)
    lst.append(s)
    return s


# ---------------------------------------------------------------- mods
def _forget(owner):
    for k in [k for k in _err_counts if k[0] == owner]:
        del _err_counts[k]
    for ev in handlers.values():
        ev[:] = [h for h in ev if h[1] != owner]
    _timers[:] = [t for t in _timers if t[3] != owner]
    for obj in [o for o in _persistent + _world_draws if getattr(o, 'owner', None) == owner]:
        try:
            obj.remove()
        except Exception:
            traceback.print_exc()
    try:
        U.close_owner(owner)
        from . import _menu
        _menu.forget_owner(owner)
    except Exception:
        traceback.print_exc()
    for f in list(cleanup_hooks):
        try:
            f(owner)
        except Exception:
            traceback.print_exc()
    N.remove_owner(owner)
    settings.pop(owner, None)
    _data.pop(owner, None)
    sys.modules.pop(owner, None)


def _meta(path):
    """NAME / VERSION / AUTHOR / DESCRIPTION / ICON from the file without running it."""
    out = {}
    try:
        src = open(path, encoding='utf-8').read()
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in ('NAME', 'VERSION', 'AUTHOR', 'DESCRIPTION', 'ICON', 'MENU_KEY'):
                    try:
                        out[name.lower()] = str(ast.literal_eval(node.value))
                    except Exception:
                        pass
        if 'description' not in out:
            doc = ast.get_docstring(tree)
            if doc:
                out['description'] = doc.strip().split('\n\n')[0]
            else:
                lines = []
                for ln in src.splitlines():
                    if ln.startswith('#') and not ln.startswith(('#!', '# -*-')):
                        lines.append(ln.lstrip('#').strip())
                    else:
                        break
                if lines:
                    out['description'] = ' '.join(lines)
    except Exception:
        pass
    return out


def builtin_icons():
    """Names of the built-in icons (pymodder/res/icons/<name>.png)."""
    d = os.path.join(ROOT or '.', 'res', 'icons')
    try:
        return sorted(f[:-4] for f in os.listdir(d) if f.lower().endswith('.png'))
    except OSError:
        return []


def builtin_icon(name):
    """Path of a built-in icon ("skull", "star", ...) or None."""
    if not name:
        return None
    n = str(name).strip().lower()
    if n.endswith('.png'):
        n = n[:-4]
    if not n or not all(ch.isalnum() or ch in '_-' for ch in n):
        return None
    p = os.path.join(ROOT or '.', 'res', 'icons', n + '.png')
    return p if os.path.isfile(p) else None


def _icon_of(path, icon=None):
    """Icon of a mod for the mods menu: ICON = "file.png" / a built-in icon name ("skull") / a GD frame name,
    icon.png in the mod folder, or <name>.png next to a one-file mod. None -> the default icon."""
    d = os.path.dirname(os.path.abspath(path))
    if icon:
        icon = str(icon)
        p = icon if os.path.isabs(icon) else os.path.join(d, icon)
        if os.path.isfile(p):
            return p
        b = builtin_icon(icon)
        if b:
            return b
        return icon                # maybe a GD frame name ("GJ_starsIcon_001.png")
    if os.path.basename(path) == 'main.py':
        p = os.path.join(d, 'icon.png')
    else:
        p = os.path.splitext(os.path.abspath(path))[0] + '.png'
    return p if os.path.isfile(p) else None


def _owner_of(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    if os.path.basename(path) == 'main.py':
        stem = os.path.basename(os.path.dirname(path))
    return stem, 'gdmod_' + ''.join(ch if ch.isalnum() else '_' for ch in stem)


def load_mod(path):
    stem, owner = _owner_of(path)
    meta = _meta(path)
    info = mods[owner] = {'name': stem, 'id': owner, 'path': path, 'ok': False, 'error': None, 'traceback': '',
                          'runtime_error': None, 'enabled': True, 'title': meta.get('name', stem),
                          'version': meta.get('version', ''), 'author': meta.get('author', ''),
                          'description': meta.get('description', ''), 'icon': _icon_of(path, meta.get('icon'))}
    if stem in CFG.get('disabled_mods', []):
        info['enabled'] = False
        print('[PyModder] mod disabled: %s' % stem)
        return info
    try:
        spec = importlib.util.spec_from_file_location(owner, path)
        mod = importlib.util.module_from_spec(spec)
        mod.MOD_DIR = os.path.dirname(os.path.abspath(path))
        sys.modules[owner] = mod
        spec.loader.exec_module(mod)
        info.update(ok=True, title=str(getattr(mod, 'NAME', info['title'])),
                    version=str(getattr(mod, 'VERSION', info['version'])),
                    author=str(getattr(mod, 'AUTHOR', info['author'])),
                    description=str(getattr(mod, 'DESCRIPTION', info['description']) or ''),
                    icon=_icon_of(path, getattr(mod, 'ICON', None) or meta.get('icon')))
        mk = getattr(mod, 'MENU_KEY', None)
        if mk and owner not in menu_keys:
            set_menu_key(owner, mk)
        print('[PyModder] mod loaded: %s' % stem)
    except Exception as e:
        info['error'] = '%s: %s' % (type(e).__name__, e)
        info['traceback'] = traceback.format_exc(limit=-8)
        report(owner, 'loading')
        _forget(owner)
    return info


def mod_files():
    d = os.path.join(ROOT, 'mods')
    out = []
    for fn in sorted(os.listdir(d), key=str.lower):
        p = os.path.join(d, fn)
        if fn.endswith('.py') and not fn.startswith(('_', '.')):
            out.append(p)
        elif os.path.isdir(p) and os.path.isfile(os.path.join(p, 'main.py')) and fn != 'data':
            out.append(os.path.join(p, 'main.py'))
    return out


def load_mods():
    for p in mod_files():
        load_mod(p)


def _start_mod(owner):
    emit_owner(owner, 'load')
    if state.started:
        emit_owner(owner, 'level_start', state.level)


def reload_mods(quiet=False):
    for owner in list(mods):
        emit_owner(owner, 'unload')
        _forget(owner)
    mods.clear()
    load_mods()
    for owner in mods:
        _start_mod(owner)
    if not quiet:
        good = sum(1 for m in mods.values() if m['ok'])
        notify('Mods reloaded (%d)' % good, 2, (120, 255, 120))
    try:
        from . import _menu
        _menu.refresh_menu()
    except Exception:
        traceback.print_exc()


def set_mod_enabled(owner, on):
    info = mods.get(owner)
    if not info:
        return
    dis = [x for x in CFG.get('disabled_mods', []) if x != info['name']]
    if not on:
        dis.append(info['name'])
    CFG['disabled_mods'] = dis
    save_config()
    if on and not info['ok']:
        new = load_mod(info['path'])
        if new['ok']:
            _start_mod(owner)
    elif not on:
        if info['ok']:
            emit_owner(owner, 'unload')
            _forget(owner)
        info.update(ok=False, enabled=False, error=None, runtime_error=None)


def save_config():
    path = os.path.join(ROOT, 'config.json')
    try:
        cur = json.load(open(path, encoding='utf-8-sig')) if os.path.exists(path) else {}
    except Exception:
        cur = {}
    cur.update({k: CFG[k] for k in CFG})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)


def emit_owner(owner, event, *args):
    for func, o, _ in list(handlers.get(event, ())):
        if o == owner:
            try:
                func(*args)
            except Exception:
                report(owner, event)


def start(root, cfg):
    global ROOT, GD_DIR
    ROOT = root
    GD_DIR = os.path.dirname(root)
    CFG.update(cfg)
    U.CFG['invert_scroll'] = CFG.get('invert_scroll', False)
    ver = N.load(root)
    print('[PyModder] GeometryDash.exe timestamp=%d, bindings: %s, loader: %s' % (N.gd_module.timestamp, ver,
                                                                              N.loader_path))
    if not ver:
        print('[PyModder] no bindings for this GD version - mods are off. Put a .bro/.json file into pymodder/bindings')
        return
    C.init(GD_DIR)
    try:
        from . import _plugins
        _plugins.clean_cache()
    except Exception:
        traceback.print_exc()
    install_hooks()
    U.hooks['menu_key_code'] = _cfg_code('menu_key')
    print('[PyModder] hooks installed: %d' % len(N.hooks))
