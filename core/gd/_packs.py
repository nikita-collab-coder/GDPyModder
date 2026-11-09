"""Texture packs: folders with GD resource files (same names as in Geometry Dash/Resources) that are used
instead of the original files. Folder: Geometry Dash/pymodder/packs/<name>/"""
import os

from . import _core as K
from . import _mem as M
from . import _native as N

_orig = [None]       # the game's search paths before any pack
_active = []         # pack folders (absolute), first = highest priority


def packs_dir():
    d = os.path.join(K.ROOT or '.', 'packs')
    os.makedirs(d, exist_ok=True)
    return d


def available():
    """Names of the folders in pymodder/packs."""
    d = packs_dir()
    return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))


def _fu():
    from ctypes import c_void_p
    return N.cocos_fn('?sharedFileUtils@CCFileUtils@cocos2d@@SAPEAV12@XZ', c_void_p)()


def search_paths():
    """The folders where the game looks for files (first = highest priority)."""
    from ctypes import c_void_p
    get = _export_like('?getSearchPaths@CCFileUtils@', c_void_p, c_void_p)
    return M.string_vector(get(_fu()))


def _export_like(prefix, restype, *argtypes):
    from ctypes import CFUNCTYPE
    for name, addr in N.cocos.exports.items():
        if name.startswith(prefix):
            return CFUNCTYPE(restype, *argtypes)(addr)
    raise KeyError('not in libcocos2d.dll: ' + prefix)


def set_search_paths(paths):
    from ctypes import c_void_p
    fu = _fu()
    vec = M.StringVector(paths)
    _export_like('?setSearchPaths@CCFileUtils@', None, c_void_p, c_void_p)(fu, vec.addr)
    _export_like('?purgeCachedEntries@CCFileUtils@', None, c_void_p)(fu)


def _folder(p):
    if not os.path.isabs(p):
        p = os.path.join(packs_dir(), p)
    p = os.path.abspath(p)
    if not os.path.isdir(p):
        raise FileNotFoundError('no pack folder: ' + p)
    return p.replace('\\', '/').rstrip('/') + '/'


def apply(packs, reload=True):
    """Use these packs (names in pymodder/packs or full paths; first = highest priority).
    apply([]) goes back to the original textures. reload=True reloads the textures (like GD does after
    changing the graphics settings)."""
    if _orig[0] is None:
        _orig[0] = [p for p in search_paths()]
    folders = [_folder(p) for p in packs]
    _active[:] = folders
    set_search_paths(folders + [p for p in _orig[0] if p not in folders])
    if reload:
        K.later(reload_textures)


def active():
    """Names / paths of the packs in use."""
    d = packs_dir().replace('\\', '/').rstrip('/') + '/'
    return [f[len(d):].rstrip('/') if f.startswith(d) else f for f in _active]


def reload_textures():
    """Reload all textures and go back to the menu (GameManager::reloadAll)."""
    gm = N.function('GameManager::sharedState')()
    N.function('GameManager::reloadAll')(gm, False, False, False, False, False)


def file_in_packs(name):
    """Which pack provides a file (e.g. "GJ_GameSheet03-uhd.png"), or None."""
    for f in _active:
        if os.path.isfile(os.path.join(f, name)):
            return f
    return None
