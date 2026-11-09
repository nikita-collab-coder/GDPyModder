"""Native plugins: a mod can ship its own C/C++ .dll (see pymodder/sdk/pymodder.h).

The DLL gets a table of PyModder functions (log, hooks, addresses of game functions, run on the game
thread, events to Python) through its exported `pymodder_init(const PyModderAPI*)`.
Python calls the DLL's exported functions with ctypes.
"""
import ctypes
import json
import os
import shutil
import traceback
from ctypes import (c_void_p, c_char_p, c_int, c_float, CFUNCTYPE, POINTER, Structure, byref,
                    create_string_buffer)

from . import _core as K
from . import _native as N

API_VERSION = 1

LOG = CFUNCTYPE(None, c_char_p)
NOTIFY = CFUNCTYPE(None, c_char_p, c_float)
ADDRESS = CFUNCTYPE(c_void_p, c_char_p)
HOOK = CFUNCTYPE(c_int, c_void_p, c_void_p, POINTER(c_void_p))
UNHOOK = CFUNCTYPE(c_int, c_void_p)
LATER_FN = CFUNCTYPE(None, c_void_p)
LATER = CFUNCTYPE(None, c_void_p, c_void_p)
EMIT = CFUNCTYPE(None, c_char_p, c_char_p)
CALL = CFUNCTYPE(c_void_p, c_char_p, c_char_p)


class API(Structure):
    _fields_ = [('version', c_int), ('size', c_int),
                ('gd_base', c_void_p), ('cocos_base', c_void_p),
                ('mod_dir', c_char_p), ('mod_name', c_char_p),
                ('log', LOG), ('notify', NOTIFY), ('address', ADDRESS),
                ('hook', HOOK), ('unhook', UNHOOK), ('hook_raw', HOOK),
                ('later', LATER), ('emit', EMIT), ('call', CALL)]


MH_ERROR_ALREADY_CREATED, MH_ERROR_NOT_CREATED = 9, 10
libs = {}            # owner -> [NativeLib]
_rva_names = {}      # rva -> binding name (for hooks by address)
_counter = [0]


def _name_of(addr):
    if not _rva_names:
        for name, f in N.bindings.items():
            _rva_names.setdefault(f[0], name)
    return _rva_names.get(addr - N.gd_module.base)


def _cache_dir():
    d = os.path.join(K.ROOT, 'cache', 'native')
    os.makedirs(d, exist_ok=True)
    return d


def clean_cache():
    d = os.path.join(K.ROOT, 'cache', 'native')
    if os.path.isdir(d):
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
            except OSError:
                pass                # still loaded


class NativeLib:
    """A loaded native plugin.

        lib = gd.load_dll("mymod.dll")
        add = lib.func("add", ctypes.c_int, ctypes.c_int, ctypes.c_int)
        add(2, 3)
        lib.jump_count()                   # any export, ctypes defaults (int result)

        @lib.on("jump")                     # api->emit("jump", "...") from C++
        def jumped(data): ...

        lib.expose("best", lambda arg: str(best))   # api->call("best", "") from C++ -> "87"
    """

    def __init__(self, owner, path):
        if not os.path.isfile(path):
            raise FileNotFoundError('no such file: %s' % path)
        self.owner, self.path = owner, os.path.abspath(path)
        self.name = os.path.basename(path)
        self._events, self._exposed = {}, {}
        self._raw_hooks = []           # targets hooked directly with MinHook
        self._keep = []
        self._ret = create_string_buffer(1)
        _counter[0] += 1
        # load a copy: the original file stays unlocked, you can rebuild it while the game runs (F5 reloads)
        copy = os.path.join(_cache_dir(), '%s_%d_%s' % (K.mod_name(owner), _counter[0], self.name))
        shutil.copyfile(self.path, copy)
        self.copy = copy
        self.dll = ctypes.CDLL(copy)
        self.handle = self.dll._handle
        self.api = self._make_api()
        init = self._export('pymodder_init')
        if init:
            init.restype, init.argtypes = c_int, [POINTER(API)]
            rc = init(byref(self.api))
            if rc:
                self.unload()
                raise RuntimeError('%s: pymodder_init returned %d' % (self.name, rc))
        libs.setdefault(owner, []).append(self)

    def _export(self, name):
        try:
            return getattr(self.dll, name)
        except AttributeError:
            return None

    # ------------------------------------------------ calls from Python
    def func(self, name, restype=c_int, *argtypes):
        """An exported function with its C types: lib.func("add", c_int, c_int, c_int)."""
        f = getattr(self.dll, name)
        f.restype = restype
        f.argtypes = list(argtypes)
        return f

    def __getattr__(self, name):
        if name.startswith('_') or name in ('dll',):
            raise AttributeError(name)
        return getattr(self.dll, name)

    def on(self, event):
        """Decorator: func(data: str) for api->emit(event, data) from the DLL."""
        def decorator(func):
            self._events.setdefault(event, []).append(func)
            return func
        return decorator

    def expose(self, name, func):
        """Make a Python function callable from the DLL: api->call(name, arg) -> str(func(arg))."""
        self._exposed[name] = func
        return func

    # ------------------------------------------------ the API table
    def _make_api(self):
        owner = self.owner
        tag = '[%s/%s]' % (K.mod_name(owner), self.name)

        def log(text):
            print(tag, (text or b'').decode('utf-8', 'replace'))

        def notify(text, seconds):
            t = (text or b'').decode('utf-8', 'replace')
            K.later(lambda: K.notify(t, seconds or 2.5))

        def address(name):
            try:
                n = (name or b'').decode()
                if n.startswith('?'):
                    return N.cocos.exports.get(n) or 0
                if '::' in n and n in N.bindings:
                    return N.resolve(n)[0]
                return N.cocos.exports.get(n) or 0
            except Exception:
                return 0

        def hook(target, detour, original):
            """Chained through PyModder (works together with Python hooks on the same function)."""
            try:
                if not target or not detour:
                    return 1
                name = _name_of(target)
                if target not in N.hooks and not name:
                    return hook_raw(target, detour, original)
                h = N.hooks.get(target) or N.ensure_hook(name)
                sig = h.sig
                cdet = sig.proto(detour)
                chain = []

                def handler(nxt, *args):
                    chain.append(nxt)
                    try:
                        return cdet(*args)
                    finally:
                        chain.pop()

                def call_next(*args):
                    return chain[-1](*args) if chain else h.original(*args)
                nxt_cb = sig.proto(call_next)
                self._keep += [cdet, nxt_cb, handler]
                handler.native_target = target
                h.handlers.append((handler, owner))
                original[0] = ctypes.cast(nxt_cb, c_void_p).value
                return 0
            except Exception:
                traceback.print_exc()
                return 1

        def hook_raw(target, detour, original):
            """Straight MinHook: fastest, but fails if the function is already hooked."""
            if target in N.hooks:
                return MH_ERROR_ALREADY_CREATED
            out = c_void_p()
            rc = N.lib.pymodder_hook(c_void_p(target), c_void_p(detour), byref(out))
            if rc == 0:
                self._raw_hooks.append(target)
                original[0] = out.value
            return rc

        def unhook(target):
            if target in self._raw_hooks:
                self._raw_hooks.remove(target)
                return N.lib.pymodder_unhook(c_void_p(target))
            h = N.hooks.get(target)
            if h:
                before = len(h.handlers)
                h.handlers[:] = [x for x in h.handlers if getattr(x[0], 'native_target', None) != target
                                 or x[1] != owner]
                return 0 if len(h.handlers) != before else MH_ERROR_NOT_CREATED
            return MH_ERROR_NOT_CREATED

        def later(fn, arg):
            f = LATER_FN(fn)
            self._keep.append(f)

            def run():
                try:
                    f(arg)
                finally:
                    if f in self._keep:
                        self._keep.remove(f)
            K.later(run)

        def emit(event, data):
            ev = (event or b'').decode('utf-8', 'replace')
            d = (data or b'').decode('utf-8', 'replace')
            for f in list(self._events.get(ev, ())):
                try:
                    f(d)
                except Exception:
                    K.report(owner, 'native event ' + ev)

        def call(name, arg):
            try:
                f = self._exposed.get((name or b'').decode())
                if f is None:
                    return None
                r = f((arg or b'').decode('utf-8', 'replace'))
                if not isinstance(r, str):
                    r = json.dumps(r) if r is not None else ''
            except Exception:
                K.report(owner, 'native call')
                return None
            self._ret = create_string_buffer(r.encode('utf-8'))
            return ctypes.addressof(self._ret)

        cbs = [LOG(log), NOTIFY(notify), ADDRESS(address), HOOK(hook), UNHOOK(unhook), HOOK(hook_raw),
               LATER(later), EMIT(emit), CALL(call)]
        self._keep += cbs
        self._mod_dir = os.path.dirname(self.path).encode('utf-8')
        self._mod_name = K.mod_name(owner).encode('utf-8')
        cocos_base = N.cocos.base if N.cocos else 0
        return API(API_VERSION, ctypes.sizeof(API), N.gd_module.base, cocos_base, self._mod_dir, self._mod_name,
                   *cbs)

    # ------------------------------------------------ unload
    def unload(self):
        if not self.dll:
            return
        f = self._export('pymodder_unload')
        if f:
            try:
                f.restype, f.argtypes = None, []
                f()
            except Exception:
                traceback.print_exc()
        for t in list(self._raw_hooks):
            N.lib.pymodder_unhook(c_void_p(t))
        self._raw_hooks = []
        for h in N.hooks.values():
            h.handlers[:] = [x for x in h.handlers if not (getattr(x[0], 'native_target', None) and x[1] == self.owner)]
        try:
            ctypes.windll.kernel32.FreeLibrary(c_void_p(self.handle))
        except Exception:
            pass
        self.dll = None
        try:
            os.remove(self.copy)
        except OSError:
            pass


def load(owner, path):
    return NativeLib(owner, path)


def _unload_owner(owner):
    for lib in libs.pop(owner, []):
        try:
            lib.unload()
        except Exception:
            traceback.print_exc()


K.cleanup_hooks.append(_unload_owner)
