"""Hooks and calls of game functions (by binding name or address)."""
import ctypes
import json
import os
import re
import traceback
from ctypes import (c_void_p, c_bool, c_int, c_uint, c_float, c_double, c_byte, c_ubyte, c_short,
                    c_ushort, c_int64, c_uint64, POINTER, byref)

from . import _mem

ROOT = None
lib = None          # our loader DLL (XInput1_4.dll, opengl32.dll or version.dll)
loader_path = None
gd_module = None    # GeometryDash.exe
cocos = None        # libcocos2d.dll
bindings = {}
version = None
_keep = []          # keep ctypes callbacks alive
hooks = {}          # addr -> Hook

_PRIM = {
    'void': None, 'bool': c_bool, 'int': c_int, 'unsigned int': c_uint, 'unsigned': c_uint,
    'int32_t': c_int, 'uint32_t': c_uint, 'long': c_int, 'unsigned long': c_uint,
    'float': c_float, 'double': c_double, 'char': c_byte, 'signed char': c_byte,
    'unsigned char': c_ubyte, 'uint8_t': c_ubyte, 'int8_t': c_byte, 'short': c_short,
    'unsigned short': c_ushort, 'uint16_t': c_ushort, 'int16_t': c_short, 'long long': c_int64,
    'unsigned long long': c_uint64, 'int64_t': c_int64, 'uint64_t': c_uint64, 'size_t': c_uint64,
    'intptr_t': c_int64, 'uintptr_t': c_uint64, 'time_t': c_int64, 'GLubyte': c_ubyte,
    'GLuint': c_uint, 'GLint': c_int, 'GLenum': c_uint, 'GLfloat': c_float,
}
# small plain structs that MSVC x64 passes in a register (by value)
_REG8 = {'cocos2d::ccBlendFunc', 'ccBlendFunc'}
_REG4 = {'cocos2d::ccColor4B', 'ccColor4B'}
# CCPoint / CCSize have a copy constructor: by value they are passed as a pointer to a copy
# (checked: LevelEditorLayer::createObject copy-constructs its CCPoint from the pointer in r8)
_classes = set()


def ctype(t, ret=False):
    """C++ type string -> (ctypes type, kind). kind: 'val', 'ptr', 'obj' (object passed via pointer)."""
    t = re.sub(r'\bconst\b', '', t).replace('struct ', '').replace('enum ', '').strip()
    t = re.sub(r'\s+', ' ', t).replace(' *', '*').replace(' &', '&')
    if t.endswith('*') or t.endswith('&'):
        return c_void_p, 'ptr'
    if t in _PRIM:
        return _PRIM[t], 'val'
    if t in _REG8:
        return c_uint64, 'val'
    if t in ('CCPoint', 'CCSize', 'CCRect'):
        return c_void_p, 'obj'
    if t in _REG4:
        return c_uint, 'val'
    base = t.split('::')[-1]
    if '<' in t or t.startswith(('gd::', 'std::', 'geode::')) or t in _classes or t.startswith('cocos2d::') \
            or base in _classes or t in ('TodoReturn',):
        return c_void_p, 'obj'
    return c_int, 'val'   # enums


class Sig:
    """Prototype of a function: list of ctypes args (including this / hidden return pointer)."""

    def __init__(self, ret='void', params=(), static=False, name='?'):
        self.name = name
        self.static = static
        rt, rkind = ctype(ret, ret=True)
        self.sret = rkind == 'obj' and ret != 'TodoReturn'
        args = [] if static else [c_void_p]
        if self.sret:
            args.append(c_void_p)
            rt = c_void_p
        for p in params:
            args.append(ctype(p)[0])
        self.restype, self.argtypes = rt, args
        self.proto = ctypes.CFUNCTYPE(rt, *args)


def load(root):
    global ROOT, lib, gd_module, cocos, bindings, version
    ROOT = root
    lib = _find_loader(root)
    lib.pymodder_hook.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]
    lib.pymodder_hook.restype = c_int
    lib.pymodder_unhook.argtypes = [c_void_p]
    lib.pymodder_status.restype = ctypes.c_char_p
    gd_module = _mem.Module(None)
    cocos = _mem.Module('libcocos2d.dll')
    bdir = os.path.join(root, 'bindings')
    for fn in sorted(os.listdir(bdir)):
        path = os.path.join(bdir, fn)
        if fn.endswith('.json'):
            data = json.load(open(path, encoding='utf-8-sig'))
        elif fn.endswith('.bro'):
            from . import _bro
            funcs, classes = _bro.parse(open(path, encoding='utf-8').read())
            data = {'version': fn[:-4], 'timestamp': None, 'classes': classes, 'funcs': funcs}
        else:
            continue
        if data.get('timestamp') in (None, gd_module.timestamp):
            if data.get('timestamp') is None and not _looks_right(data['funcs']):
                continue
            bindings, version = data['funcs'], data['version']
            _classes.update(data['classes'])
            break
    return version


LOADER_NAMES = ('XInput1_4.dll', 'opengl32.dll', 'version.dll')


def _find_loader(root):
    """The PyModder loader DLL that started us (it is a proxy with one of several names)."""
    global loader_path
    cands = [os.environ.get('PYMODDER_LOADER')] + [os.path.join(os.path.dirname(root), n) for n in LOADER_NAMES]
    for path in cands:
        if not path:
            continue
        h = _mem.k32.GetModuleHandleW(path)
        if h and _mem.k32.GetProcAddress(c_void_p(h), b'pymodder_hook'):
            loader_path = path
            return ctypes.CDLL(path, handle=h)
    raise OSError('PyModder loader DLL not found (%s)' % ', '.join(LOADER_NAMES))


def _looks_right(funcs):
    sample = list(funcs.values())[:400]
    ok = sum(gd_module.is_function_start(gd_module.base + f[0]) for f in sample)
    return ok > len(sample) * 0.7


def resolve(name):
    """'PlayLayer::init' or address -> (absolute address, Sig or None)."""
    if isinstance(name, int):
        return name, None
    if '::' in name and name.split('::')[0] in ('cocos2d',):
        raise KeyError(name)
    f = bindings.get(name)
    if f is None:
        raise KeyError('no such function in bindings %s: %s' % (version, name))
    rva, ret, params, flags = f
    return gd_module.base + rva, Sig(ret, params, 's' in flags, name)


def function(name, restype=None, argtypes=None):
    """Callable for a game function: gd.raw.function('PlayLayer::getCurrentPercent')(playlayer)."""
    addr, sig = resolve(name)
    if argtypes is not None:
        return ctypes.CFUNCTYPE(restype, *argtypes)(addr)
    return sig.proto(addr)


class Hook:
    """One native hook per address; any number of Python handlers are chained on it."""

    def __init__(self, addr, sig):
        self.addr, self.sig = addr, sig
        self.handlers = []   # [(handler, owner)]
        self.original = None

        def detour(*args):
            hs = self.handlers
            if not hs:
                return self.original(*args)
            return self._run(0, hs, args)

        self._cb = sig.proto(detour)
        orig = c_void_p()
        rc = lib.pymodder_hook(c_void_p(addr), ctypes.cast(self._cb, c_void_p), byref(orig))
        if rc != 0:
            raise OSError('hook %s failed: %s' % (sig.name, lib.pymodder_status(rc).decode()))
        self.original = sig.proto(orig.value)
        _keep.append(self._cb)

    def _run(self, i, hs, args):
        if i >= len(hs):
            return self.original(*args)
        done = []

        def nxt(*a):
            r = self._run(i + 1, hs, a or args)
            done.append(r)
            return r
        try:
            r = hs[i][0](nxt, *args)
            if r is None and done:
                return done[0]
            return r
        except Exception:
            print('[PyModder] error in hook %s (%s):' % (self.sig.name, hs[i][1]))
            traceback.print_exc()
        return done[0] if done else self._run(i + 1, hs, args)


def _custom_sig(name, restype, argtypes):
    sig = Sig.__new__(Sig)
    sig.name, sig.restype, sig.argtypes, sig.sret, sig.static = name, restype, list(argtypes), False, False
    sig.proto = ctypes.CFUNCTYPE(restype, *argtypes)
    return sig


def hook(name, handler, owner='pymodder', restype=None, argtypes=None):
    """Add a handler(original, *args) to a game function. Call original() to run the game code."""
    if isinstance(name, str) and name.startswith('?'):
        addr = cocos.exports.get(name)
        if not addr:
            raise KeyError('not in libcocos2d.dll: ' + name)
        sig = _custom_sig(name, restype, argtypes or [])
    else:
        addr, sig = resolve(name)
        if argtypes is not None or sig is None:
            sig = _custom_sig(hex(addr), restype, argtypes or [])
        if not gd_module.is_function_start(addr):
            print('[PyModder] warning: %s (+0x%x) does not look like a function start' % (sig.name, addr - gd_module.base))
    h = hooks.get(addr)
    if h is None:
        h = hooks[addr] = Hook(addr, sig)
    h.handlers.append((handler, owner))
    return h


def ensure_hook(name):
    """The Hook object of a game function (installed if needed, no handler added)."""
    addr, sig = resolve(name)
    h = hooks.get(addr)
    if h is None:
        h = hooks[addr] = Hook(addr, sig)
    return h


def remove_owner(owner):
    for h in hooks.values():
        h.handlers[:] = [x for x in h.handlers if x[1] != owner]


def cocos_fn(mangled, restype, *argtypes):
    """Exported cocos2d function by its mangled name."""
    addr = cocos.exports.get(mangled)
    if not addr:
        raise KeyError('not in libcocos2d.dll: ' + mangled)
    return ctypes.CFUNCTYPE(restype, *argtypes)(addr)


