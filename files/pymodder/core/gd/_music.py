"""Music: replace level songs / the menu music with your files, play music, pick files in Windows."""
import ctypes
import os
import threading
from ctypes import c_void_p, c_bool

from . import _core as K
from . import _mem as M
from . import _native as N

OFF_ENGINE = 0x90bf60      # FMODAudioEngine singleton (2.2091)
_songs = {}                # custom song id -> [path, owner]
_official = {}             # official song index -> [path, owner]
_menu = []                 # [path, owner] (last wins)
_hooked = set()


def engine():
    p = M.ptr(N.gd_module.base + OFF_ENGINE) if N.version == '2.2091' else None
    if p and M.class_name(p) == 'FMODAudioEngine':
        return p
    raise RuntimeError('FMODAudioEngine not found')


def _h_path(orig, this, sret, song_id):
    ent = _songs.get(song_id)
    if ent:
        M.write_std_string(sret, ent[0])
        return sret
    return orig()


def _h_downloaded(orig, this, song_id):
    if song_id in _songs:
        return True
    return orig()


def _h_official(orig, sret, index):
    ent = _official.get(index)
    if ent:
        M.write_std_string(sret, ent[0])
        return sret
    return orig()


def _h_menu(orig, this, sret):
    if _menu:
        M.write_std_string(sret, _menu[-1][0])
        return sret
    return orig()


def _hook(name, h):
    if name not in _hooked:
        N.hook(name, h, 'pymodder')
        _hooked.add(name)


def _abs(path, owner):
    if not os.path.isabs(path):
        from . import _media as MD
        path = os.path.join(MD.mod_dir(owner), path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return os.path.abspath(path)


def replace_song(song_id, path, owner='pymodder'):
    """Levels with this Newgrounds song id play your file instead (also if the song is not downloaded)."""
    _hook('MusicDownloadManager::pathForSong', _h_path)
    _hook('MusicDownloadManager::isSongDownloaded', _h_downloaded)
    _songs[int(song_id)] = [_abs(path, owner), owner]


def replace_official(index, path, owner='pymodder'):
    """Replace a main level song (0 = Stereo Madness, 1 = Back On Track, ...)."""
    _hook('LevelTools::getAudioFileName', _h_official)
    _official[int(index)] = [_abs(path, owner), owner]


def set_menu_music(path, owner='pymodder'):
    """Your file as the main menu music (None = the original one)."""
    _hook('GameManager::getMenuMusicFile', _h_menu)
    _menu[:] = [m for m in _menu if m[1] != owner]
    if path:
        _menu.append([_abs(path, owner), owner])
    K.later(_restart_menu_music)


def _restart_menu_music():
    from . import _nodes as Nd
    lay = Nd.current_layer()
    if lay is not None and lay.cls == 'MenuLayer':
        gm = N.function('GameManager::sharedState')()
        N.function('GameManager::fadeInMenuMusic')(gm)


def restore(song_id=None, owner=None):
    for d in (_songs, _official):
        for k in [k for k, v in d.items() if (song_id is None or k == song_id) and (owner is None or v[1] == owner)]:
            del d[k]


def play(path, loop=True, fade=0.0, channel=0, owner='pymodder'):
    """Play a music file (mp3 / ogg / wav) through the game's audio engine."""
    p = _abs(path, owner)
    s = M.StdString(p)
    try:
        N.function('FMODAudioEngine::playMusic')(engine(), s.addr, bool(loop), float(fade), int(channel))
    finally:
        s.free()


def stop():
    N.function('FMODAudioEngine::stopAllMusic')(engine(), True)


def playing(channel=0):
    return bool(N.function('FMODAudioEngine::isMusicPlaying')(engine(), int(channel)))


def position(seconds=None, channel=0):
    """Music position in seconds (set it with position(12.5))."""
    if seconds is not None:
        N.function('FMODAudioEngine::setMusicTimeMS')(engine(), int(seconds * 1000), True, int(channel))
        return seconds
    return N.function('FMODAudioEngine::getMusicTimeMS')(engine(), int(channel)) / 1000.0


def length(channel=0):
    return N.function('FMODAudioEngine::getMusicLengthMS')(engine(), int(channel)) / 1000.0


def effect(path, owner='pymodder'):
    """Play a sound effect file through the game (respects the SFX volume)."""
    p = _abs(path, owner) if not os.path.isabs(path) or os.path.isfile(path) else path
    s = M.StdString(p)
    try:
        N.function('FMODAudioEngine::playEffect')(engine(), s.addr)
    finally:
        s.free()


def song_path(song_id):
    """Where the game keeps a downloaded Newgrounds song."""
    mdm = N.function('MusicDownloadManager::sharedState')()
    f = N.function('MusicDownloadManager::pathForSong')
    return M.returned_string(lambda r: f(mdm, r, int(song_id)))


def _forget(owner):
    restore(owner=owner)
    if any(m[1] == owner for m in _menu):
        _menu[:] = [m for m in _menu if m[1] != owner]


K.cleanup_hooks.append(_forget)


# ---------------------------------------------------------------- Windows file dialog
class _OFN(ctypes.Structure):
    _fields_ = [('lStructSize', ctypes.c_uint32), ('hwndOwner', c_void_p), ('hInstance', c_void_p),
                ('lpstrFilter', ctypes.c_wchar_p), ('lpstrCustomFilter', ctypes.c_wchar_p),
                ('nMaxCustFilter', ctypes.c_uint32), ('nFilterIndex', ctypes.c_uint32),
                ('lpstrFile', c_void_p), ('nMaxFile', ctypes.c_uint32), ('lpstrFileTitle', ctypes.c_wchar_p),
                ('nMaxFileTitle', ctypes.c_uint32), ('lpstrInitialDir', ctypes.c_wchar_p),
                ('lpstrTitle', ctypes.c_wchar_p), ('Flags', ctypes.c_uint32), ('nFileOffset', ctypes.c_uint16),
                ('nFileExtension', ctypes.c_uint16), ('lpstrDefExt', ctypes.c_wchar_p), ('lCustData', c_void_p),
                ('lpfnHook', c_void_p), ('lpTemplateName', ctypes.c_wchar_p), ('pvReserved', c_void_p),
                ('dwReserved', ctypes.c_uint32), ('FlagsEx', ctypes.c_uint32)]


FILTERS = {'audio': 'Audio (mp3, ogg, wav)\0*.mp3;*.ogg;*.wav;*.flac\0All files\0*.*\0',
           'image': 'Pictures (png, jpg, gif)\0*.png;*.jpg;*.jpeg;*.gif\0All files\0*.*\0',
           'any': 'All files\0*.*\0'}


def _dialog(kind, title, folder, save=False):
    try:
        ctypes.windll.ole32.CoInitializeEx(None, 2)
    except Exception:
        pass
    buf = ctypes.create_unicode_buffer(4096)
    ofn = _OFN()
    ofn.lStructSize = ctypes.sizeof(_OFN)
    ofn.lpstrFilter = FILTERS.get(kind, kind if '\0' in str(kind) else FILTERS['any']) + '\0'
    ofn.lpstrFile = ctypes.cast(buf, c_void_p)
    ofn.nMaxFile = 4096
    ofn.lpstrTitle = title
    ofn.lpstrInitialDir = folder
    ofn.Flags = 0x80000 | 0x8 | (0x2 if save else 0x1000 | 0x800)
    f = ctypes.windll.comdlg32.GetSaveFileNameW if save else ctypes.windll.comdlg32.GetOpenFileNameW
    ok = f(ctypes.byref(ofn))
    return buf.value if ok else None


def pick_file(on_done, kind='any', title='Choose a file', folder=None, save=False, owner='pymodder'):
    """Windows "Open file" dialog (does not freeze the game). on_done(path or None)."""
    from . import _ui as U

    def run():
        try:
            path = _dialog(kind, title, folder, save)
        except Exception as e:
            print('[PyModder] file dialog failed:', e)
            path = None
        K.later(lambda: U.flex_call(owner, on_done, path))
    threading.Thread(target=run, daemon=True, name='pymodder-dialog').start()
