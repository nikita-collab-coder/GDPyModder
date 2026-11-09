"""Game speed (gd.speed). In a level GD sets the scheduler time scale itself every frame
(GJBaseGameLayer::applyTimeWarp: time scale = time warp * the level's "time speed"), so changing
CCScheduler's time scale there does nothing to the game. In a level / editor playtest we set GD's own
time speed (the one of the testmode speed slider) instead: the physics really slows down, the music
follows it, and GD counts the attempt as a speed-changed one (no progress is saved, like in testmode).
Outside levels: CCScheduler time scale + the pitch of FMOD's master channel group."""
import traceback

from . import _native as N
from . import _mem as M
from . import _cocos as C
from . import _audio as A
from . import _core

# GJBaseGameLayer / PlayLayer fields, checked in GD 2.2091:
#   warp     - m_timeWarp (argument of applyTimeWarp from update)
#   speed    - time speed (TimeSpeedControl::timeSliderChanged, multiplies the time scale)
#   audio    - audio speed (FMOD channel pitch set by applyTimeWarp)
#   modified - "speed was changed in this attempt" (levelComplete / destroyPlayer don't save progress)
#   started  - the level is running (applyTimeWarp only works then)
#   frozen   - paused / dead (applyTimeWarp uses the normal speed then)
OFFSETS = {'2.2091': dict(warp=0x330, speed=0x3560, audio=0x3564, modified=0x39fa, started=0x3358, frozen=0x8a6)}

_want = [1.0, True]     # speed, audio
_layer = [0]            # the game layer we have changed (PlayLayer / LevelEditorLayer)
_global = [False]       # we changed the scheduler time scale / master pitch outside levels


def _off():
    return OFFSETS.get(N.version or '')


def _editor_layer():
    sc = C.running_scene()
    if sc:
        for ch in C.children(sc):
            if M.class_name(ch) == 'LevelEditorLayer':
                return ch
    return 0


def _game_layer():
    st = _core.state
    if st.layer and st.started:
        return st.layer, True
    return _editor_layer(), False


def _no_global():
    if _global[0]:
        C.time_scale(1.0)
        A.speed(1.0)            # in a level GD sets the pitch of the music / sfx groups itself
        _global[0] = False


def _write(layer, play):
    o = _off()
    v, audio = _want
    slow = abs(v - 1.0) > 1e-6
    _no_global()
    M.write_f32(layer + o['speed'], v)
    M.write_f32(layer + o['audio'], v if audio else 1.0)
    _layer[0] = layer if slow else 0
    if play and slow:
        M.write_u8(layer + o['modified'], 1)
        try:
            N.function('PlayLayer::updateTestModeLabel')(layer)
        except Exception:
            traceback.print_exc()
    if M.u8(layer + o['started']):          # right now, not on the next frame
        try:
            N.function('GJBaseGameLayer::applyTimeWarp')(layer, M.f32(layer + o['warp'], 1.0) or 1.0)
        except Exception:
            traceback.print_exc()
        # applyTimeWarp skips the pitch when the time scale did not change (only "audio" changed)
        A.group_speed(1.0 if M.u8(layer + o['frozen']) else (v if audio else 1.0))
    elif not slow:
        A.group_speed(1.0)


def apply():
    """Put the wanted speed where it works on the current screen."""
    v, audio = _want
    layer, play = _game_layer()
    if layer and _off():
        _write(layer, play)
        return
    if abs(v - 1.0) > 1e-6 or _global[0]:
        C.time_scale(v)
        A.speed(v if audio else 1.0)
        _global[0] = abs(v - 1.0) > 1e-6


def speed(value=None, audio=True):
    if value is not None:
        _want[0], _want[1] = max(0.01, min(100.0, float(value))), bool(audio)
        try:
            apply()
        except Exception:
            traceback.print_exc()
    return _want[0]


def _left(*_):
    """The level / editor is closed: GD sets the time scale back to 1, the channel groups keep the pitch."""
    if _layer[0]:
        _layer[0] = 0
        A.group_speed(1.0)
    if abs(_want[0] - 1.0) > 1e-6:
        _core.when_scene_ready(apply)


def _h_play_init(orig, this, *args):
    ok = orig()
    if ok and abs(_want[0] - 1.0) > 1e-6 and _off():
        try:
            _write(this, True)
        except Exception:
            traceback.print_exc()
    return ok


def _h_editor_init(orig, this, *args):
    ok = orig()
    if ok and abs(_want[0] - 1.0) > 1e-6 and _off():
        try:
            _write(this, False)
        except Exception:
            traceback.print_exc()
    return ok


def _h_stop_playtest(orig, this, *args):
    r = orig()
    if _layer[0] == this:               # building in the editor - normal speed
        C.time_scale(1.0)
        A.group_speed(1.0)
    return r


def _h_editor_exit(orig, this, *args):
    was = _layer[0]
    r = orig()
    if was:
        _left()
    return r


def install():
    _core.leave_hooks.append(_left)
    hooks = [('PlayLayer::init', _h_play_init), ('LevelEditorLayer::init', _h_editor_init),
             ('LevelEditorLayer::onStopPlaytest', _h_stop_playtest)]
    hooks += [('EditorPauseLayer::' + n, _h_editor_exit) for n in ('onSaveAndExit', 'onExitNoSave', 'onSaveAndPlay')]
    for name, h in hooks:
        try:
            N.hook(name, h)
        except Exception as e:
            print('[PyModder] speed hook %s not installed: %s' % (name, e))
