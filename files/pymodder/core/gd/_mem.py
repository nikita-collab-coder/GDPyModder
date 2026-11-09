"""Low-level memory helpers (Windows x64). Safe reads never crash the game."""
import ctypes
import struct
from bisect import bisect_left
from ctypes import c_void_p, c_size_t, c_wchar_p, POINTER, byref

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.GetModuleHandleW.restype = c_void_p
k32.GetModuleHandleW.argtypes = [c_wchar_p]
k32.GetCurrentProcess.restype = c_void_p
k32.GetProcAddress.restype = c_void_p
k32.GetProcAddress.argtypes = [c_void_p, ctypes.c_char_p]
k32.ReadProcessMemory.argtypes = [c_void_p, c_void_p, c_void_p, c_size_t, POINTER(c_size_t)]
k32.ReadProcessMemory.restype = ctypes.c_int
k32.VirtualProtect.argtypes = [c_void_p, c_size_t, ctypes.c_ulong, POINTER(ctypes.c_ulong)]
k32.VirtualProtect.restype = ctypes.c_int
k32.GetCurrentThreadId.restype = ctypes.c_ulong
_proc = c_void_p(k32.GetCurrentProcess())


def read(addr, n):
    """Read n bytes; returns None if the memory is not readable."""
    if not addr or addr < 0x10000 or addr > 0x7FFFFFFFFFFF:
        return None
    buf = ctypes.create_string_buffer(n)
    got = c_size_t()
    if k32.ReadProcessMemory(_proc, c_void_p(addr), buf, n, byref(got)) and got.value == n:
        return buf.raw
    return None


def _unpack(fmt, size):
    def f(addr, default=None):
        b = read(addr, size)
        return struct.unpack('<' + fmt, b)[0] if b else default
    return f


ptr = _unpack('Q', 8)
u8 = _unpack('B', 1)
i32 = _unpack('i', 4)
u32 = _unpack('I', 4)
f32 = _unpack('f', 4)
f64 = _unpack('d', 8)


def boolean(addr):
    v = u8(addr)
    return None if v is None else bool(v)


def write(addr, data):
    """Write bytes (changes page protection if needed)."""
    old = ctypes.c_ulong()
    k32.VirtualProtect(c_void_p(addr), len(data), 0x40, byref(old))
    ctypes.memmove(addr, data, len(data))
    k32.VirtualProtect(c_void_p(addr), len(data), old.value, byref(old))


def write_f32(addr, v): write(addr, struct.pack('<f', v))
def write_i32(addr, v): write(addr, struct.pack('<i', v))
def write_u8(addr, v): write(addr, struct.pack('<B', v))


def cstr(addr, maxlen=256):
    out = b''
    while len(out) < maxlen:
        chunk = read(addr + len(out), 16)
        if chunk is None:
            break
        i = chunk.find(b'\0')
        if i >= 0:
            return (out + chunk[:i]).decode('utf-8', 'replace')
        out += chunk
    return None


def std_string(addr, maxlen=1 << 20):
    """Read an MSVC std::string (gd::string) located at addr. None if it is not a valid string."""
    b = read(addr, 32)
    if not b:
        return None
    size, cap = struct.unpack_from('<QQ', b, 16)
    if cap < 15 or size > cap or cap > maxlen:
        return None
    if cap == 15:
        data = b[:size]
        if b[size:size + 1] != b'\0':
            return None
    else:
        data = read(struct.unpack_from('<Q', b)[0], size + 1)
        if not data or data[size:] != b'\0':
            return None
        data = data[:size]
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return None


class Module:
    """A loaded PE module: base address, exports, function starts (from .pdata)."""

    def __init__(self, name=None):
        self.base = k32.GetModuleHandleW(name)
        if not self.base:
            raise OSError('module not loaded: %s' % name)
        b = self.base
        nt = b + struct.unpack('<I', ctypes.string_at(b + 0x3C, 4))[0]
        self.timestamp = struct.unpack('<I', ctypes.string_at(nt + 8, 4))[0]
        opt = nt + 24
        self.size = struct.unpack('<I', ctypes.string_at(opt + 56, 4))[0]
        dd = opt + 112
        self._exp = struct.unpack('<II', ctypes.string_at(dd, 8))
        self._exc = struct.unpack('<II', ctypes.string_at(dd + 24, 8))
        self._exports = None
        self._starts = None

    def contains(self, addr):
        return self.base <= addr < self.base + self.size

    @property
    def exports(self):
        if self._exports is None:
            rva, size = self._exp
            out = {}
            if rva:
                d = ctypes.string_at(self.base + rva, 40)
                nfun, nnames, afun, anames, aord = struct.unpack_from('<IIIII', d, 20)
                funcs = struct.unpack('<%dI' % nfun, ctypes.string_at(self.base + afun, 4 * nfun))
                names = struct.unpack('<%dI' % nnames, ctypes.string_at(self.base + anames, 4 * nnames))
                ords = struct.unpack('<%dH' % nnames, ctypes.string_at(self.base + aord, 2 * nnames))
                for n, o in zip(names, ords):
                    out[ctypes.string_at(self.base + n).decode('ascii', 'replace')] = self.base + funcs[o]
            self._exports = out
        return self._exports

    @property
    def function_starts(self):
        if self._starts is None:
            rva, size = self._exc
            blob = ctypes.string_at(self.base + rva, size) if rva else b''
            self._starts = sorted({s for s, _, _ in struct.iter_unpack('<III', blob[:size // 12 * 12])})
        return self._starts

    def is_function_start(self, addr):
        rva = addr - self.base
        s = self.function_starts
        i = bisect_left(s, rva)
        return i < len(s) and s[i] == rva


_vt_names = {}


def class_name(obj):
    """C++ class name of an object (from MSVC RTTI), e.g. 'PlayLayer'. None if unknown."""
    vt = ptr(obj)
    if not vt:
        return None
    if vt in _vt_names:
        return _vt_names[vt]
    name = None
    col = ptr(vt - 8)
    b = read(col, 24) if col else None
    if b:
        sig, _, _, td, _, self_rva = struct.unpack('<6I', b)
        if sig == 1:
            raw = cstr(col - self_rva + td + 16, 256)
            if raw and raw[:4] in ('.?AV', '.?AU'):
                parts = raw[4:].split('@@')[0].split('@')
                name = '::'.join(reversed(parts))
    _vt_names[vt] = name
    return name


def find_pointer_to(obj, cls, start=0, end=0x4000, skip=0):
    """Offset of the first (after `skip`) pointer field in obj that points to an object of class cls."""
    found = 0
    for off in range(start, end, 8):
        p = ptr(obj + off)
        if p and p > 0x10000 and class_name(p) == cls:
            if found == skip:
                return off
            found += 1
    return None


# ---------------------------------------------------------------- C++ heap, std::string, std::vector
# GD (and libcocos2d) use the shared C runtime (ucrtbase.dll) for operator new/delete, so memory
# from ucrtbase malloc can be freed by the game and the other way round.
_crt = None


def _ucrt():
    global _crt
    if _crt is None:
        _crt = ctypes.CDLL('ucrtbase')
        _crt.malloc.restype = c_void_p
        _crt.malloc.argtypes = [c_size_t]
        _crt.free.restype = None
        _crt.free.argtypes = [c_void_p]
    return _crt


def alloc(n):
    """Raw memory from the game's heap (free it with M.free, or let the game free it)."""
    p = _ucrt().malloc(max(1, n))
    if not p:
        raise MemoryError('malloc(%d) failed' % n)
    return p


def free(p):
    if p:
        _ucrt().free(c_void_p(p))


def std_alloc(n):
    """Like MSVC std::allocator<char>::allocate: blocks of 4096+ bytes are 32-byte aligned and the real
    pointer is stored just before them (the game checks this when it frees the block)."""
    if n < 4096:
        return alloc(n)
    raw = alloc(n + 0x27)
    p = (raw + 0x27) & ~0x1F
    ctypes.c_uint64.from_address(p - 8).value = raw
    return p


def std_free(p, n):
    if not p:
        return
    if n >= 4096:
        p = ctypes.c_uint64.from_address(p - 8).value
    free(p)


def write_std_string(addr, text):
    """Build an MSVC std::string at addr (32 bytes of memory that does not hold a live string).
    Long text goes to the game heap, so the game may free it later (by-value arguments, return values)."""
    data = text.encode('utf-8') if isinstance(text, str) else bytes(text)
    n = len(data)
    if n <= 15:
        buf = data + b'\0' * (16 - n)
        write_raw(addr, buf + struct.pack('<QQ', n, 15))
    else:
        p = std_alloc(n + 1)
        ctypes.memmove(p, data + b'\0', n + 1)
        write_raw(addr, struct.pack('<Q', p) + b'\0' * 8 + struct.pack('<QQ', n, n))
    return addr


def free_std_string(addr):
    """Destroy a std::string we own (frees heap text) and leave it empty."""
    b = read(addr, 32)
    if not b:
        return
    p, = struct.unpack_from('<Q', b)
    size, cap = struct.unpack_from('<QQ', b, 16)
    if cap > 15 and size <= cap:
        std_free(p, cap + 1)
    write_raw(addr, b'\0' * 16 + struct.pack('<QQ', 0, 15))


def write_raw(addr, data):
    ctypes.memmove(addr, data, len(data))


class StdString:
    """A temporary std::string for calling game functions:

        s = StdString("text")
        func(s.addr)       # std::string / const std::string& parameter
        s.free()           # always call it after (does nothing if the game already took the text)
    """

    def __init__(self, text=''):
        self.buf = ctypes.create_string_buffer(32)
        self.addr = ctypes.addressof(self.buf)
        write_std_string(self.addr, text)

    @property
    def value(self):
        return std_string(self.addr)

    def free(self):
        free_std_string(self.addr)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.free()


def returned_string(call, *args):
    """Call a function that returns std::string through a hidden pointer; returns a Python str.
    call(sret, *args) - e.g. returned_string(lambda r: f(this, r, 5))."""
    buf = ctypes.create_string_buffer(32)
    addr = ctypes.addressof(buf)
    write_raw(addr, b'\0' * 16 + struct.pack('<QQ', 0, 15))
    call(addr, *args)
    s = std_string(addr)
    free_std_string(addr)
    return s


def std_vector(addr, item_size=8):
    """(begin, count) of an MSVC std::vector located at addr."""
    b = read(addr, 24)
    if not b:
        return 0, 0
    first, last, _ = struct.unpack('<QQQ', b)
    if not first or last < first:
        return 0, 0
    return first, (last - first) // item_size


def string_vector(addr):
    """Read a std::vector<std::string> -> [str]."""
    first, n = std_vector(addr, 32)
    out = []
    for i in range(min(n, 10000)):
        s = std_string(first + 32 * i)
        out.append(s if s is not None else '')
    return out


class StringVector:
    """A std::vector<std::string> built in our memory, for const std::vector<std::string>& parameters.
    The strings point to Python buffers (the game only copies them)."""

    def __init__(self, items):
        items = [s.encode('utf-8') if isinstance(s, str) else bytes(s) for s in items]
        self._data = [ctypes.create_string_buffer(s + b'\0', len(s) + 1) for s in items]
        self._arr = ctypes.create_string_buffer(32 * max(1, len(items)))
        base = ctypes.addressof(self._arr)
        for i, (s, d) in enumerate(zip(items, self._data)):
            if len(s) <= 15:
                write_raw(base + 32 * i, s + b'\0' * (16 - len(s)) + struct.pack('<QQ', len(s), 15))
            else:
                write_raw(base + 32 * i, struct.pack('<QQQQ', ctypes.addressof(d), 0, len(s), len(s)))
        self._vec = ctypes.create_string_buffer(
            struct.pack('<QQQ', base, base + 32 * len(items), base + 32 * len(items)), 24)
        self.addr = ctypes.addressof(self._vec)


# ---------------------------------------------------------------- RTTI: base classes and their offsets
_bases_cache = {}


def bases(obj):
    """{class name: offset of that base inside the object} from MSVC RTTI (cached per vtable)."""
    vt = ptr(obj)
    if not vt:
        return {}
    got = _bases_cache.get(vt)
    if got is not None:
        return got
    out = {}
    col = ptr(vt - 8)
    b = read(col, 24) if col else None
    if b:
        sig, off, _, td, chd, self_rva = struct.unpack('<6I', b)
        if sig == 1:
            base = col - self_rva
            h = read(base + chd, 16)
            if h:
                _, _, nbases, arr = struct.unpack('<4I', h)
                rvas = read(base + arr, 4 * min(nbases, 64)) or b''
                for (bcd,) in struct.iter_unpack('<I', rvas):
                    d = read(base + bcd, 28)
                    if not d:
                        continue
                    btd, _, mdisp, pdisp, _, _, _ = struct.unpack('<IIiiiII', d)
                    raw = cstr(base + btd + 16, 256)
                    if not raw or raw[:4] not in ('.?AV', '.?AU') or pdisp != -1:
                        continue
                    parts = raw[4:].split('@@')[0].split('@')
                    out.setdefault('::'.join(reversed(parts)), mdisp - off)
    _bases_cache[vt] = out
    return out


def is_a(obj, cls):
    """Does the object derive from class cls (e.g. 'cocos2d::CCSprite' or 'GameObject')."""
    b = bases(obj)
    return cls in b or ('cocos2d::' + cls) in b
