"""gd.Node - any cocos2d node of the game (layers, menus, buttons, sprites, labels):
properties, search, node IDs, buttons and "layer opened" events. Everything runs on the game thread."""
import ctypes
import re
import struct
import sys
import os
import traceback
from ctypes import c_void_p, c_float, c_int, c_uint, c_bool, c_ubyte, c_char_p

from . import _cocos as C
from . import _core as K
from . import _mem as M
from . import _native as N

# ---------------------------------------------------------------- virtual calls
# name -> (vtable slot, restype, argtypes after `this`, mangled name of the CCNode version)
# Slots were read from libcocos2d.dll 2.2091 and are checked at runtime against ??_7CCNode@cocos2d@@6B@.
_CN = '@CCNode@cocos2d@@'
_V = {
    'getTag': (7, c_int, (), '?getTag@CCObject@cocos2d@@UEBAHXZ'),
    'setTag': (8, None, (c_int,), '?setTag@CCObject@cocos2d@@UEAAXH@Z'),
    'setZOrder': (10, None, (c_int,), '?setZOrder' + _CN + 'UEAAXH@Z'),
    'getZOrder': (12, c_int, (), '?getZOrder' + _CN + 'UEAAHXZ'),
    'setScaleX': (15, None, (c_float,), '?setScaleX' + _CN + 'UEAAXM@Z'),
    'getScaleX': (16, c_float, (), '?getScaleX' + _CN + 'UEAAMXZ'),
    'setScaleY': (17, None, (c_float,), '?setScaleY' + _CN + 'UEAAXM@Z'),
    'getScaleY': (18, c_float, (), '?getScaleY' + _CN + 'UEAAMXZ'),
    'setScale': (20, None, (c_float,), '?setScale' + _CN + 'UEAAXM@Z'),
    'getScale': (21, c_float, (), '?getScale' + _CN + 'UEAAMXZ'),
    'setPosition': (22, None, (c_float, c_float), '?setPosition' + _CN + 'UEAAXMM@Z'),
    'getPosition': (25, c_void_p, (), '?getPosition' + _CN + 'UEAAAEBVCCPoint@2@XZ'),
    'setPositionX': (26, None, (c_float,), '?setPositionX' + _CN + 'UEAAXM@Z'),
    'getPositionX': (27, c_float, (), '?getPositionX' + _CN + 'UEAAMXZ'),
    'setPositionY': (28, None, (c_float,), '?setPositionY' + _CN + 'UEAAXM@Z'),
    'getPositionY': (29, c_float, (), '?getPositionY' + _CN + 'UEAAMXZ'),
    'setSkewX': (32, None, (c_float,), '?setSkewX' + _CN + 'UEAAXM@Z'),
    'getSkewX': (33, c_float, (), '?getSkewX' + _CN + 'UEAAMXZ'),
    'setSkewY': (34, None, (c_float,), '?setSkewY' + _CN + 'UEAAXM@Z'),
    'getSkewY': (35, c_float, (), '?getSkewY' + _CN + 'UEAAMXZ'),
    'setAnchorPoint': (36, None, (c_void_p,), '?setAnchorPoint' + _CN + 'UEAAXAEBVCCPoint@2@@Z'),
    'getAnchorPoint': (37, c_void_p, (), '?getAnchorPoint' + _CN + 'UEAAAEBVCCPoint@2@XZ'),
    'setContentSize': (39, None, (c_void_p,), '?setContentSize' + _CN + 'UEAAXAEBVCCSize@2@@Z'),
    'getContentSize': (40, c_void_p, (), '?getContentSize' + _CN + 'UEBAAEBVCCSize@2@XZ'),
    'setVisible': (42, None, (c_bool,), '?setVisible' + _CN + 'UEAAX_N@Z'),
    'isVisible': (43, c_bool, (), '?isVisible' + _CN + 'UEAA_NXZ'),
    'setRotation': (44, None, (c_float,), '?setRotation' + _CN + 'UEAAXM@Z'),
    'getRotation': (45, c_float, (), '?getRotation' + _CN + 'UEAAMXZ'),
    'addChild': (56, None, (c_void_p, c_int, c_int), '?addChild' + _CN + 'UEAAXPEAV12@HH@Z'),
    'getChildByTag': (59, c_void_p, (c_int,), '?getChildByTag' + _CN + 'UEAAPEAV12@H@Z'),
    'getChildren': (60, c_void_p, (), '?getChildren' + _CN + 'UEAAPEAVCCArray@2@XZ'),
    'getChildrenCount': (61, c_uint, (), '?getChildrenCount' + _CN + 'UEBAIXZ'),
    'getParent': (63, c_void_p, (), '?getParent' + _CN + 'UEAAPEAV12@XZ'),
    'removeFromParentAndCleanup': (65, None, (c_bool,), '?removeFromParentAndCleanup' + _CN + 'UEAAX_N@Z'),
    'removeChild': (67, None, (c_void_p, c_bool), '?removeChild' + _CN + 'UEAAXPEAV12@_N@Z'),
    'removeAllChildrenWithCleanup': (72, None, (c_bool,), '?removeAllChildrenWithCleanup' + _CN + 'UEAAX_N@Z'),
    'reorderChild': (73, None, (c_void_p, c_int), '?reorderChild' + _CN + 'UEAAXPEAV12@H@Z'),
    'isRunning': (84, c_bool, (), '?isRunning' + _CN + 'UEAA_NXZ'),
    # CCMenuItem
    'activate': (111, None, (), '?activate@CCMenuItem@cocos2d@@UEAAXXZ'),
    'isEnabled': (116, c_bool, (), '?isEnabled@CCMenuItem@cocos2d@@UEAA_NXZ'),
    'setEnabled': (117, None, (c_bool,), '?setEnabled@CCMenuItem@cocos2d@@UEAAX_N@Z'),
}
_MENU_ITEM_CALLS = ('activate', 'isEnabled', 'setEnabled')
# secondary bases: (base class, slot, restype, argtypes); "this" is the base subobject inside the node
_P = {
    'setColor': ('cocos2d::CCRGBAProtocol', 0, None, (c_void_p,)),
    'getColor': ('cocos2d::CCRGBAProtocol', 1, c_void_p, ()),
    'getOpacity': ('cocos2d::CCRGBAProtocol', 4, c_ubyte, ()),
    'setOpacity': ('cocos2d::CCRGBAProtocol', 5, None, (c_ubyte,)),
    'setString': ('cocos2d::CCLabelProtocol', 0, None, (c_char_p,)),
    'getString': ('cocos2d::CCLabelProtocol', 1, c_char_p, ()),
}
_use_vt = {}       # name -> True (virtual call through the object's vtable) / False (direct export)
_fn_cache = {}
_protos = {}


def _proto(rt, at):
    key = (rt, at)
    p = _protos.get(key)
    if p is None:
        p = _protos[key] = ctypes.CFUNCTYPE(rt, c_void_p, *at)
    return p


def _check_vtables():
    """Compare our slot numbers with the real CCNode / CCMenuItem vtables (once)."""
    ex = N.cocos.exports if N.cocos else {}
    vts = {False: ex.get('??_7CCNode@cocos2d@@6B@'), True: ex.get('??_7CCMenuItem@cocos2d@@6BCCNode@1@@')}
    bad = []
    for name, (slot, _, _, mangled) in _V.items():
        vt = vts[name in _MENU_ITEM_CALLS]
        exp = ex.get(mangled)
        got = M.ptr(vt + 8 * slot) if vt else None
        _use_vt[name] = bool(exp and got == exp)
        if not _use_vt[name]:
            bad.append(name)
    if bad:
        print('[PyModder] node vtable check: direct calls for', ', '.join(bad))


def vcall(ptr, name, *args):
    """Call a cocos2d virtual method of a node: vcall(node, 'setPosition', 10.0, 20.0)."""
    if name in _P:
        base, slot, rt, at = _P[name]
        off = M.bases(ptr).get(base)
        if off is None:
            raise TypeError('%s is not a %s' % (M.class_name(ptr), base.split('::')[-1]))
        sub = ptr + off
        fp = ctypes.c_uint64.from_address(ctypes.c_uint64.from_address(sub).value + 8 * slot).value
        key = (name, fp)
        f = _fn_cache.get(key)
        if f is None:
            f = _fn_cache[key] = _proto(rt, at)(fp)
        return f(sub, *args)
    if not _use_vt:
        _check_vtables()
    slot, rt, at, mangled = _V[name]
    if _use_vt.get(name):
        fp = ctypes.c_uint64.from_address(ctypes.c_uint64.from_address(ptr).value + 8 * slot).value
    else:
        fp = N.cocos.exports.get(mangled)
        if not fp:
            raise KeyError('not in libcocos2d.dll: ' + mangled)
    key = (name, fp)
    f = _fn_cache.get(key)
    if f is None:
        f = _fn_cache[key] = _proto(rt, at)(fp)
    return f(ptr, *args)


_xf = {}


def _x(key):
    """Extra cocos2d exports used here (loaded on first use)."""
    f = _xf.get(key)
    if f is None:
        v, fl, b = c_void_p, c_float, c_bool
        T = {
            'arr_create': ('?create@CCArray@cocos2d@@SAPEAV12@XZ', v),
            'arr_add': ('?addObject@CCArray@cocos2d@@QEAAXPEAVCCObject@2@@Z', None, v, v),
            'anim_frames': ('?createWithSpriteFrames@CCAnimation@cocos2d@@SAPEAV12@PEAVCCArray@2@M@Z', v, v, fl),
            'animate': ('?create@CCAnimate@cocos2d@@SAPEAV12@PEAVCCAnimation@2@@Z', v, v),
            'repeat': ('?create@CCRepeat@cocos2d@@SAPEAV12@PEAVCCFiniteTimeAction@2@I@Z', v, v, c_uint),
            'normal_image': ('?getNormalImage@CCMenuItemSprite@cocos2d@@UEAAPEAVCCNode@2@XZ', v, v),
            'frame_shown': ('?isFrameDisplayed@CCSprite@cocos2d@@UEAA_NPEAVCCSpriteFrame@2@@Z', b, v, v),
            'skew_to': ('?create@CCSkewTo@cocos2d@@SAPEAV12@MMM@Z', v, fl, fl, fl),
            'rotate_to': ('?create@CCRotateTo@cocos2d@@SAPEAV12@MM@Z', v, fl, fl),
            'tint_to': ('?create@CCTintTo@cocos2d@@SAPEAV12@MEEE@Z', v, fl, c_ubyte, c_ubyte, c_ubyte),
            'ease_in_out': ('?create@CCEaseInOut@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@M@Z', v, v, fl),
            'convert_to_node': ('?convertToNodeSpace@CCNode@cocos2d@@QEAA?AVCCPoint@2@AEBV32@@Z', v, v, v, v),
        }
        sig = T[key]
        f = _xf[key] = N.cocos_fn(sig[0], *sig[1:])
    return f


def _addr(p):
    if isinstance(p, Node):
        return p.ptr
    if isinstance(p, c_void_p):
        return p.value or 0
    return int(p or 0)


def _array(arr):
    if not arr:
        return []
    n = C.fn('arr_count')(arr)
    return [C.fn('arr_at')(arr, i) for i in range(min(n, 100000))]


# ---------------------------------------------------------------- selectors -> names, node IDs
_sel_names = {}


def selector_name(addr):
    """'MenuLayer::onPlay' for the address of a game function (None if unknown)."""
    if not _sel_names and N.bindings:
        base = N.gd_module.base
        for name, f in N.bindings.items():
            _sel_names.setdefault(base + f[0], name)
    return _sel_names.get(addr)


def _kebab(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', s)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1-\2', s)
    return s.replace('_', '-').lower()


# Geode-like IDs for well known buttons (selector -> id); other buttons: "onFooBar" -> "foo-bar-button"
ID_ALIASES = {
    'MenuLayer::onGarage': 'icon-kit-button', 'MenuLayer::onCreator': 'editor-button',
    'MenuLayer::onOptions': 'settings-button', 'MenuLayer::onDaily': 'daily-chest-button',
    'MenuLayer::onMyProfile': 'profile-button', 'MenuLayer::onQuit': 'close-button',
    'MenuLayer::onAchievements': 'achievements-button', 'MenuLayer::onStats': 'stats-button',
    'MenuLayer::onNewgrounds': 'newgrounds-button', 'MenuLayer::onMoreGames': 'more-games-button',
    'MenuLayer::onPlay': 'play-button', 'MenuLayer::onYouTube': 'youtube-button',
    'MenuLayer::onRobTop': 'robtop-button', 'LevelInfoLayer::onPlay': 'play-button',
    'LevelInfoLayer::onGarage': 'garage-button', 'LevelInfoLayer::onInfo': 'info-button',
    'LevelInfoLayer::onLevelInfo': 'info-button', 'LevelInfoLayer::onClone': 'copy-button',
    'LevelInfoLayer::onFavorite': 'favorite-button', 'LevelInfoLayer::onLike': 'like-button',
    'LevelInfoLayer::onRateStars': 'rate-button', 'LevelInfoLayer::onRateDemon': 'demon-rate-button',
    'LevelInfoLayer::onBack': 'back-button', 'PauseLayer::onResume': 'play-button',
    'PauseLayer::onQuit': 'exit-button', 'PauseLayer::tryQuit': 'exit-button',
    'PauseLayer::onRestart': 'retry-button', 'PauseLayer::onRestartFull': 'retry-button-full',
    'PauseLayer::onEdit': 'edit-button', 'PauseLayer::onPracticeMode': 'practice-button',
    'PauseLayer::onNormalMode': 'normal-button', 'PauseLayer::onSettings': 'options-button',
}
# a menu that holds one of these buttons gets this ID
MENU_IDS = {'play-button': 'main-menu', 'achievements-button': 'bottom-menu', 'profile-button': 'profile-menu',
            'close-button': 'close-menu', 'daily-chest-button': 'right-side-menu',
            'more-games-button': 'more-games-menu'}
_ids = {}          # ptr -> (vtable, id) for IDs set by mods
_owned_ids = {}    # owner -> [ptr]


def auto_id(ptr):
    """The automatic ID of a node (from its button selector), or None."""
    cls = M.class_name(ptr) or ''
    if 'MenuItem' in cls:
        sel = selector_name(M.ptr(ptr + MI_SELECTOR) or 0)
        if not sel:
            return None
        if sel in ID_ALIASES:
            return ID_ALIASES[sel]
        meth = sel.split('::')[-1]
        if meth.startswith('on') and len(meth) > 2:
            meth = meth[2:]
        return _kebab(meth) + '-button'
    if cls == 'cocos2d::CCMenu':
        for ch in _array(_children_arr(ptr))[:40]:
            mid = MENU_IDS.get(node_id(ch))
            if mid:
                return mid
    return None


def node_id(ptr):
    got = _ids.get(ptr)
    if got and got[0] == M.ptr(ptr):
        return got[1]
    return auto_id(ptr)


def set_node_id(ptr, value, owner=None):
    if len(_ids) > 4000:
        _prune_ids()
    if value is None:
        _ids.pop(ptr, None)
    else:
        _ids[ptr] = (M.ptr(ptr), str(value))
        if owner:
            _owned_ids.setdefault(owner, []).append(ptr)


def _prune_ids():
    alive = set()
    sc = C.running_scene()
    if sc:
        for n in Node(sc).walk(12):
            alive.add(n.ptr)
    for p in [p for p in _ids if p not in alive]:
        del _ids[p]


def _children_arr(ptr):
    return vcall(ptr, 'getChildren')


# ---------------------------------------------------------------- Node
MI_ENABLED, MI_LISTENER, MI_SELECTOR = 0x159, 0x160, 0x168     # CCMenuItem fields (2.2091)
HELPER_MENU_TAG = 0x50594D


def _color_in(rgb):
    from . import _ui as U
    return U.parse_color(rgb)


class Node:
    """A game node. gd.Node(pointer). Compare with ==, use in sets / dicts.

        menu = layer.find(id="main-menu")
        btn = menu.add_button("GJ_infoIcon_001.png", lambda: gd.alert("Hi"))
    """
    __slots__ = ('ptr',)

    def __init__(self, ptr):
        self.ptr = _addr(ptr)

    def __eq__(self, other):
        return isinstance(other, Node) and other.ptr == self.ptr

    def __hash__(self):
        return hash(self.ptr)

    def __bool__(self):
        return bool(self.ptr)

    def __int__(self):
        return self.ptr

    def __repr__(self):
        i = self.id
        return '<Node %s%s 0x%x>' % (self.cls or '?', ' id=%r' % i if i else '', self.ptr)

    # --- type
    @property
    def class_name(self):
        """C++ class, e.g. 'cocos2d::CCMenu' or 'MenuLayer'."""
        return M.class_name(self.ptr)

    @property
    def cls(self):
        """Class without the namespace: 'CCMenu', 'MenuLayer'."""
        n = M.class_name(self.ptr)
        return n.split('::')[-1] if n else None

    def is_a(self, cls):
        """Is the node of class cls or derived from it: node.is_a('CCSprite'), node.is_a('FLAlertLayer')."""
        return M.is_a(self.ptr, cls)

    @property
    def valid(self):
        """Does the pointer still look like a live cocos2d object (best effort)."""
        vt = M.ptr(self.ptr)
        if not vt:
            return False
        for mod in (N.gd_module, N.cocos):
            if mod and mod.contains(vt):
                return True
        return M.class_name(self.ptr) is not None

    # --- transform
    @property
    def x(self):
        return vcall(self.ptr, 'getPositionX')

    @x.setter
    def x(self, v):
        vcall(self.ptr, 'setPositionX', float(v))

    @property
    def y(self):
        return vcall(self.ptr, 'getPositionY')

    @y.setter
    def y(self, v):
        vcall(self.ptr, 'setPositionY', float(v))

    @property
    def pos(self):
        return vcall(self.ptr, 'getPositionX'), vcall(self.ptr, 'getPositionY')

    @pos.setter
    def pos(self, xy):
        vcall(self.ptr, 'setPosition', float(xy[0]), float(xy[1]))

    def move(self, x, y):
        vcall(self.ptr, 'setPosition', float(x), float(y))
        return self

    def move_by(self, dx, dy):
        x, y = self.pos
        return self.move(x + dx, y + dy)

    @property
    def scale(self):
        return vcall(self.ptr, 'getScale')

    @scale.setter
    def scale(self, v):
        vcall(self.ptr, 'setScale', float(v))

    @property
    def scale_x(self):
        return vcall(self.ptr, 'getScaleX')

    @scale_x.setter
    def scale_x(self, v):
        vcall(self.ptr, 'setScaleX', float(v))

    @property
    def scale_y(self):
        return vcall(self.ptr, 'getScaleY')

    @scale_y.setter
    def scale_y(self, v):
        vcall(self.ptr, 'setScaleY', float(v))

    @property
    def rotation(self):
        return vcall(self.ptr, 'getRotation')

    @rotation.setter
    def rotation(self, v):
        vcall(self.ptr, 'setRotation', float(v))

    @property
    def skew(self):
        return vcall(self.ptr, 'getSkewX'), vcall(self.ptr, 'getSkewY')

    @skew.setter
    def skew(self, xy):
        vcall(self.ptr, 'setSkewX', float(xy[0]))
        vcall(self.ptr, 'setSkewY', float(xy[1]))

    @property
    def visible(self):
        return bool(vcall(self.ptr, 'isVisible'))

    @visible.setter
    def visible(self, v):
        vcall(self.ptr, 'setVisible', bool(v))

    def show(self):
        self.visible = True
        return self

    def hide(self):
        self.visible = False
        return self

    @property
    def z(self):
        return vcall(self.ptr, 'getZOrder')

    @z.setter
    def z(self, v):
        p = vcall(self.ptr, 'getParent')
        if p:
            vcall(p, 'reorderChild', self.ptr, int(v))
        else:
            vcall(self.ptr, 'setZOrder', int(v))

    @property
    def tag(self):
        return vcall(self.ptr, 'getTag')

    @tag.setter
    def tag(self, v):
        vcall(self.ptr, 'setTag', int(v))

    @property
    def anchor(self):
        p = vcall(self.ptr, 'getAnchorPoint')
        return struct.unpack('<ff', ctypes.string_at(p, 8)) if p else (0.5, 0.5)

    @anchor.setter
    def anchor(self, xy):
        vcall(self.ptr, 'setAnchorPoint', C.point(*xy))

    @property
    def size(self):
        """Content size (without scale)."""
        p = vcall(self.ptr, 'getContentSize')
        return struct.unpack('<ff', ctypes.string_at(p, 8)) if p else (0.0, 0.0)

    @size.setter
    def size(self, wh):
        vcall(self.ptr, 'setContentSize', C.size_buf(*wh))

    @property
    def width(self):
        return self.size[0] * abs(self.scale_x)

    @property
    def height(self):
        return self.size[1] * abs(self.scale_y)

    @property
    def world_pos(self):
        """Position on the screen."""
        p = vcall(self.ptr, 'getParent')
        x, y = self.pos
        return C.to_world(p, x, y) if p else (x, y)

    @property
    def world_rect(self):
        """(x0, y0, x1, y1) of the node on the screen."""
        return C.world_rect(self.ptr)

    def to_local(self, x, y):
        """Screen point -> point inside this node."""
        ret = ctypes.create_string_buffer(8)
        _x('convert_to_node')(self.ptr, ret, C.point(x, y))
        return struct.unpack('<ff', ret.raw)

    def contains_point(self, x, y):
        x0, y0, x1, y1 = self.world_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    # --- color / opacity / text (CCRGBAProtocol / CCLabelProtocol bases)
    @property
    def color(self):
        try:
            p = vcall(self.ptr, 'getColor')
        except TypeError:
            return None
        return tuple(ctypes.string_at(p, 3)) if p else None

    @color.setter
    def color(self, rgb):
        vcall(self.ptr, 'setColor', C.color3(_color_in(rgb)))

    @property
    def opacity(self):
        try:
            return vcall(self.ptr, 'getOpacity')
        except TypeError:
            return 255

    @opacity.setter
    def opacity(self, v):
        vcall(self.ptr, 'setOpacity', max(0, min(255, int(v))))

    @property
    def text(self):
        """Text of a label (CCLabelBMFont / CCLabelTTF); None for other nodes."""
        if 'cocos2d::CCLabelProtocol' not in M.bases(self.ptr):
            return None
        s = vcall(self.ptr, 'getString')
        return s.decode('utf-8', 'replace') if s else ''

    @text.setter
    def text(self, value):
        vcall(self.ptr, 'setString', str(value).encode('utf-8'))

    # --- tree
    @property
    def parent(self):
        p = vcall(self.ptr, 'getParent')
        return Node(p) if p else None

    @property
    def children(self):
        return [Node(p) for p in _array(vcall(self.ptr, 'getChildren'))]

    def child(self, index):
        """Child by index (negative = from the end); None if there is none."""
        ch = _array(vcall(self.ptr, 'getChildren'))
        try:
            return Node(ch[index])
        except IndexError:
            return None

    def child_by_tag(self, tag):
        p = vcall(self.ptr, 'getChildByTag', int(tag))
        return Node(p) if p else None

    @property
    def child_count(self):
        return vcall(self.ptr, 'getChildrenCount')

    def add(self, child, z=0, tag=None, x=None, y=None):
        c = _addr(child)
        vcall(self.ptr, 'addChild', c, int(z), int(vcall(c, 'getTag') if tag is None else tag))
        if x is not None or y is not None:
            vcall(c, 'setPosition', float(x or 0), float(y or 0))
        return Node(c)

    def remove(self, cleanup=True):
        """Remove the node from its parent (it is deleted if nobody else keeps it)."""
        vcall(self.ptr, 'removeFromParentAndCleanup', bool(cleanup))

    def remove_children(self):
        vcall(self.ptr, 'removeAllChildrenWithCleanup', True)

    def move_to_parent(self, new_parent, z=None):
        """Re-attach the node to another parent (keeps it alive while moving)."""
        C.fn('retain')(self.ptr)
        try:
            zz = self.z if z is None else z
            vcall(self.ptr, 'removeFromParentAndCleanup', False)
            Node(new_parent).add(self.ptr, zz)
        finally:
            C.fn('release')(self.ptr)
        return self

    def walk(self, depth=8):
        """This node and all children (depth-first)."""
        out = [self]
        if depth > 0:
            for ch in _array(vcall(self.ptr, 'getChildren')):
                out += Node(ch).walk(depth - 1)
        return out

    @property
    def running(self):
        return bool(vcall(self.ptr, 'isRunning'))

    # --- search
    def _match(self, id=None, cls=None, base=None, selector=None, frame=None, text=None, tag=None, where=None,
               _frame_ptr=None):
        p = self.ptr
        if cls is not None:
            n = M.class_name(p) or ''
            if n != cls and n.split('::')[-1] != cls:
                return False
        if base is not None and not M.is_a(p, base):
            return False
        if tag is not None and vcall(p, 'getTag') != tag:
            return False
        if id is not None and node_id(p) != id:
            return False
        if selector is not None:
            n = M.class_name(p) or ''
            if 'MenuItem' not in n:
                return False
            s = selector_name(M.ptr(p + MI_SELECTOR) or 0) or ''
            if s != selector and s.split('::')[-1] != selector:
                return False
        if text is not None:
            t = self.text
            if t is None or (t != text and not (callable(text) and text(t))):
                return False
        if frame is not None and not self.shows_frame(frame, _frame_ptr):
            return False
        if where is not None:
            try:
                if not where(self):
                    return False
            except Exception:
                return False
        return True

    def find_all(self, id=None, cls=None, base=None, selector=None, frame=None, text=None, tag=None, where=None,
                 depth=8):
        """All nodes inside this one that match every given filter:
        id ("play-button"), cls ("CCMenu"), base (a base class), selector ("MenuLayer::onPlay" or "onPlay"),
        frame (sprite frame name, also checks a button's image), text (label text), tag, where (func(node))."""
        fp = None
        if frame is not None:
            fp = C.fn('sfc_get')(C.fn('sfc')(), str(frame).encode())
            if not fp:
                return []
        out = []
        for n in self.walk(depth)[1:]:
            if n._match(id, cls, base, selector, frame, text, tag, where, fp):
                out.append(n)
        return out

    def find(self, id=None, cls=None, base=None, selector=None, frame=None, text=None, tag=None, where=None,
             depth=8):
        """The first matching node (see find_all) or None."""
        fp = None
        if frame is not None:
            fp = C.fn('sfc_get')(C.fn('sfc')(), str(frame).encode())
            if not fp:
                return None
        stack = [(self.ptr, 0)]
        while stack:
            p, d = stack.pop()
            if p != self.ptr and Node(p)._match(id, cls, base, selector, frame, text, tag, where, fp):
                return Node(p)
            if d < depth:
                stack.extend((c, d + 1) for c in reversed(_array(vcall(p, 'getChildren'))))
        return None

    def shows_frame(self, name, _frame_ptr=None):
        """Does this sprite (or this button's image) show the sprite frame `name`."""
        fp = _frame_ptr or C.fn('sfc_get')(C.fn('sfc')(), str(name).encode())
        if not fp:
            return False
        p = self.ptr
        if M.is_a(p, 'cocos2d::CCMenuItemSprite'):
            p = _x('normal_image')(p) or 0
        if not p or not M.is_a(p, 'cocos2d::CCSprite'):
            return False
        return bool(_x('frame_shown')(p, fp))

    # --- node IDs
    @property
    def id(self):
        """Node ID: set by a mod (node.id = "my-button") or automatic for buttons ("play-button")."""
        return node_id(self.ptr)

    @id.setter
    def id(self, value):
        set_node_id(self.ptr, value, K.caller_owner())

    def by_id(self, node_id_, depth=8):
        return self.find(id=node_id_, depth=depth)

    # --- buttons (CCMenuItem)
    @property
    def is_button(self):
        return M.is_a(self.ptr, 'cocos2d::CCMenuItem')

    @property
    def selector(self):
        """Name of the game function a button calls, e.g. 'MenuLayer::onPlay' (None if unknown)."""
        if not self.is_button:
            return None
        return selector_name(M.ptr(self.ptr + MI_SELECTOR) or 0)

    @property
    def enabled(self):
        return bool(vcall(self.ptr, 'isEnabled')) if self.is_button else True

    @enabled.setter
    def enabled(self, v):
        if self.is_button:
            vcall(self.ptr, 'setEnabled', bool(v))

    def click(self):
        """Press the button (runs what the game does on a click)."""
        if not self.is_button:
            raise TypeError('%r is not a button' % self)
        vcall(self.ptr, 'activate')

    def on_click(self, func=None):
        """Replace what a game button does. func(original, button): call original() to run the game code.

            @layer.find(id="play-button").on_click
            def play(original):
                gd.confirm("Play?", on_yes=original)
        """
        owner = K.caller_owner()

        def deco(f):
            set_click(self.ptr, f, owner)
            return f
        return deco(func) if func is not None else deco

    @property
    def image(self):
        """The sprite of a button (CCMenuItemSprite normal image)."""
        if M.is_a(self.ptr, 'cocos2d::CCMenuItemSprite'):
            p = _x('normal_image')(self.ptr)
            return Node(p) if p else None
        return None

    def add_button(self, image=None, callback=None, x=0.0, y=0.0, size=None, text=None, color='green', id=None,
                   z=5, scale=None):
        """Add a GD button (with the GD click animation) to this node. image: sprite frame / .png / builtin
        icon name; or text= for a GD text button. On a CCMenu it is added to the menu, otherwise to a small
        menu created inside this node (x, y are relative to this node)."""
        owner = K.caller_owner()
        return add_button(self, image, callback, x, y, size, text, color, id, z, owner, scale)

    def add_label(self, text, x=0.0, y=0.0, size=0.5, color=(255, 255, 255), font=None, z=5, id=None,
                  anchor=None):
        """Add a text node to this node (GD font, Arial for non-latin text) -> gd.Node.
        It is removed when the mod is reloaded. Change it later: label.text = "..."."""
        from . import _cocos as CC
        owner = K.caller_owner()
        lb = CC.Label(str(text), float(x), float(y), size, font, color, z=int(z), parent=self.ptr,
                      anchor_xy=anchor)
        _added.append((lb.node, M.ptr(lb.node), owner))
        if id:
            set_node_id(lb.node, id, owner)
        return Node(lb.node)

    # --- sprites
    def set_frame(self, name):
        """Show another sprite frame (CCSprite.setDisplayFrame). name: frame name or a frame pointer."""
        fr = name if isinstance(name, int) else C.fn('sfc_get')(C.fn('sfc')(), str(name).encode())
        if not fr:
            raise KeyError('no sprite frame %r' % (name,))
        C.fn('spr_frame_set')(self.ptr, fr)
        return self

    def animate(self, frames, fps=12.0, loop=True, times=None):
        """Play sprite frames (names or frame pointers) on this sprite. loop=False plays once."""
        arr = _x('arr_create')()
        n = 0
        for fr in frames:
            p = fr if isinstance(fr, int) else C.fn('sfc_get')(C.fn('sfc')(), str(fr).encode())
            if p:
                _x('arr_add')(arr, p)
                n += 1
        if not n:
            raise KeyError('no frames to animate')
        act = _x('animate')(_x('anim_frames')(arr, float(1.0 / max(0.1, fps))))
        if times:
            act = _x('repeat')(act, int(times))
        elif loop:
            act = C.fn('repeat_forever')(act)
        return self.run(act)

    # --- actions
    def run(self, action):
        if action:
            return C.fn('run_action')(self.ptr, action)
        return None

    def stop(self):
        C.fn('stop_all')(self.ptr)
        return self

    def _ease(self, act, ease):
        if not ease:
            return act
        f = {'back': 'ease_back_out', 'bounce': 'ease_bounce_out', 'sine': 'ease_sine_out'}.get(ease)
        if f:
            return C.fn(f)(act)
        if ease == 'elastic':
            return C.fn('ease_elastic_out')(act, 0.3)
        if ease == 'in_out':
            return _x('ease_in_out')(act, 2.0)
        raise ValueError('ease: back, bounce, sine, elastic, in_out')

    def move_to(self, x, y, t=0.3, ease=None):
        return self.run(self._ease(C.fn('move_to')(float(t), C.point(x, y)), ease))

    def scale_to(self, s, t=0.3, ease=None):
        return self.run(self._ease(C.fn('scale_to')(float(t), float(s)), ease))

    def fade_to(self, opacity, t=0.3):
        return self.run(C.fn('fade_to')(float(t), max(0, min(255, int(opacity)))))

    def rotate_to(self, angle, t=0.3, ease=None):
        return self.run(self._ease(_x('rotate_to')(float(t), float(angle)), ease))

    def rotate_by(self, angle, t=0.3):
        return self.run(C.fn('rotate_by')(float(t), float(angle)))

    def tint_to(self, rgb, t=0.3):
        r, g, b = _color_in(rgb)
        return self.run(_x('tint_to')(float(t), r, g, b))

    def spin(self, speed=90.0):
        """Rotate forever (degrees per second)."""
        return self.run(C.fn('repeat_forever')(C.fn('rotate_by')(1.0, float(speed))))

    def retain(self):
        C.fn('retain')(self.ptr)
        return self

    def release(self):
        C.fn('release')(self.ptr)


def scene():
    """The running scene as a Node (None while switching)."""
    p = C.running_scene()
    return Node(p) if p else None


def find(**kw):
    """Search the whole running scene: gd.find(id="play-button")."""
    sc = scene()
    return sc.find(**kw) if sc else None


def find_all(**kw):
    sc = scene()
    return sc.find_all(**kw) if sc else []


def current_layer():
    """The main layer of the running scene (MenuLayer, LevelInfoLayer, PlayLayer...)."""
    sc = scene()
    if not sc:
        return None
    for ch in sc.children:
        n = ch.class_name or ''
        if not n.startswith('cocos2d::') and ch.visible:
            return ch
    ch = sc.children
    return ch[0] if ch else None


# ---------------------------------------------------------------- button callbacks
_SEL = ctypes.CFUNCTYPE(None, c_void_p, c_void_p)
_clicks = {}       # item ptr -> [func, owner, listener, original selector, vtable]
_added = []        # [(item, vtable, owner)] buttons created by mods


def _on_click(this, sender):
    try:
        ent = _clicks.get(sender)
        if not ent:
            return
        func, owner, listener, orig_sel, _ = ent

        def original():
            _SEL(orig_sel)(listener, sender)
        from . import _ui as U
        U.flex_call(owner, func, original, Node(sender))
    except Exception:
        traceback.print_exc()


_click_cb = _SEL(_on_click)
_click_addr = ctypes.cast(_click_cb, c_void_p).value


def set_click(item, func, owner):
    item = _addr(item)
    if not M.is_a(item, 'cocos2d::CCMenuItem'):
        raise TypeError('not a button: %s' % M.class_name(item))
    cur = M.ptr(item + MI_SELECTOR)
    ent = _clicks.get(item)
    if ent and cur == _click_addr and ent[4] == M.ptr(item):
        ent[0], ent[1] = func, owner
        return
    _clicks[item] = [func, owner, M.ptr(item + MI_LISTENER), cur, M.ptr(item)]
    M.write(item + MI_SELECTOR, struct.pack('<Q', _click_addr))


def _restore_clicks(owner):
    for item, ent in list(_clicks.items()):
        if ent[1] != owner:
            continue
        del _clicks[item]
        try:
            if M.ptr(item) == ent[4] and M.ptr(item + MI_SELECTOR) == _click_addr:
                M.write(item + MI_SELECTOR, struct.pack('<Q', ent[3]))
        except Exception:
            traceback.print_exc()


def _mod_dir(owner):
    m = sys.modules.get(owner)
    return getattr(m, 'MOD_DIR', None) or os.path.join(K.ROOT or '.', 'mods')


def helper_menu(node):
    """A CCMenu inside `node` at (0, 0) for our buttons (created once)."""
    p = _addr(node)
    m = vcall(p, 'getChildByTag', HELPER_MENU_TAG)
    if m and M.class_name(m) == 'cocos2d::CCMenu':
        return m
    m = C.fn('menu_create')()
    vcall(m, 'setPosition', 0.0, 0.0)
    vcall(p, 'addChild', m, 10, HELPER_MENU_TAG)
    return m


def add_button(node, image=None, callback=None, x=0.0, y=0.0, size=None, text=None, color='green', id=None, z=5,
               owner='pymodder', scale=None):
    from . import _menu as MN
    from . import _ui as U
    p = _addr(node)
    menu = p if M.is_a(p, 'cocos2d::CCMenu') else helper_menu(p)
    if text is not None:
        spr = C.button_sprite(str(text) if str(text).isascii() else '?', 0, U._texture(color), 'goldFont.fnt',
                              1.0, 0.0, False)
        if spr:
            w, h = C.node_size(spr)
            s = scale if scale else (size / max(h, 1) if size else 0.7)
            vcall(spr, 'setScale', float(s))
    else:
        spr, _ = MN._icon(image, _mod_dir(owner), size or 30)
        if spr and scale:
            vcall(spr, 'setScale', float(scale))
    if not spr:
        raise ValueError('cannot make a button image from %r' % (image if text is None else text))
    item = N.function('CCMenuItemSpriteExtra::create')(spr, None, menu, MN._sel_addr)
    if not item:
        raise RuntimeError('CCMenuItemSpriteExtra::create failed')
    MN._item_cbs[item] = (callback, owner)
    vcall(menu, 'addChild', item, int(z), 0)
    vcall(item, 'setPosition', float(x), float(y))
    _added.append((item, M.ptr(item), owner))
    if id:
        set_node_id(item, id, owner)
    return Node(item)


def _remove_added(owner):
    from . import _menu as MN
    keep = []
    for item, vt, own in _added:
        if own != owner:
            keep.append((item, vt, own))
            continue
        MN._item_cbs.pop(item, None)
        try:
            if M.ptr(item) == vt and vcall(item, 'getParent'):
                vcall(item, 'removeFromParentAndCleanup', True)
        except Exception:
            traceback.print_exc()
    _added[:] = keep


# ---------------------------------------------------------------- layer events
# The function that builds each layer (handlers run right after it). Default: "<Class>::init".
LAYER_ENTRY = {
    'PauseLayer': 'PauseLayer::customSetup', 'OptionsLayer': 'OptionsLayer::customSetup',
    'EndLevelLayer': 'EndLevelLayer::customSetup', 'StatsLayer': 'StatsLayer::customSetup',
    'AchievementsLayer': 'AchievementsLayer::customSetup', 'SupportLayer': 'SupportLayer::customSetup',
    'AccountLayer': 'AccountLayer::customSetup', 'SongsLayer': 'SongsLayer::customSetup',
    'LevelCell': 'LevelCell::loadFromLevel', 'CommentCell': 'CommentCell::loadFromComment',
    'GJScoreCell': 'GJScoreCell::loadFromScore', 'GJLevelScoreCell': 'GJLevelScoreCell::loadFromScore',
    'MapPackCell': 'MapPackCell::loadFromMapPack', 'ProfilePage': 'ProfilePage::init',
}
_layer_handlers = {}     # entry -> [(cls, func, owner)]
_layer_hooks = set()
_layer_args = {}         # layer ptr -> (vtable, args) of its last init call


def layer_entry(cls):
    e = LAYER_ENTRY.get(cls)
    if e:
        return e
    for cand in (cls + '::init', cls + '::customSetup', cls + '::setup'):
        if cand in N.bindings:
            return cand
    raise KeyError('do not know how %s is created; pass entry="Class::function"' % cls)


def _wrap_args(entry, args):
    f = N.bindings.get(entry)
    params = f[2] if f else []
    out = []
    for i, a in enumerate(args):
        t = params[i] if i < len(params) else ''
        out.append(_wrap(t, a))
    return out


def _wrap(t, a):
    t = t.replace('const', '').replace(' ', '')
    if t.endswith('*') and a:
        base = t[:-1].split('::')[-1]
        if base == 'GJGameLevel':
            from . import _levels as L
            return L.LevelData(a)
        if base in ('GameObject', 'EffectGameObject', 'RingObject', 'StartPosObject', 'TextGameObject'):
            from . import _objects as O
            return O.GameObject(a)
        if base.startswith('CC') or base.endswith(('Layer', 'Page', 'Cell', 'Popup', 'UI', 'Sprite', 'Player',
                                                   'Object', 'Node', 'Menu')):
            return Node(a)
        return a
    if t.endswith('&') and 'string' in t and a:
        return M.std_string(a)
    return a


def _layer_hook(entry):
    def handler(orig, this, *args):
        r = orig()
        if r is False:
            return r
        try:
            wrapped = _wrap_args(entry, args)
            if len(_layer_args) > 300:
                _layer_args.clear()
            _layer_args[this] = (M.ptr(this), wrapped)
            _dispatch(entry, this, wrapped)
        except Exception:
            traceback.print_exc()
        return r
    return handler


def _dispatch(entry, this, wrapped, only=None):
    from . import _ui as U
    cls = M.class_name(this) or ''
    short = cls.split('::')[-1]
    for c, func, owner in list(_layer_handlers.get(entry, [])):
        if only is not None and (func, owner) != only:
            continue
        if c not in (cls, short) and not M.is_a(this, c):
            continue
        U.flex_call(owner, func, Node(this), *wrapped)


def on_layer(cls, func, owner, entry=None):
    entry = entry or layer_entry(cls)
    if entry not in _layer_hooks:
        N.hook(entry, _layer_hook(entry), 'pymodder')
        _layer_hooks.add(entry)
    _layer_handlers.setdefault(entry, []).append((cls, func, owner))
    K.later(lambda: _rescan(entry, cls, func, owner))
    return func


def _guess_args(entry, ptr):
    f = N.bindings.get(entry)
    out = []
    for t in (f[2] if f else []):
        t2 = t.replace('const', '').replace(' ', '')
        if t2.endswith('GJGameLevel*'):
            off = M.find_pointer_to(ptr, 'GJGameLevel', 0x100, 0x1000)
            out.append(_wrap(t, M.ptr(ptr + off)) if off is not None else None)
        else:
            out.append(None)
    return out


def _rescan(entry, cls, func, owner):
    """A mod registered after the layer was built (mod reload): run the handler for open layers too."""
    if (cls, func, owner) not in _layer_handlers.get(entry, []):
        return
    sc = C.running_scene()
    if not sc:
        return
    for n in Node(sc).walk(5):
        name = n.class_name or ''
        if name != cls and name.split('::')[-1] != cls:
            continue
        got = _layer_args.get(n.ptr)
        args = got[1] if got and got[0] == M.ptr(n.ptr) else _guess_args(entry, n.ptr)
        _dispatch(entry, n.ptr, args, only=(func, owner))


def _forget_owner(owner):
    for entry, lst in _layer_handlers.items():
        lst[:] = [h for h in lst if h[2] != owner]
    _restore_clicks(owner)
    _remove_added(owner)
    for p in _owned_ids.pop(owner, []):
        _ids.pop(p, None)


K.cleanup_hooks.append(_forget_owner)
