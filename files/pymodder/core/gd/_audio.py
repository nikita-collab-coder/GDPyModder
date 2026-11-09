"""Game audio speed: the pitch of FMOD's master channel group (music + sound effects).
Used by gd.speed(..., audio=True) and gd.audio_speed()."""
import ctypes
from ctypes import c_void_p, c_float, c_int

from . import _native as N
from . import _mem as M

# FMODAudioEngine::sharedEngine() instance (a global in GeometryDash.exe) and FMODAudioEngine::m_system.
# Checked in GD 2.2091: the inlined sharedEngine() reads [rip -> 0x90bf60], setupAudioEngine() calls
# FMOD_System_Create(&this->m_system) with this + 0x230. The channel groups whose pitch
# GJBaseGameLayer::applyTimeWarp sets (music / sound effects): this + 0x228, 0x248, 0x250.
OFFSETS = {'2.2091': (0x90BF60, 0x230, (0x228, 0x248, 0x250))}
_f = {}
_speed = [1.0]


def _fmod():
    if 'ok' not in _f:
        _f['ok'] = False
        try:
            ex = M.Module('fmod.dll').exports
            get = (ex.get('?getMasterChannelGroup@System@FMOD@@QEAA?AW4FMOD_RESULT@@PEAPEAVChannelGroup@2@@Z')
                   or ex.get('FMOD_System_GetMasterChannelGroup'))
            setp = (ex.get('?setPitch@ChannelControl@FMOD@@QEAA?AW4FMOD_RESULT@@M@Z')
                    or ex.get('FMOD_ChannelGroup_SetPitch'))
            getp = (ex.get('?getPitch@ChannelControl@FMOD@@QEAA?AW4FMOD_RESULT@@PEAM@Z')
                    or ex.get('FMOD_ChannelGroup_GetPitch'))
            if get and setp:
                _f['master'] = ctypes.CFUNCTYPE(c_int, c_void_p, ctypes.POINTER(c_void_p))(get)
                _f['set'] = ctypes.CFUNCTYPE(c_int, c_void_p, c_float)(setp)
                if getp:
                    _f['get'] = ctypes.CFUNCTYPE(c_int, c_void_p, ctypes.POINTER(c_float))(getp)
                _f['ok'] = True
        except Exception as e:
            print('[PyModder] FMOD not available:', e)
    return _f['ok']


def engine():
    """FMODAudioEngine* (None if unknown for this GD version)."""
    off = OFFSETS.get(N.version or '')
    if not off or not N.gd_module:
        return None
    e = M.ptr(N.gd_module.base + off[0])
    if not e or 'FMODAudioEngine' not in (M.class_name(e) or ''):
        return None
    return e


def master_group():
    e = engine()
    if not e or not _fmod():
        return None
    system = M.ptr(e + OFFSETS[N.version][1])
    if not system:
        return None
    out = c_void_p()
    if _f['master'](system, ctypes.byref(out)) != 0:
        return None
    return out.value


def speed(value=None):
    """Audio speed (pitch): 1 = normal, 0.5 = half speed and an octave lower. Returns the current value."""
    if value is not None:
        value = max(0.01, min(10.0, float(value)))
        g = master_group()
        if g:
            _f['set'](g, value)
            _speed[0] = value
        elif abs(value - 1.0) > 1e-6:
            print('[PyModder] audio speed is not supported for GD %s' % N.version)
        return _speed[0]
    g = master_group()
    if g and 'get' in _f:
        out = c_float()
        if _f['get'](g, ctypes.byref(out)) == 0:
            _speed[0] = out.value
    return _speed[0]


def group_speed(value):
    """Pitch of the channel groups GD itself slows down in a level (applyTimeWarp)."""
    e = engine()
    if not e or not _fmod():
        return
    for off in OFFSETS[N.version][2]:
        g = M.ptr(e + off)
        if g:
            _f['set'](g, float(value))
