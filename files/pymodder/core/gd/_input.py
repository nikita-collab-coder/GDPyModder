"""Simulated input (game buttons, taps, keys) and macros (record / play clicks, .macro files)."""
import time
import traceback

from . import _core as K
from . import _cocos as C
from . import _storage as S
from . import _ui as U
from . import _mem as M

_held_touch = [False]


# ---------------------------------------------------------------- game buttons
def hold(seconds, button=1, player2=False, owner=None):
    K.press(button, player2)
    K.after(max(0.0, float(seconds)), lambda: K.release(button, player2), owner or K.caller_owner())


# ---------------------------------------------------------------- touches / mouse
def touch_down(x, y):
    C.sim_touch('begin', x, y)
    _held_touch[0] = True


def touch_move(x, y):
    if _held_touch[0]:
        C.sim_touch('move', x, y)


def touch_up(x, y):
    if _held_touch[0]:
        _held_touch[0] = False
        C.sim_touch('end', x, y)


def tap(x, y, hold_time=0.0, owner=None):
    """Click at a screen point: menus, GD buttons and PyModder windows react as to the mouse."""
    if _held_touch[0]:
        touch_up(x, y)
    touch_down(x, y)
    if hold_time and hold_time > 0:
        K.after(hold_time, lambda: touch_up(x, y), owner or K.caller_owner())
    else:
        K.later(lambda: touch_up(x, y))


def mouse_pos():
    return C.mouse_pos()


# ---------------------------------------------------------------- keyboard
def _dispatch_key(code, down):
    disp = C.fn('kbd_dispatcher')(C.director())
    if not disp:
        return False
    h = K.state.key_hook
    f = h.original if h is not None and h.original else C.fn('kbd_dispatch')
    return bool(f(disp, int(code), bool(down), False, time.perf_counter()))


def key_down(key):
    """Press a keyboard key for the game (PyModder's own key handlers do not see it)."""
    return _dispatch_key(K.key_code(key), True)


def key_up(key):
    return _dispatch_key(K.key_code(key), False)


def key_tap(key, hold_time=0.0, owner=None):
    code = K.key_code(key)
    _dispatch_key(code, True)
    if hold_time and hold_time > 0:
        K.after(hold_time, lambda: _dispatch_key(code, False), owner or K.caller_owner())
    else:
        K.later(lambda: _dispatch_key(code, False))


# ---------------------------------------------------------------- macros
# Macros work by physics ticks, not by time: GD 2.2 moves the game in fixed steps (240 per second), and
# GJBaseGameLayer counts them (+2 for a step, +1 for a half step). Clicks are recorded with the tick of
# the step they were handled in and replayed right before the queued input of the same step
# (GJBaseGameLayer::processQueuedButtons), so a replay is the same at any FPS and game speed.
# "Click between steps" (half steps) is turned off while a macro records / plays.
FORMAT = 'pymodder-macro'
TPS = 240                    # physics steps per second
TICKS_PER_SECOND = TPS * 2   # GD's step counter
_active = []                 # macros that record or play

# GJBaseGameLayer fields (GD 2.2091): tick - the step counter (m_currentProgress, set by resetLevel,
# loadFromCheckpoint, start positions), step - the tick of the step being processed now,
# cbs - "click between steps" is on for this level (half steps on input).
OFFSETS = {'2.2091': dict(tick=0x3E0, step=0x3EC, cbs=0x38F1)}
_in_queue = [False]          # inside processQueuedButtons
_hooked = [False]
_cbs = [0, None]             # layer, its original "click between steps" value


def _off():
    from . import _native as N
    return OFFSETS.get(N.version or '')


def current_tick(next_step=True):
    """GD's step counter of the running level (480 per second). next_step=True: the tick an input
    given now acts on."""
    layer = K.state.layer if K.state.started else 0
    o = _off()
    if not layer or not o:
        return 0
    if _in_queue[0]:
        return M.i32(layer + o['step'], 0)
    return M.i32(layer + (o['tick'] if next_step else o['step']), 0)


def seconds_to_tick(t):
    return int(round(float(t) * TPS)) * 2


def _h_queue(orig, this, dt, flush):
    if not _active or this != K.state.layer or not K.state.started:
        return orig()
    o = _off()
    tick = M.i32(this + o['step'], 0)
    for m in list(_active):
        if m.playing and not m._wait_start:
            try:
                m._fire(tick)
            except Exception:
                traceback.print_exc()
    _in_queue[0] = True
    try:
        return orig()
    finally:
        _in_queue[0] = False


def _ensure_hooks():
    if _hooked[0]:
        return True
    from . import _native as N
    try:
        N.hook('GJBaseGameLayer::processQueuedButtons', _h_queue)
        _hooked[0] = True
    except Exception as e:
        print('[PyModder] macro hook not installed:', e)
    return _hooked[0]


def _sync_cbs():
    """Half steps off while a macro is busy in this level, the level's own value back after."""
    o = _off()
    if not o:
        return
    layer = K.state.layer if K.state.started else 0
    busy = bool(layer) and any(m.recording or m.playing for m in _active)
    if _cbs[0] and _cbs[0] != layer:
        if K.state.layer == _cbs[0] and _cbs[1] is not None:
            M.write_u8(_cbs[0] + o['cbs'], _cbs[1])
        _cbs[0], _cbs[1] = 0, None
    if busy:
        if _cbs[0] != layer:
            _cbs[0], _cbs[1] = layer, M.u8(layer + o['cbs'])
        M.write_u8(layer + o['cbs'], 0)
    elif _cbs[0]:
        if _cbs[1] is not None:
            M.write_u8(_cbs[0] + o['cbs'], _cbs[1])
        _cbs[0], _cbs[1] = 0, None


def busy():
    """A macro records or plays right now."""
    return any(m.recording or m.playing for m in _active)


def _block(on):
    K.state.block_input = bool(on)


class Macro:
    """Record and play back clicks, exactly by physics ticks (480 per second).
    A .macro file is JSON: {"version": 2, "inputs": [[tick, down, button, player2], ...]}.

        m = gd.Macro()
        m.record()             # the level restarts, clicks are recorded
        ...
        m.stop(); m.save("my_run.macro")
        gd.Macro.load("my_run.macro").play()
    """

    def __init__(self, inputs=None, name='', level=None, owner=None, version=2):
        self.owner = owner or K.caller_owner()
        self.name = name
        self.inputs = [self._row(r, version) for r in (inputs or [])]
        self.inputs.sort(key=lambda r: r[0])
        self.level = level            # {'id': ..., 'name': ...}
        self.recording = self.playing = False
        self.loop = False
        self.block_input = True       # the player's own clicks are ignored while it plays
        self.on_finish = None
        self._i = 0
        self._held = set()
        self._wait_start = False
        self._done = False

    # --- data
    @staticmethod
    def _row(r, version=2):
        if isinstance(r, dict):
            if 'tick' in r:
                r, version = [r['tick'], r.get('down', True), r.get('button', 1), r.get('player2', False)], 2
            else:
                r, version = [r.get('t', r.get('time', 0)), r.get('down', True), r.get('button', 1),
                              r.get('player2', False)], 1
        tick = seconds_to_tick(r[0]) if version < 2 else int(r[0])
        down = bool(r[1]) if len(r) > 1 else True
        button = K.button_code(r[2]) if len(r) > 2 else 1
        p2 = bool(r[3]) if len(r) > 3 else False
        return [max(0, tick), 1 if down else 0, button, 1 if p2 else 0]

    def _insert(self, row):
        import bisect
        keys = [r[0] for r in self.inputs]
        self.inputs.insert(bisect.bisect_right(keys, row[0]), row)

    def add(self, t, down=True, button=1, player2=False):
        """Add a click by hand at t seconds: m.add(1.5, True) ... m.add(1.7, False)."""
        self._insert(self._row([seconds_to_tick(t), down, button, player2]))
        return self

    def add_tick(self, tick, down=True, button=1, player2=False):
        """Add a click at a physics tick (480 per second, the first step is tick 0)."""
        self._insert(self._row([tick, down, button, player2]))
        return self

    def click(self, t, length=0.05, button=1, player2=False):
        """Press at time t and release `length` seconds later (at least one step later)."""
        a = seconds_to_tick(t)
        self._insert(self._row([a, True, button, player2]))
        self._insert(self._row([max(a + 2, seconds_to_tick(t + max(0.0, length))), False, button, player2]))
        return self

    def clear(self):
        self.inputs = []
        return self

    @property
    def ticks(self):
        return self.inputs[-1][0] if self.inputs else 0

    @property
    def duration(self):
        """Length in seconds of level time."""
        return self.ticks / float(TICKS_PER_SECOND)

    @property
    def clicks(self):
        return sum(1 for r in self.inputs if r[1])

    @property
    def position(self):
        """How many inputs are already played."""
        return self._i

    def __len__(self):
        return len(self.inputs)

    def __repr__(self):
        st = 'rec' if self.recording else ('play' if self.playing else 'idle')
        return '<Macro %r %d inputs %.2fs %s>' % (self.name, len(self.inputs), self.duration, st)

    def to_dict(self):
        lv = self.level
        if lv is None and K.state.level:
            lv = {'id': K.state.level.id, 'name': K.state.level.name}
        return {'format': FORMAT, 'version': 2, 'name': self.name, 'level': lv, 'tps': TPS,
                'inputs': [list(r) for r in self.inputs]}

    @classmethod
    def from_dict(cls, data, owner=None):
        if isinstance(data, list):
            data = {'inputs': data}
        ver = data.get('version', 1)
        try:
            ver = int(ver)
        except (TypeError, ValueError):
            ver = 1
        return cls(data.get('inputs', []), data.get('name', ''), data.get('level'), owner=owner, version=ver)

    def save(self, name):
        """Save to pymodder/saves/<mod>/name (the name must end with .macro)."""
        if not str(name).lower().endswith('.macro'):
            raise ValueError('a macro is saved to a .macro file')
        if not self.name:
            self.name = str(name)[:-6]
        return S.save(self.owner, name, self.to_dict())

    @classmethod
    def load(cls, name, owner=None):
        owner = owner or K.caller_owner()
        if not str(name).lower().endswith('.macro'):
            raise ValueError('a macro is loaded from a .macro file')
        data = S.load(owner, name, None)
        if data is None:
            raise FileNotFoundError('no file %s in pymodder/saves/%s' % (name, K.mod_name(owner)))
        return cls.from_dict(data, owner)

    # --- control
    def record(self, restart=True):
        """Start recording. restart=True - the level restarts (otherwise recording starts with the next attempt).
        Practice mode works: going back to a checkpoint drops the clicks after it."""
        self.stop()
        self.recording = True
        self.inputs = []
        self._wait_start = True
        _activate(self)
        if restart and K.state.started:
            K.restart(full=True)
        return self

    def play(self, restart=True, loop=False):
        """Play it back. restart=True - the level restarts. loop=True - again on every attempt
        (otherwise it stops when the level restarts from the start; a practice checkpoint continues)."""
        self.stop()
        self.playing, self.loop = True, bool(loop)
        self._i = 0
        self._done = False
        self._wait_start = True
        _activate(self)
        if restart and K.state.started:
            K.restart(full=True)
        return self

    def stop(self):
        self.recording = self.playing = False
        self._wait_start = False
        self._release_all()
        if self in _active:
            _active.remove(self)
        _sync_cbs()
        _block(any(m.playing and m.block_input for m in _active))
        return self

    # --- engine
    def _send(self, down, button, p2):
        key = (button, bool(p2))
        if down:
            K.press(button, bool(p2))
            self._held.add(key)
        else:
            K.release(button, bool(p2))
            self._held.discard(key)

    def _release_all(self):
        for button, p2 in list(self._held):
            try:
                K.release(button, p2)
            except Exception:
                traceback.print_exc()
        self._held.clear()

    def _held_before(self, tick):
        held = set()
        for t, down, button, p2 in self.inputs:
            if t >= tick:
                break
            (held.add if down else held.discard)((button, bool(p2)))
        return held

    def _attempt(self, tick):
        if self._wait_start:
            self._wait_start = False
        elif self.playing and not self.loop and tick <= 0:
            self._done = True           # the level started again from the start
            return
        self._release_all()
        if self.recording:
            # a new attempt / practice checkpoint: keep the clicks before it, the buttons are up again
            held = self._held_before(tick)
            self.inputs = [r for r in self.inputs if r[0] < tick]
            for button, p2 in sorted(held):
                self.inputs.append([tick, 0, button, 1 if p2 else 0])
            return
        import bisect
        self._i = bisect.bisect_left([r[0] for r in self.inputs], tick)
        self._done = False
        for button, p2 in sorted(self._held_before(tick)):
            self._send(True, button, p2)       # buttons held at this point of the macro

    def _finish(self):
        cb = self.on_finish
        self.stop()
        if cb:
            U.flex_call(self.owner, cb, self)

    def _fire(self, tick):
        rows = self.inputs
        while self._i < len(rows) and rows[self._i][0] <= tick:
            _, down, button, p2 = rows[self._i]
            self._i += 1
            self._send(down, button, p2)
        if self._i >= len(rows) and not self.loop and not self._held:
            self._done = True

    def _step(self, dt):
        if self.playing and self._done:
            self._finish()

    def _input(self, down, button, p2):
        if self.recording and not self._wait_start:
            self.inputs.append([current_tick(), 1 if down else 0, button, 1 if p2 else 0])


def _activate(m):
    _ensure_hooks()
    if m not in _active:
        _active.append(m)
    _sync_cbs()
    _block(any(x.playing and x.block_input for x in _active))


def _on_attempt():
    tick = current_tick()
    _sync_cbs()
    for m in list(_active):
        m._attempt(tick)


def _on_update(dt):
    for m in list(_active):
        m._step(dt)


def _on_button(down, button, p2):
    for m in list(_active):
        m._input(down, button, p2)


def _on_leave():
    for m in list(_active):
        m.stop()                       # a recording keeps its inputs
    _sync_cbs()
    _block(False)


def _on_complete(level):
    for m in list(_active):
        if m.recording:
            m.stop()                   # the run is finished: do not lose it on the next attempt


def _cleanup(owner):
    for m in list(_active):
        if m.owner == owner:
            m.stop()


def install():
    pass


K.attempt_listeners.append(_on_attempt)
K.pre_update.append(_on_update)
K.button_listeners.append(_on_button)
K.leave_hooks.append(_on_leave)
K.add_handler('complete', _on_complete, 'pymodder')
K.cleanup_hooks.append(_cleanup)
