"""Level info (GJGameLevel fields), the player's icons and colors, icon sprites (SimplePlayer)."""
import base64
import ctypes
import struct
import zlib

from . import _cocos as C
from . import _mem as M
from . import _native as N

# GJGameLevel fields in 2.2091 (from GJGameLevel::encodeWithCoder). kind: str, i32, bool, rsv
# rsv = SeedValueRSV {rand, seed, value}: value = rand - seed ("rsv_r": the two ints are swapped)
FIELDS = {
    'id': ('rsv', 0x148), 'name': ('str', 0x158), 'description_raw': ('str', 0x178),
    'level_string_raw': ('str', 0x198), 'creator': ('str', 0x1b8), 'record_string': ('str', 0x1d8),
    'upload_date': ('str', 0x1f8), 'update_date': ('str', 0x218),
    'user_id': ('rsv', 0x288), 'account_id': ('rsv', 0x294), 'difficulty_raw': ('i32', 0x2a0),
    'official_song': ('i32', 0x2a4), 'song_id': ('i32', 0x2a8), 'revision': ('i32', 0x2ac),
    'unlisted': ('bool', 0x2b0), 'object_count': ('rsv', 0x2b4), 'ratings': ('i32', 0x2c4),
    'ratings_sum': ('i32', 0x2c8), 'downloads': ('i32', 0x2cc), 'editable': ('bool', 0x2d0),
    'gauntlet': ('bool', 0x2d1), 'edit_time': ('i32', 0x2d4), 'low_detail': ('bool', 0x348),
    'verified': ('rsv', 0x350), 'uploaded': ('bool', 0x359), 'level_version': ('i32', 0x35c),
    'game_version': ('i32', 0x360), 'attempts': ('rsv', 0x364), 'jumps': ('rsv', 0x370),
    'clicks': ('rsv', 0x37c), 'attempt_time': ('rsv', 0x388), 'normal_percent': ('rsv_r', 0x3a0),
    'orbs_percent': ('rsv', 0x3a8), 'practice_percent': ('i32', 0x3c0), 'likes': ('i32', 0x3c4),
    'dislikes': ('i32', 0x3c8), 'length_raw': ('i32', 0x3cc), 'featured': ('i32', 0x3d0),
    'epic_raw': ('i32', 0x3d4), 'favorite': ('bool', 0x3d8), 'folder': ('i32', 0x3dc),
    'daily_id': ('rsv', 0x3e0), 'is_demon': ('rsv', 0x3ec), 'demon_type': ('i32', 0x3f8),
    'stars': ('rsv', 0x3fc), 'is_auto': ('bool', 0x408), 'coins': ('i32', 0x40c),
    'coins_verified': ('rsv', 0x410), 'password': ('rsv', 0x41c), 'original_id': ('rsv', 0x424),
    'two_player': ('bool', 0x430), 'requested_stars': ('i32', 0x45c), 'level_type': ('i32', 0x4c4),
}
DIFFICULTIES = ['N/A', 'Easy', 'Normal', 'Hard', 'Harder', 'Insane']
DEMONS = {3: 'Easy Demon', 4: 'Medium Demon', 0: 'Hard Demon', 5: 'Insane Demon', 6: 'Extreme Demon'}
LENGTHS = ['Tiny', 'Short', 'Medium', 'Long', 'XL', 'Platformer']
# face sprite frames for the difficulty names
DIFF_FRAMES = {'N/A': 'difficulty_00_btn_001.png', 'Auto': 'difficulty_auto_btn_001.png',
               'Easy': 'difficulty_01_btn_001.png', 'Normal': 'difficulty_02_btn_001.png',
               'Hard': 'difficulty_03_btn_001.png', 'Harder': 'difficulty_04_btn_001.png',
               'Insane': 'difficulty_05_btn_001.png', 'Hard Demon': 'difficulty_06_btn_001.png',
               'Easy Demon': 'difficulty_07_btn_001.png', 'Medium Demon': 'difficulty_08_btn_001.png',
               'Insane Demon': 'difficulty_09_btn_001.png', 'Extreme Demon': 'difficulty_10_btn_001.png'}


def _read(ptr, kind, off):
    a = ptr + off
    if kind == 'str':
        return M.std_string(a)
    if kind == 'i32':
        return M.i32(a)
    if kind == 'bool':
        return M.boolean(a)
    if kind == 'rsv':
        r, s = M.i32(a), M.i32(a + 4)
        return None if r is None or s is None else r - s
    if kind == 'rsv_r':
        s, r = M.i32(a), M.i32(a + 4)
        return None if r is None or s is None else r - s
    raise ValueError(kind)


def decode_level_string(raw):
    """GD level data (base64 + gzip, "H4sI...") -> the plain object string."""
    if not raw:
        return ''
    s = raw.strip()
    if not s.startswith(('H4sI', 'eJ')):
        return s
    data = base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))
    return zlib.decompress(data, 15 | 32).decode('utf-8', 'replace')


def encode_level_string(text):
    co = zlib.compressobj(9, zlib.DEFLATED, 31)
    data = co.compress(text.encode('utf-8')) + co.flush()
    return base64.urlsafe_b64encode(data).decode()


def parse_objects(level_string):
    """Plain level string -> (header dict, [object dicts]); keys are strings ("1" = object id, "2" = x...)."""
    parts = [p for p in level_string.split(';') if p]
    if not parts:
        return {}, []

    def kv(s):
        a = s.split(',')
        return {a[i]: a[i + 1] for i in range(0, len(a) - 1, 2)}
    return kv(parts[0]), [kv(p) for p in parts[1:]]


def decode_b64(s):
    if not s:
        return ''
    try:
        return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'replace')
    except Exception:
        return s


class LevelData:
    """A GJGameLevel (any level: online, saved, the one being played). Read-only fields:
    id, name, creator, description, stars, difficulty, likes, downloads, length, coins, song_id, ..."""

    def __init__(self, ptr):
        self.ptr = int(ptr or 0)

    def __eq__(self, o):
        return isinstance(o, LevelData) and o.ptr == self.ptr

    def __hash__(self):
        return hash(self.ptr)

    @property
    def valid(self):
        """Do the known field offsets fit this game version (checks the id field)."""
        if not self.ptr or M.class_name(self.ptr) != 'GJGameLevel':
            return False
        r, s, v = M.i32(self.ptr + 0x148), M.i32(self.ptr + 0x14c), M.i32(self.ptr + 0x150)
        return r is not None and r - s == v and M.std_string(self.ptr + 0x158) is not None

    def __getattr__(self, name):
        f = FIELDS.get(name)
        if f is None:
            raise AttributeError(name)
        return _read(self.ptr, f[0], f[1])

    def get(self, name, default=None):
        v = getattr(self, name)
        return default if v is None else v

    @property
    def description(self):
        return decode_b64(self.description_raw or '')

    @property
    def level_string(self):
        """The decoded object string (empty until the level is downloaded)."""
        try:
            return decode_level_string(self.level_string_raw or '')
        except Exception:
            return ''

    def objects(self):
        """[dict] of every object in the level data ("1": id, "2": x, "3": y...)."""
        return parse_objects(self.level_string)[1]

    @property
    def demon(self):
        return bool(self.is_demon)

    @property
    def auto(self):
        return bool(self.is_auto)

    @property
    def difficulty(self):
        """'Auto', 'Easy' ... 'Insane', 'Easy Demon' ... 'Extreme Demon' or 'N/A'."""
        if self.is_auto:
            return 'Auto'
        if self.is_demon:
            return DEMONS.get(self.demon_type, 'Hard Demon')
        n, s = self.ratings or 0, self.ratings_sum or 0
        d = s // n if n > 0 else (self.difficulty_raw or 0)
        return DIFFICULTIES[d] if 0 <= d < len(DIFFICULTIES) else 'N/A'

    @property
    def difficulty_frame(self):
        return DIFF_FRAMES.get(self.difficulty, DIFF_FRAMES['N/A'])

    @property
    def length(self):
        v = self.length_raw or 0
        return LENGTHS[v] if 0 <= v < len(LENGTHS) else '?'

    @property
    def platformer(self):
        return self.length_raw == 5

    @property
    def rating(self):
        """'mythic', 'legendary', 'epic', 'featured', 'rated' or 'unrated'."""
        e = self.epic_raw or 0
        if e >= 3:
            return 'mythic'
        if e == 2:
            return 'legendary'
        if e == 1:
            return 'epic'
        if (self.featured or 0) > 0:
            return 'featured'
        return 'rated' if (self.stars or 0) > 0 else 'unrated'

    @property
    def official(self):
        return self.level_type == 1

    @property
    def song(self):
        """Custom song id (Newgrounds), or None for an official song."""
        return self.song_id or None

    def info(self):
        """A dict with the most useful fields (for printing / saving)."""
        keys = ['id', 'name', 'creator', 'description', 'difficulty', 'stars', 'length', 'rating', 'likes',
                'dislikes', 'downloads', 'coins', 'coins_verified', 'song_id', 'official_song', 'object_count',
                'game_version', 'level_version', 'attempts', 'jumps', 'clicks', 'normal_percent',
                'practice_percent', 'account_id', 'user_id', 'original_id', 'two_player', 'upload_date',
                'update_date', 'password', 'requested_stars', 'edit_time', 'daily_id', 'featured']
        out = {}
        for k in keys:
            try:
                out[k] = getattr(self, k)
            except Exception:
                out[k] = None
        return out

    def __repr__(self):
        return '<LevelData %r id=%s by %s>' % (self.name, self.id, self.creator)


# ---------------------------------------------------------------- the player's icons (GameManager)
ICON_FIELDS = {'cube': 0x2ec, 'ship': 0x2f8, 'ball': 0x304, 'ufo': 0x310, 'wave': 0x31c, 'robot': 0x328,
               'spider': 0x334, 'swing': 0x340, 'color1': 0x34c, 'color2': 0x358, 'glow_color': 0x364,
               'trail': 0x370, 'ship_fire': 0x37c, 'death': 0x388, 'jetpack': 0x394}
OFF_GLOW = 0x3b0
ICON_TYPES = {'cube': 0, 'ship': 1, 'ball': 2, 'ufo': 3, 'wave': 4, 'robot': 5, 'spider': 6, 'swing': 7,
              'jetpack': 8, 'death': 98, 'trail': 99, 'ship_fire': 101}


def game_manager():
    return N.function('GameManager::sharedState')()


def _rsv_ok(a):
    r, s, v = M.i32(a), M.i32(a + 4), M.i32(a + 8)
    return r is not None and r - s == v


def my_icons():
    """The player's icons: {'cube': 12, 'ship': 3, ..., 'color1': 0, 'color2': 3, 'glow': True, ...}."""
    gm = game_manager()
    out = {}
    for k, off in ICON_FIELDS.items():
        out[k] = _read(gm, 'rsv', off) if _rsv_ok(gm + off) else M.i32(gm + off + 8)
    out['glow'] = bool(M.u8(gm + OFF_GLOW, 0))
    return out


def set_icons(**icons):
    """Change the player's icons / colors: gd.set_icons(cube=35, color1=12, glow=True).
    The game uses them for the next level / garage visit."""
    gm = game_manager()
    for k, v in icons.items():
        if k == 'glow':
            M.write_u8(gm + OFF_GLOW, 1 if v else 0)
            continue
        off = ICON_FIELDS.get(k)
        if off is None:
            raise KeyError('unknown icon field %r (%s, glow)' % (k, ', '.join(ICON_FIELDS)))
        a = gm + off
        seed = M.i32(a + 4) or 0
        M.write(a, struct.pack('<iii', int(v) + seed, seed, int(v)))


def color(index):
    """RGB of a GD player color index (0..106): gd.color(12)."""
    buf = ctypes.create_string_buffer(8)
    p = N.function('GameManager::colorForIdx')(game_manager(), buf, int(index))
    return tuple((ctypes.string_at(p, 3) if p else buf.raw[:3]))


# ---------------------------------------------------------------- icon sprite (SimplePlayer)
SP_FIRST, SP_SECOND, SP_OUTLINE, SP_HAS_GLOW, SP_CUSTOM_GLOW = 0x258, 0x260, 0x270, 0x294, 0x29c


def _icon_type(kind):
    if isinstance(kind, int):
        return kind
    t = ICON_TYPES.get(str(kind).lower())
    if t is None or t > 8:
        raise KeyError('icon kind: cube, ship, ball, ufo, wave, robot, spider, swing, jetpack')
    return t


class PlayerIcon:
    """A GD player icon (any gamemode, colors, glow) as a node. gd.PlayerIcon(kind="ship", icon=5)
    .node is a gd.Node you can add anywhere: layer.add(icon.node)."""

    def __init__(self, icon=1, kind='cube', color1=None, color2=None, glow=None, mine=False):
        from . import _nodes as Nd
        if mine:
            me = my_icons()
            kind = kind or 'cube'
            icon = me.get(kind, icon) if isinstance(kind, str) else icon
            color1 = me['color1'] if color1 is None else color1
            color2 = me['color2'] if color2 is None else color2
            if glow is None:
                glow = me['glow_color'] if me['glow'] else False
        p = N.function('SimplePlayer::create')(1)
        if not p:
            raise RuntimeError('SimplePlayer::create failed')
        self.node = Nd.Node(p)
        self.ptr = p
        self.set(icon, kind)
        self.set_colors(0 if color1 is None else color1, 3 if color2 is None else color2, glow)

    def set(self, icon, kind='cube'):
        N.function('SimplePlayer::updatePlayerFrame')(self.ptr, int(icon), _icon_type(kind))
        return self

    def set_colors(self, color1=None, color2=None, glow=None):
        """Colors: GD color index or (r, g, b). glow: False / True (= color2) / index / (r, g, b)."""
        def rgb(c):
            return color(c) if isinstance(c, int) else tuple(c)[:3]
        if color1 is not None:
            N.function('SimplePlayer::setColor')(self.ptr + 0x140, C.color3(rgb(color1)))
        if color2 is not None:
            spr = M.ptr(self.ptr + SP_SECOND)
            if spr:
                from . import _nodes as Nd
                Nd.vcall(spr, 'setColor', C.color3(rgb(color2)))
        if glow is not None:
            on = glow is not False and glow is not None
            M.write_u8(self.ptr + SP_HAS_GLOW, 1 if on else 0)
            if on and glow is not True:
                M.write(self.ptr + SP_CUSTOM_GLOW, bytes((1,) + rgb(glow)))
            else:
                M.write_u8(self.ptr + SP_CUSTOM_GLOW, 0)
        N.function('SimplePlayer::updateColors')(self.ptr)
        return self

    def mine(self, kind='cube'):
        """Show the player's own icon of this gamemode with their colors."""
        me = my_icons()
        self.set(me.get(kind, 1), kind)
        return self.set_colors(me['color1'], me['color2'], me['glow_color'] if me['glow'] else False)
