"""Experimental "click between frames": a 1 ms input polling thread remembers WHEN each press happened and
the level update is split at that moment, so presses are not rounded to the frame (useful at low FPS).
Precision is the physics step of the game (1/240 s)."""
import ctypes
import threading
import time
import traceback

from . import _core as K
from . import _native as N

GROUPS = {1: (0x20, 0x26, 0x57, 0x01), 2: (0x25, 0x41), 3: (0x27, 0x44)}   # jump, left, right (VK codes)
_on = set()
_events = []         # [(t, button, down)] from the polling thread
_queue = []          # [(t, down, button, is_p1)] real presses waiting for the next update
_last_update = [None]
_lock = threading.Lock()
_thread = [None]
_replaying = [False]
_hooked = [False]
_user = [None]


def _foreground():
    u = _user[0]
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return False
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    return pid.value == ctypes.windll.kernel32.GetCurrentProcessId()


def _poll():
    u = _user[0]
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass
    state = {b: False for b in GROUPS}
    while _on:
        try:
            if K.state.started and not K.state.paused and _foreground():
                now = time.perf_counter()
                for b, keys in GROUPS.items():
                    d = any(u.GetAsyncKeyState(k) & 0x8000 for k in keys)
                    if d != state[b]:
                        state[b] = d
                        with _lock:
                            _events.append((now, b, d))
                            if len(_events) > 200:
                                del _events[:100]
            time.sleep(0.001)
        except Exception:
            traceback.print_exc()
            time.sleep(0.05)
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass
    _thread[0] = None


def _when(button, down):
    """Time of the polled press that matches a real one (now if the poller did not see it)."""
    now = time.perf_counter()
    with _lock:
        for i, (t, b, d) in enumerate(_events):
            if b == button and d == down and now - t < 0.1:
                del _events[:i + 1]
                return t
    return now


def _h_button(orig, this, down, button, is_p1):
    if _replaying[0] or not _on or this != K.state.layer or not K.state.started or K.state.in_press:
        return orig()
    from . import _input
    if _input.busy():          # a macro records / plays: input goes by physics ticks
        return orig()
    _queue.append((_when(button, bool(down)), bool(down), int(button), bool(is_p1)))
    return None


def _h_update(orig, this, dt):
    now = time.perf_counter()
    prev, _last_update[0] = _last_update[0], now
    if not _queue or this != K.state.layer or prev is None or now - prev <= 0 or dt <= 0:
        if _queue and this == K.state.layer:
            _flush(this)
        return orig()
    q = sorted(_queue)
    _queue[:] = []
    done = 0.0
    span = now - prev
    for t, down, button, p1 in q:
        f = min(1.0, max(0.0, (t - prev) / span))
        part = dt * f - done
        if part > 1e-6:
            orig(this, part)
            done += part
        _press(this, down, button, p1)
    rest = dt - done
    if rest > 1e-6:
        orig(this, rest)
    return None


def _press(this, down, button, p1):
    _replaying[0] = True
    was, K.state.in_press = K.state.in_press, True
    try:
        N.function('GJBaseGameLayer::handleButton')(this, down, button, p1)
    finally:
        _replaying[0] = False
        K.state.in_press = was


def _flush(this):
    q, _queue[:] = list(_queue), []
    for _, down, button, p1 in q:
        _press(this, down, button, p1)


def enable(on=True, owner='pymodder'):
    """gd.click_between_frames(True) - experimental."""
    if on:
        if not _hooked[0]:
            _user[0] = ctypes.windll.user32
            _user[0].GetForegroundWindow.restype = ctypes.c_void_p
            _user[0].GetAsyncKeyState.restype = ctypes.c_short
            N.hook('GJBaseGameLayer::handleButton', _h_button, 'pymodder')
            N.hook('GJBaseGameLayer::update', _h_update, 'pymodder')
            _hooked[0] = True
        _on.add(owner)
        if _thread[0] is None:
            _thread[0] = threading.Thread(target=_poll, daemon=True, name='pymodder-cbf')
            _thread[0].start()
    else:
        _on.discard(owner)
        if not _on and _queue and K.state.layer:
            _flush(K.state.layer)


def enabled():
    return bool(_on)


K.cleanup_hooks.append(lambda owner: enable(False, owner))
