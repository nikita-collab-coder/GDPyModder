"""cocos2d helpers: director, nodes, labels, sprites, actions, drawing.
Every call here must run on the game thread."""
import ctypes
import math
import os
import struct
import time
from ctypes import (c_void_p, c_float, c_int, c_uint, c_bool, c_char_p, c_ubyte, create_string_buffer)

from . import _native as N
from . import _mem as M

_f = {}
GD_DIR = None
_ext = {}        # CCScale9Sprite functions from libExtensions.dll (found at runtime)


def fn(key):
    return _f[key]


def init(gd_dir):
    global GD_DIR
    GD_DIR = gd_dir
    C = N.cocos_fn
    v, f, b, i, u, s, ub, d = c_void_p, c_float, c_bool, c_int, c_uint, c_char_p, c_ubyte, ctypes.c_double
    T = {
        'director': ('?sharedDirector@CCDirector@cocos2d@@SAPEAV12@XZ', v),
        'scene': ('?getRunningScene@CCDirector@cocos2d@@QEAAPEAVCCScene@2@XZ', v, v),
        'next_scene': ('?getNextScene@CCDirector@cocos2d@@QEAAPEAVCCScene@2@XZ', v, v),
        'winsize': ('?getWinSize@CCDirector@cocos2d@@QEAA?AVCCSize@2@XZ', v, v, v),
        'scale_factor': ('?getContentScaleFactor@CCDirector@cocos2d@@QEAAMXZ', f, v),
        'scheduler': ('?getScheduler@CCDirector@cocos2d@@UEAAPEAVCCScheduler@2@XZ', v, v),
        'set_ts': ('?setTimeScale@CCScheduler@cocos2d@@QEAAXM@Z', None, v, f),
        'get_ts': ('?getTimeScale@CCScheduler@cocos2d@@QEAAMXZ', f, v),
        # labels
        'bm_create': ('?create@CCLabelBMFont@cocos2d@@SAPEAV12@PEBD0@Z', v, s, s),
        'bm_create_w': ('?create@CCLabelBMFont@cocos2d@@SAPEAV12@PEBD0MW4CCTextAlignment@2@@Z', v, s, s, f, i),
        'bm_set': ('?setString@CCLabelBMFont@cocos2d@@UEAAXPEBD@Z', None, v, s),
        'bm_color': ('?setColor@CCLabelBMFont@cocos2d@@UEAAXAEBU_ccColor3B@2@@Z', None, v, v),
        'bm_opacity': ('?setOpacity@CCLabelBMFont@cocos2d@@UEAAXE@Z', None, v, ub),
        'ttf_create': ('?create@CCLabelTTF@cocos2d@@SAPEAV12@PEBD0M@Z', v, s, s, f),
        'ttf_create_d': ('?create@CCLabelTTF@cocos2d@@SAPEAV12@PEBD0MAEBVCCSize@2@W4CCTextAlignment@2@@Z',
                         v, s, s, f, v, i),
        'ttf_set': ('?setString@CCLabelTTF@cocos2d@@UEAAXPEBD@Z', None, v, s),
        # sprites
        'spr_create': ('?create@CCSprite@cocos2d@@SAPEAV12@PEBD@Z', v, s),
        'spr_frame': ('?createWithSpriteFrameName@CCSprite@cocos2d@@SAPEAV12@PEBD@Z', v, s),
        'sfc': ('?sharedSpriteFrameCache@CCSpriteFrameCache@cocos2d@@SAPEAV12@XZ', v),
        'sfc_get': ('?spriteFrameByName@CCSpriteFrameCache@cocos2d@@QEAAPEAVCCSpriteFrame@2@PEBD@Z', v, v, s),
        'spr_color': ('?setColor@CCSprite@cocos2d@@UEAAXAEBU_ccColor3B@2@@Z', None, v, v),
        'spr_opacity': ('?setOpacity@CCSprite@cocos2d@@UEAAXE@Z', None, v, ub),
        'spr_flipx': ('?setFlipX@CCSprite@cocos2d@@QEAAX_N@Z', None, v, b),
        'spr_frame_set': ('?setDisplayFrame@CCSprite@cocos2d@@UEAAXPEAVCCSpriteFrame@2@@Z', None, v, v),
        # nodes
        'node_create': ('?create@CCNode@cocos2d@@SAPEAV12@XZ', v),
        'add_child': ('?addChild@CCNode@cocos2d@@UEAAXPEAV12@H@Z', None, v, v, i),
        'remove': ('?removeFromParentAndCleanup@CCNode@cocos2d@@UEAAX_N@Z', None, v, b),
        'parent': ('?getParent@CCNode@cocos2d@@UEAAPEAV12@XZ', v, v),
        'children': ('?getChildren@CCNode@cocos2d@@UEAAPEAVCCArray@2@XZ', v, v),
        'arr_count': ('?count@CCArray@cocos2d@@QEBAIXZ', u, v),
        'arr_at': ('?objectAtIndex@CCArray@cocos2d@@QEAAPEAVCCObject@2@I@Z', v, v, u),
        'set_pos': ('?setPosition@CCNode@cocos2d@@UEAAXMM@Z', None, v, f, f),
        'get_x': ('?getPositionX@CCNode@cocos2d@@UEAAMXZ', f, v),
        'get_y': ('?getPositionY@CCNode@cocos2d@@UEAAMXZ', f, v),
        'get_rot': ('?getRotation@CCNode@cocos2d@@UEAAMXZ', f, v),
        'set_rot': ('?setRotation@CCNode@cocos2d@@UEAAXM@Z', None, v, f),
        'set_scale': ('?setScale@CCNode@cocos2d@@UEAAXM@Z', None, v, f),
        'set_scale_x': ('?setScaleX@CCNode@cocos2d@@UEAAXM@Z', None, v, f),
        'set_scale_y': ('?setScaleY@CCNode@cocos2d@@UEAAXM@Z', None, v, f),
        'get_scale': ('?getScale@CCNode@cocos2d@@UEAAMXZ', f, v),
        'set_visible': ('?setVisible@CCNode@cocos2d@@UEAAX_N@Z', None, v, b),
        'is_visible': ('?isVisible@CCNode@cocos2d@@UEAA_NXZ', b, v),
        'set_anchor': ('?setAnchorPoint@CCNode@cocos2d@@UEAAXAEBVCCPoint@2@@Z', None, v, v),
        'set_z': ('?setZOrder@CCNode@cocos2d@@UEAAXH@Z', None, v, i),
        'get_size': ('?getContentSize@CCNode@cocos2d@@UEBAAEBVCCSize@2@XZ', v, v),
        'set_size': ('?setContentSize@CCNode@cocos2d@@UEAAXAEBVCCSize@2@@Z', None, v, v),
        'to_world': ('?convertToWorldSpace@CCNode@cocos2d@@QEAA?AVCCPoint@2@AEBV32@@Z', v, v, v, v),
        'run_action': ('?runAction@CCNode@cocos2d@@QEAAPEAVCCAction@2@PEAV32@@Z', v, v, v),
        'stop_all': ('?stopAllActions@CCNode@cocos2d@@QEAAXXZ', None, v),
        'retain': ('?retain@CCObject@cocos2d@@QEAAXXZ', None, v),
        'release': ('?release@CCObject@cocos2d@@QEAAXXZ', None, v),
        # layers / menu
        'layer_color': ('?create@CCLayerColor@cocos2d@@SAPEAV12@AEBU_ccColor4B@2@MM@Z', v, v, f, f),
        'lc_opacity': ('?setOpacity@CCLayerColor@cocos2d@@UEAAXE@Z', None, v, ub),
        'lc_color': ('?setColor@CCLayerColor@cocos2d@@UEAAXAEBU_ccColor3B@2@@Z', None, v, v),
        'menu_create': ('?create@CCMenu@cocos2d@@SAPEAV12@XZ', v),
        # actions
        'delay': ('?create@CCDelayTime@cocos2d@@SAPEAV12@M@Z', v, f),
        'fade_out': ('?create@CCFadeOut@cocos2d@@SAPEAV12@M@Z', v, f),
        'fade_in': ('?create@CCFadeIn@cocos2d@@SAPEAV12@M@Z', v, f),
        'fade_to': ('?create@CCFadeTo@cocos2d@@SAPEAV12@ME@Z', v, f, ub),
        'scale_to': ('?create@CCScaleTo@cocos2d@@SAPEAV12@MM@Z', v, f, f),
        'move_to': ('?create@CCMoveTo@cocos2d@@SAPEAV12@MAEBVCCPoint@2@@Z', v, f, v),
        'rotate_by': ('?create@CCRotateBy@cocos2d@@SAPEAV12@MM@Z', v, f, f),
        'ease_back_out': ('?create@CCEaseBackOut@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@@Z', v, v),
        'ease_bounce_out': ('?create@CCEaseBounceOut@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@@Z', v, v),
        'ease_elastic_out': ('?create@CCEaseElasticOut@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@M@Z', v, v, f),
        'ease_sine_out': ('?create@CCEaseSineOut@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@@Z', v, v),
        'repeat_forever': ('?create@CCRepeatForever@cocos2d@@SAPEAV12@PEAVCCActionInterval@2@@Z', v, v),
        'seq2': ('?createWithTwoActions@CCSequence@cocos2d@@SAPEAV12@PEAVCCFiniteTimeAction@2@0@Z', v, v, v),
        'remove_self': ('?create@CCRemoveSelf@cocos2d@@SAPEAV12@_N@Z', v, b),
        # drawing
        'dn_create': ('?create@CCDrawNode@cocos2d@@SAPEAV12@XZ', v),
        'dn_clear': ('?clear@CCDrawNode@cocos2d@@QEAAXXZ', None, v),
        'dn_dot': ('?drawDot@CCDrawNode@cocos2d@@QEAA_NAEBVCCPoint@2@MAEBU_ccColor4F@2@@Z', b, v, v, f, v),
        'dn_seg': ('?drawSegment@CCDrawNode@cocos2d@@QEAA_NAEBVCCPoint@2@0MAEBU_ccColor4F@2@@Z', b, v, v, v, f, v),
        'dn_poly': ('?drawPolygon@CCDrawNode@cocos2d@@QEAA_NPEAVCCPoint@2@IAEBU_ccColor4F@2@M1W4BorderAlignment@2@@Z',
                    b, v, v, u, v, f, v, i),
        'dn_circle': ('?drawCircle@CCDrawNode@cocos2d@@QEAA_NAEBVCCPoint@2@MAEBU_ccColor4F@2@M1I@Z',
                      b, v, v, f, v, f, v, u),
        # input
        'set_any': ('?anyObject@CCSet@cocos2d@@QEAAPEAVCCObject@2@XZ', v, v),
        'touch_loc': ('?getLocation@CCTouch@cocos2d@@QEBA?AVCCPoint@2@XZ', v, v, v),
        'glview': ('?sharedOpenGLView@CCEGLView@cocos2d@@SAPEAV12@XZ', v),
        'gl_scale_x': ('?getScaleX@CCEGLViewProtocol@cocos2d@@QEBAMXZ', f, v),
        'gl_scale_y': ('?getScaleY@CCEGLViewProtocol@cocos2d@@QEBAMXZ', f, v),
        'gl_viewport': ('?getViewPortRect@CCEGLViewProtocol@cocos2d@@QEBAAEBVCCRect@2@XZ', v, v),
        'gl_mouse': ('?getMousePosition@CCEGLView@cocos2d@@UEBA?AVCCPoint@2@XZ', v, v, v),
        'gl_touch_begin': ('?handleTouchesBegin@CCEGLViewProtocol@cocos2d@@UEAAXHQEAHQEAM1N@Z', None, v, i, v, v, v, d),
        'gl_touch_move': ('?handleTouchesMove@CCEGLViewProtocol@cocos2d@@UEAAXHQEAHQEAM1N@Z', None, v, i, v, v, v, d),
        'gl_touch_end': ('?handleTouchesEnd@CCEGLViewProtocol@cocos2d@@UEAAXHQEAHQEAM1N@Z', None, v, i, v, v, v, d),
        'kbd_dispatcher': ('?getKeyboardDispatcher@CCDirector@cocos2d@@UEAAPEAVCCKeyboardDispatcher@2@XZ', v, v),
        'kbd_dispatch': ('?dispatchKeyboardMSG@CCKeyboardDispatcher@cocos2d@@QEAA_NW4enumKeyCodes@2@_N1N@Z',
                         b, v, i, b, b, d),
        # textures
        'tex_cache': ('?sharedTextureCache@CCTextureCache@cocos2d@@SAPEAV12@XZ', v),
        'tex_add': ('?addImage@CCTextureCache@cocos2d@@QEAAPEAVCCTexture2D@2@PEBD_N@Z', v, v, s, b),
        'tex_remove_key': ('?removeTextureForKey@CCTextureCache@cocos2d@@QEAAXPEBD@Z', None, v, s),
        'tex_size': ('?getContentSize@CCTexture2D@cocos2d@@UEAA?AVCCSize@2@XZ', v, v, v),
        'tex_alias': ('?setAliasTexParameters@CCTexture2D@cocos2d@@QEAAXXZ', None, v),
        'tex_antialias': ('?setAntiAliasTexParameters@CCTexture2D@cocos2d@@QEAAXXZ', None, v),
        'spr_with_tex': ('?createWithTexture@CCSprite@cocos2d@@SAPEAV12@PEAVCCTexture2D@2@@Z', v, v),
        'frame_with_tex': ('?createWithTexture@CCSpriteFrame@cocos2d@@SAPEAV12@PEAVCCTexture2D@2@AEBVCCRect@2@@Z',
                           v, v, v),
        'spr_tex_rect': ('?setTextureRect@CCSprite@cocos2d@@UEAAXAEBVCCRect@2@@Z', None, v, v),
        'tex_params': ('?setTexParameters@CCTexture2D@cocos2d@@QEAAXPEAU_ccTexParams@2@@Z', None, v, v),
        'sfc_add': ('?addSpriteFrame@CCSpriteFrameCache@cocos2d@@QEAAXPEAVCCSpriteFrame@2@PEBD@Z', None, v, v, s),
        'sfc_add_plist': ('?addSpriteFramesWithFile@CCSpriteFrameCache@cocos2d@@QEAAXPEBD@Z', None, v, s),
        'sfc_remove': ('?removeSpriteFrameByName@CCSpriteFrameCache@cocos2d@@QEAAXPEBD@Z', None, v, s),
    }
    for k, sig in T.items():
        try:
            _f[k] = C(sig[0], *sig[1:])
        except KeyError as e:
            print('[PyModder] missing cocos2d function:', k, e)
    apply_this_adjust()
    _find_scale9()


# setColor / setOpacity / setString are overrides of secondary base classes (CCRGBAProtocol,
# CCLabelProtocol). MSVC compiles them with "this" pointing to that base inside the object,
# so the node pointer has to be shifted before the call. Offsets checked in libcocos2d.dll 2.2091
# (the thunks do "lea rcx, [rcx - X]"): calling them with a plain node pointer crashes the game.
THIS_ADJUST = {
    'spr_color': 0x140, 'spr_opacity': 0x140,        # CCSprite (and CCLabelTTF): CCRGBAProtocol
    'bm_color': 0x170, 'bm_opacity': 0x170,          # CCLabelBMFont: CCRGBAProtocol
    'bm_set': 0x168,                                 # CCLabelBMFont: CCLabelProtocol
    'ttf_set': 0x258,                                # CCLabelTTF: CCLabelProtocol
    'lc_color': 0x198, 'lc_opacity': 0x198,          # CCLayerColor: CCRGBAProtocol
}
EXT_ADJUST = {'color': 0x140, 'opacity': 0x140}      # CCScale9Sprite : CCNodeRGBA


def _addr(p):
    if isinstance(p, c_void_p):
        return p.value or 0
    return int(p or 0)


def _shifted(raw, off):
    def call(node, *args):
        p = _addr(node)
        if not p:
            return None
        return raw(p + off, *args)
    call.raw, call.offset = raw, off
    return call


def apply_this_adjust(table=None, adjust=None):
    table = _f if table is None else table
    for k, off in (adjust or THIS_ADJUST).items():
        fn_ = table.get(k)
        if fn_ is not None and not hasattr(fn_, 'offset'):
            table[k] = _shifted(fn_, off)


def _find_scale9():
    """CCScale9Sprite lives in libExtensions.dll (exact names are searched at runtime)."""
    try:
        ext = M.Module('libExtensions.dll')
    except OSError:
        return
    ex = ext.exports
    want = {
        'create': lambda n: n.startswith('?create@CCScale9Sprite@') and n.endswith('@SAPEAV123@PEBD@Z'),
        'size': lambda n: n.startswith('?setContentSize@CCScale9Sprite@'),
        'opacity': lambda n: n.startswith('?setOpacity@CCScale9Sprite@') and n.endswith('XE@Z'),
        'color': lambda n: n.startswith('?setColor@CCScale9Sprite@'),
    }
    v = c_void_p
    sigs = {'create': (v, c_char_p), 'size': (None, v, v), 'opacity': (None, v, c_ubyte), 'color': (None, v, v)}
    for key, test in want.items():
        for name, addr in ex.items():
            if test(name):
                _ext[key] = ctypes.CFUNCTYPE(*sigs[key])(addr)
                break
    if 'create' not in _ext or 'size' not in _ext:
        _ext.clear()
    apply_this_adjust(_ext, EXT_ADJUST)
    print('[PyModder] CCScale9Sprite:', 'yes' if _ext else 'no (plain backgrounds)')


# ---------------------------------------------------------------- small value helpers
def point(x, y):
    return create_string_buffer(struct.pack('<ff', float(x), float(y)), 8)


def size_buf(w, h):
    return point(w, h)


def color3(rgb):
    r, g, b = [max(0, min(255, int(c))) for c in tuple(rgb)[:3]]
    return create_string_buffer(bytes((r, g, b, 0)), 4)


def color4(rgba):
    c = list(rgba) + [255] * (4 - len(rgba))
    return create_string_buffer(bytes(max(0, min(255, int(x))) for x in c[:4]), 4)


def color4f(rgba, premultiply=True):
    c = list(rgba) + [255] * (4 - len(rgba))
    r, g, b, a = [max(0, min(255, float(x))) / 255.0 for x in c[:4]]
    if premultiply:
        r, g, b = r * a, g * a, b * a
    return create_string_buffer(struct.pack('<4f', r, g, b, a), 16)


def _enc(text):
    return str(text).encode('utf-8')


# ---------------------------------------------------------------- director
def director():
    return _f['director']()


def running_scene():
    return _f['scene'](director())


def next_scene():
    return _f['next_scene'](director())


def win_size():
    buf = create_string_buffer(8)
    _f['winsize'](director(), buf)
    return struct.unpack('<ff', buf.raw)


def time_scale(value=None):
    s = _f['scheduler'](director())
    if value is not None:
        _f['set_ts'](s, float(value))
    return _f['get_ts'](s)


# ---------------------------------------------------------------- nodes
def position(node):
    return _f['get_x'](node), _f['get_y'](node)


def rotation(node):
    return _f['get_rot'](node)


def node_size(node):
    p = _f['get_size'](node)
    return struct.unpack('<ff', ctypes.string_at(p, 8)) if p else (0.0, 0.0)


def set_node_size(node, w, h):
    _f['set_size'](node, size_buf(w, h))


def to_world(node, x=0.0, y=0.0):
    ret = create_string_buffer(8)
    _f['to_world'](node, ret, point(x, y))
    return struct.unpack('<ff', ret.raw)


def world_rect(node):
    """(x0, y0, x1, y1) of the node box on screen."""
    w, h = node_size(node)
    x0, y0 = to_world(node, 0, 0)
    x1, y1 = to_world(node, w, h)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def children(node):
    arr = _f['children'](node) if node else None
    if not arr:
        return []
    return [_f['arr_at'](arr, i) for i in range(_f['arr_count'](arr))]


def find_children(node, cls, depth=2):
    out = []
    for ch in children(node):
        if M.class_name(ch) == cls:
            out.append(ch)
        if depth > 1:
            out += find_children(ch, cls, depth - 1)
    return out


def anchor(node, ax, ay):
    _f['set_anchor'](node, point(ax, ay))


def remove(node, cleanup=True):
    if node:
        _f['remove'](node, cleanup)


def run(node, action):
    if node and action:
        _f['run_action'](node, action)


def seq(*actions):
    a = actions[0]
    for b in actions[1:]:
        a = _f['seq2'](a, b)
    return a


def scale_bounce(node, scale, t=0.3):
    _f['stop_all'](node)
    run(node, _f['ease_bounce_out'](_f['scale_to'](t, float(scale))))


def scale_back(node, scale, t=0.25):
    _f['stop_all'](node)
    run(node, _f['ease_back_out'](_f['scale_to'](t, float(scale))))


# ---------------------------------------------------------------- resources
def frame_exists(name):
    return bool(_f['sfc_get'](_f['sfc'](), _enc(name)))


def res_path(name):
    """Full path of a file in Geometry Dash/Resources (any quality), or None."""
    if not GD_DIR:
        return None
    stem, ext = os.path.splitext(name)
    for suf in ('', '-uhd', '-hd'):
        p = os.path.join(GD_DIR, 'Resources', stem + suf + ext)
        if os.path.isfile(p):
            return p
    return None


def sprite(name, base_dir=None):
    """CCSprite from a sprite frame name ("GJ_infoIcon_001.png"), a GD resource or a .png path. None if not found."""
    if not name:
        return None
    name = str(name)
    if frame_exists(name):
        return _f['spr_frame'](_enc(name))
    path = name
    if not os.path.isabs(path) and base_dir:
        path = os.path.join(base_dir, name)
    if os.path.isfile(path):
        return _f['spr_create'](_enc(os.path.abspath(path)))
    if res_path(name):
        return _f['spr_create'](_enc(name))
    return None


def texture_rect(sprite, x, y, w, h):
    """CCSprite::setTextureRect (part of the texture; with GL_REPEAT a bigger rect tiles it)."""
    _f['spr_tex_rect'](sprite, create_string_buffer(struct.pack('<4f', float(x), float(y), float(w), float(h)), 16))


def repeat_texture(name):
    """Load a Resources .png and set GL_LINEAR + GL_REPEAT on it (as GD does for "sliderBar.png")."""
    if 'tex_params' not in _f or not res_path(name):
        return None
    tex = _f['tex_add'](_f['tex_cache'](), _enc(name), False)
    if tex:
        _f['tex_params'](tex, create_string_buffer(struct.pack('<4I', 0x2601, 0x2601, 0x2901, 0x2901), 16))
    return tex


def layer_color(rgba, w, h):
    return _f['layer_color'](color4(rgba), float(w), float(h))


def scale9(file, w, h):
    """Stretchable GD panel ("GJ_square01.png"). None if CCScale9Sprite is not available."""
    if not _ext or not res_path(file):
        return None
    n = _ext['create'](_enc(file))
    if n:
        _ext['size'](n, size_buf(w, h))
    return n


def scale9_style(node, rgb=None, opacity=None):
    if rgb is not None and 'color' in _ext:
        _ext['color'](node, color3(rgb))
    if opacity is not None and 'opacity' in _ext:
        _ext['opacity'](node, int(opacity))


def button_sprite(caption, width=0, texture='GJ_button_01.png', font='goldFont.fnt', scale=1.0, height=0.0,
                  absolute=False):
    f = N.function('ButtonSprite::create')
    return f(_enc(caption), int(width), 0, float(scale), bool(absolute), _enc(font), _enc(texture), float(height))


def set_color(node, rgb, kind='sprite'):
    key = {'sprite': 'spr_color', 'bm': 'bm_color', 'layer': 'lc_color'}[kind]
    _f[key](node, color3(rgb))


def set_opacity(node, value, kind='sprite'):
    key = {'sprite': 'spr_opacity', 'bm': 'bm_opacity', 'layer': 'lc_opacity'}[kind]
    _f[key](node, max(0, min(255, int(value))))


# ---------------------------------------------------------------- labels
ALIGN = {'left': 0, 'center': 1, 'right': 2}


class Label:
    """Text node. GD fonts for latin text, Arial for other languages (switches automatically)."""

    def __init__(self, text, x, y, size=0.5, font=None, color=(255, 255, 255), z=10000, parent=None,
                 width=None, align='center', anchor_xy=None):
        self._auto = font is None
        self._font = font
        self._text, self._x, self._y, self._size = str(text), x, y, size
        self._color, self._opacity, self._visible = tuple(color), 255, True
        self.width, self.align, self._anchor = width, align, anchor_xy
        self.z = z
        self.node = None
        self._build()
        if parent:
            _f['add_child'](parent, self.node, z)

    def _pick_font(self, text):
        f = self._font or 'bigFont.fnt'
        if f.endswith('.fnt') and not text.isascii():
            return 'Arial'      # GD bitmap fonts have latin letters only
        return f

    def _build(self):
        text = self._text
        self.font = self._pick_font(text)
        self.bm = self.font.endswith('.fnt')
        scale = self._size
        if self.bm:
            if self.width:
                self.node = _f['bm_create_w'](_enc(text), _enc(self.font), float(self.width / scale),
                                              ALIGN.get(self.align, 1))
            else:
                self.node = _f['bm_create'](_enc(text), _enc(self.font))
        else:
            scale = scale * 0.9
            if self.width:
                self.node = _f['ttf_create_d'](_enc(text), _enc(self.font), 32.0,
                                               size_buf(self.width / scale, 0), ALIGN.get(self.align, 1))
            else:
                self.node = _f['ttf_create'](_enc(text), _enc(self.font), 32.0)
        if not self.node:
            raise RuntimeError('cannot create a label (font %s?)' % self.font)
        self._scale = scale
        _f['set_pos'](self.node, float(self._x), float(self._y))
        _f['set_scale'](self.node, float(scale))
        if self._anchor:
            anchor(self.node, *self._anchor)
        self._apply_color()
        if self._opacity != 255:
            self.opacity(self._opacity)
        if not self._visible:
            _f['set_visible'](self.node, False)

    def _apply_color(self):
        (_f['bm_color'] if self.bm else _f['spr_color'])(self.node, color3(self._color))

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        value = str(value)
        if value == self._text:
            return
        self._text = value
        if self._pick_font(value) != self.font:
            old = self.node
            parent = _f['parent'](old)
            self._build()
            if parent:
                _f['add_child'](parent, self.node, self.z)
            _f['remove'](old, True)
            return
        (_f['bm_set'] if self.bm else _f['ttf_set'])(self.node, _enc(value))

    def move(self, x, y):
        self._x, self._y = x, y
        _f['set_pos'](self.node, float(x), float(y))

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, rgb):
        self._color = tuple(rgb)
        self._apply_color()

    def opacity(self, value):
        self._opacity = max(0, min(255, int(value)))
        (_f['bm_opacity'] if self.bm else _f['spr_opacity'])(self.node, self._opacity)

    def visible(self, value):
        self._visible = bool(value)
        _f['set_visible'](self.node, self._visible)

    def anchor(self, ax, ay):
        self._anchor = (ax, ay)
        anchor(self.node, ax, ay)

    def fit(self, max_w):
        """Shrink the text if it is wider than max_w."""
        w, _ = self.size()
        if w > max_w > 0:
            self._scale *= max_w / w
            _f['set_scale'](self.node, float(self._scale))

    def size(self):
        """Size on screen (width, height)."""
        w, h = node_size(self.node)
        return w * self._scale, h * self._scale

    def fade_and_remove(self, delay):
        a = seq(_f['delay'](float(delay)), _f['fade_out'](0.4), _f['remove_self'](True))
        _f['run_action'](self.node, a)


# ---------------------------------------------------------------- drawing
def draw_node():
    return _f['dn_create']()


def draw_line(dn, x1, y1, x2, y2, rgba, width=1.0):
    _f['dn_seg'](dn, point(x1, y1), point(x2, y2), float(width) / 2, color4f(rgba))


def draw_dot(dn, x, y, r, rgba, segments=None):
    """Filled circle. (CCDrawNode::drawDot draws a square in GD, so this is a polygon.)"""
    n = segments or max(12, min(40, int(r * 2.5)))
    pts = [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    draw_poly(dn, pts, rgba, 0.0)


def draw_poly(dn, pts, fill, border=0.0, border_rgba=None):
    n = len(pts)
    arr = create_string_buffer(struct.pack('<%df' % (2 * n), *[float(c) for p in pts for c in p]), 8 * n)
    _f['dn_poly'](dn, arr, n, color4f(fill), float(border), color4f(border_rgba or fill), 0)


# ---------------------------------------------------------------- input simulation
TOUCH_ID = 0x5D0          # touch id used for simulated taps (the real mouse uses 0)


def _glview():
    return _f['glview']()


def screen_to_frame(x, y):
    """Game point (y up) -> window pixel (y down), the way CCEGLView receives the mouse."""
    gl = _glview()
    vx, vy = struct.unpack('<ff', ctypes.string_at(_f['gl_viewport'](gl), 8))
    sx, sy = _f['gl_scale_x'](gl) or 1.0, _f['gl_scale_y'](gl) or 1.0
    h = win_size()[1]
    return float(x) * sx + vx, (h - float(y)) * sy + vy


def mouse_pos():
    """Mouse position in game coordinates (as gd.screen(): y is up)."""
    ret = create_string_buffer(8)
    _f['gl_mouse'](_glview(), ret)
    x, y = struct.unpack('<ff', ret.raw)
    return x, win_size()[1] - y


def sim_touch(kind, x, y, tid=TOUCH_ID):
    """kind: 'begin', 'move', 'end'. Goes through the normal cocos touch path (buttons react)."""
    fx, fy = screen_to_frame(x, y)
    ids, xs, ys = (c_int * 1)(int(tid)), (c_float * 1)(fx), (c_float * 1)(fy)
    _f['gl_touch_' + kind](_glview(), 1, ids, xs, ys, time.perf_counter())


# ---------------------------------------------------------------- textures
def texture(path):
    """CCTexture2D* for an image file (cached by cocos). None if it can not be loaded."""
    return _f['tex_add'](_f['tex_cache'](), _enc(os.path.abspath(path)), False) or None


def texture_size(tex):
    ret = create_string_buffer(8)
    _f['tex_size'](tex, ret)
    return struct.unpack('<ff', ret.raw)


def texture_smooth(tex, smooth=True):
    _f['tex_antialias' if smooth else 'tex_alias'](tex)


def forget_texture(path):
    _f['tex_remove_key'](_f['tex_cache'](), _enc(os.path.abspath(path)))


def frame_from_texture(tex, rect=None):
    """CCSpriteFrame* covering the whole texture (or rect=(x, y, w, h) in points)."""
    if rect is None:
        w, h = texture_size(tex)
        rect = (0.0, 0.0, w, h)
    buf = create_string_buffer(struct.pack('<4f', *[float(v) for v in rect]), 16)
    return _f['frame_with_tex'](tex, buf)


def add_frame(name, frame):
    _f['sfc_add'](_f['sfc'](), frame, _enc(name))


def remove_frame(name):
    _f['sfc_remove'](_f['sfc'](), _enc(name))


def add_frames_plist(path):
    _f['sfc_add_plist'](_f['sfc'](), _enc(os.path.abspath(path)))


def sprite_from_texture(tex):
    return _f['spr_with_tex'](tex) or None


def content_scale():
    return _f['scale_factor'](director()) or 1.0
