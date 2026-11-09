"""GD-looking UI: native GD alerts (FLAlertLayer) and extra popup widgets: list cells, progress bars,
stat rows, player icons, tabs."""
import ctypes
import traceback
from ctypes import c_void_p, c_bool

from . import _cocos as C
from . import _core as K
from . import _mem as M
from . import _native as N
from . import _ui as U

# ---------------------------------------------------------------- native FLAlertLayer
_CLICKED = ctypes.CFUNCTYPE(None, c_void_p, c_void_p, c_bool)
_alerts = {}       # protocol object address -> (object, vtable, callback, owner)


def _on_alert(this, alert, btn2):
    ent = _alerts.pop(this, None)
    if not ent or ent[2] is None:
        return
    cb, owner = ent[2], ent[3]
    K.later(lambda: U.flex_call(owner, cb, bool(btn2)))


_clicked_cb = _CLICKED(_on_alert)


def gd_alert(text, title='Info', button='OK', button2=None, on_close=None, width=360.0, owner='pymodder'):
    """A real GD alert. Text may use GD color tags: <cg>green</c> <cr>red</c> <cy>yellow</c> <cl>blue</c>
    <co>orange</c> <cp>pink</c>. on_close(second_button_pressed)."""
    proto = 0
    if on_close is not None:
        if len(_alerts) > 50:
            _alerts.clear()
        vt = (c_void_p * 2)(ctypes.cast(_clicked_cb, c_void_p).value, 0)
        obj = (c_void_p * 2)(ctypes.addressof(vt), 0)
        proto = ctypes.addressof(obj)
        _alerts[proto] = (obj, vt, on_close, owner)
    desc = M.StdString(str(text))
    try:
        enc = lambda s: str(s).encode('utf-8') if s is not None else None
        layer = N.function('FLAlertLayer::create')(proto or None, enc(title), desc.addr, enc(button),
                                                   enc(button2), float(width))
    finally:
        desc.free()
    if not layer:
        raise RuntimeError('FLAlertLayer::create failed')
    N.function('FLAlertLayer::show')(layer)
    from . import _nodes as Nd
    return Nd.Node(layer)


# ---------------------------------------------------------------- popup widgets
BROWN = ((161, 88, 44), (194, 114, 62))


class Cell(U.Widget):
    """A GD list row: icon, title, subtitle and an optional button on the right.
    callback() - click on the row; on_button() - click on the button."""
    interactive = True
    flex = True

    def __init__(self, title, subtitle='', icon=None, button=None, callback=None, on_button=None, index=None,
                 height=44, color=None, button_color='green', base_dir=None):
        super().__init__()
        self.title, self.subtitle, self.icon, self.button = str(title), str(subtitle or ''), icon, button
        self.callback, self.on_button, self.index, self.ch = callback, on_button, index, height
        self.bg_color, self.button_color, self.base_dir = color, button_color, base_dir
        self.btn = None
        self.part = None

    def build(self, width):
        self.w, self.h = width, self.ch
        w, h = width, self.ch
        i = self.index
        if i is None:
            items = self.popup.items
            i = sum(1 for x in items[:items.index(self)] if isinstance(x, Cell)) if self in items else 0
        col = self.bg_color or BROWN[i % 2]
        self._add(C.layer_color(tuple(col) + (255,), w, h - 1), -w / 2, -h / 2, z=1)
        left = -w / 2 + 8
        if self.icon:
            spr = C.sprite(K.builtin_icon(self.icon) or self.icon, self.base_dir or self.popup.base_dir)
            if spr:
                sw, sh = C.node_size(spr)
                s = (h - 12) / max(sw, sh, 1)
                C.fn('set_scale')(spr, float(s))
                self._add(spr, left + (h - 12) / 2, 0, z=2)
                left += h - 4
        right = 8
        if self.button:
            spr = C.button_sprite(str(self.button) if str(self.button).isascii() else '?', 0,
                                  U._texture(self.button_color), 'bigFont.fnt', 1.0, 0.0, False)
            if spr:
                bw, bh = C.node_size(spr)
                s = min(0.6, (h - 14) / max(bh, 1))
                C.fn('set_scale')(spr, float(s))
                self.btn = (spr, s, bw * s)
                self._add(spr, w / 2 - 8 - bw * s / 2, 0, z=3)
                right += bw * s + 8
        avail = w - (left + w / 2) - right
        dy = 7 if self.subtitle else 0
        t = C.Label(self.title, 0, 0, 0.5, 'bigFont.fnt' if self.title.isascii() else None, z=2,
                    parent=self.popup.box, anchor_xy=(0, 0.5))
        t.fit(avail)
        self.nodes.append([t.node, left, dy])
        if self.subtitle:
            s = C.Label(self.subtitle, 0, 0, 0.42, 'goldFont.fnt' if self.subtitle.isascii() else None, z=2,
                        parent=self.popup.box, anchor_xy=(0, 0.5))
            s.fit(avail)
            self.nodes.append([s.node, left, -10])

    def _part(self, x):
        if self.btn and x >= self.x + self.w / 2 - 12 - self.btn[2]:
            return 'button'
        return 'row'

    def down(self, x, y):
        self.part = self._part(x)
        if self.part == 'button':
            C.scale_bounce(self.btn[0], self.btn[1] * 1.2)

    def cancel(self):
        if self.part == 'button' and self.btn:
            C.scale_back(self.btn[0], self.btn[1])

    def up(self, x, y, inside):
        self.cancel()
        part, self.part = self.part, None
        if not inside or part != self._part(x):
            return
        if part == 'button':
            self._call(self.on_button)
        else:
            self._call(self.callback)


class ProgressBar(U.Widget):
    """A GD progress bar (like on the level page). value 0..1."""

    def __init__(self, value=0.0, color=(0, 255, 0), width=200, text=None, x=None, y=None):
        super().__init__(width, x, y)
        self._value, self.color, self._text = max(0.0, min(1.0, float(value))), color, text
        self.fill = self.label = None
        self.fw = self.fh = 0

    def build(self, width):
        bg = C.sprite('GJ_progressBar_001.png')
        if not bg:
            bg = C.layer_color((0, 0, 0, 125), self.req_w or 200, 16)
            self._add(bg, -(self.req_w or 200) / 2, -8)
            self.w, self.h = self.req_w or 200, 16
            return
        bw, bh = C.node_size(bg)
        s = (self.req_w or bw) / max(bw, 1)
        C.fn('set_scale')(bg, float(s))
        C.set_color(bg, (0, 0, 0))
        C.set_opacity(bg, 125)
        self._add(bg, 0, 0, z=2)
        self.w, self.h = bw * s, bh * s
        fill = C.sprite('GJ_progressBar_001.png')
        C.fn('set_scale_x')(fill, float(s * 0.992))
        C.fn('set_scale_y')(fill, float(s * 0.86))
        C.anchor(fill, 0.0, 0.5)
        C.set_color(fill, U.parse_color(self.color))
        self.fill, self.fw, self.fh = fill, bw, bh
        self._add(fill, -self.w * 0.992 / 2, 0, z=3)
        if self._text is not None:
            self.label = C.Label(str(self._text), 0, 0, 0.5, 'bigFont.fnt', z=4, parent=self.popup.box)
            self.label.fit(self.w - 10)
            self.nodes.append([self.label.node, 0, 1])
        self._apply()

    def _apply(self):
        if self.fill:
            C.texture_rect(self.fill, 0, 0, self.fw * self._value, self.fh)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = max(0.0, min(1.0, float(v)))
        if self.alive:
            self._apply()

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, v):
        self._text = str(v)
        if self.alive and self.label:
            self.label.text = self._text


# GD icons for stat rows
STAT_ICONS = {'stars': 'GJ_starsIcon_001.png', 'moons': 'GJ_moonsIcon_001.png', 'likes': 'GJ_likesIcon_001.png',
              'dislikes': 'GJ_dislikesIcon_001.png', 'downloads': 'GJ_downloadsIcon_001.png',
              'time': 'GJ_timeIcon_001.png', 'coins': 'GJ_coinsIcon_001.png', 'demons': 'GJ_demonIcon_001.png',
              'diamonds': 'GJ_diamondsIcon_001.png', 'orbs': 'currencyOrbIcon_001.png',
              'objects': 'GJ_hammerIcon_001.png', 'user_coins': 'GJ_coinsIcon2_001.png',
              'creator_points': 'GJ_hammerIcon_001.png', 'song': 'GJ_musicIcon_001.png'}


class Stat(U.Widget):
    """An icon + a value, like on the GD level page: Stat("downloads", "12 345")."""

    def __init__(self, icon, value, size=0.45, color=(255, 255, 255), x=None, y=None):
        super().__init__(None, x, y)
        self.icon, self._value, self.size, self.color = icon, str(value), size, color

    def build(self, width):
        name = STAT_ICONS.get(self.icon, self.icon)
        spr = C.sprite(name) if name else None
        iw = 0
        if spr:
            sw, sh = C.node_size(spr)
            s = 18 / max(sw, sh, 1)
            C.fn('set_scale')(spr, float(s))
            iw = 20
        lb = C.Label(self._value, 0, 0, self.size, 'bigFont.fnt' if self._value.isascii() else None, self.color,
                     z=2, parent=self.popup.box, anchor_xy=(0, 0.5))
        tw, th = lb.size()
        self.w, self.h = iw + 4 + tw, max(20, th)
        if spr:
            self._add(spr, -self.w / 2 + 9, 0)
        self.nodes.append([lb.node, -self.w / 2 + iw + 4, 0])


class Icon(U.Widget):
    """A GD player icon in a popup: Icon(kind="ship", icon=12, color1=3, color2=12, glow=False) or mine=True."""

    def __init__(self, icon=1, kind='cube', color1=None, color2=None, glow=None, mine=False, size=1.0,
                 callback=None, x=None, y=None):
        super().__init__(None, x, y)
        self.args = (icon, kind, color1, color2, glow, mine)
        self.size, self.callback = size, callback
        self.interactive = callback is not None
        self.player = None

    def build(self, width):
        from . import _levels as L
        self.player = L.PlayerIcon(*self.args)
        C.fn('set_scale')(self.player.ptr, float(self.size))
        self.w = self.h = 32 * self.size + 4
        self._add(self.player.ptr, 0, 0, z=3)

    def up(self, x, y, inside):
        if inside:
            self._call(self.callback)


class Tabs(U.Row):
    """Tab buttons. Everything added to the popup after the tabs is the page: build(popup, index) adds it
    again when the tab changes."""

    def __init__(self, names, build=None, value=0, gap=6, size=0.6):
        super().__init__(gap)
        self.names, self.build_page, self.index, self.size = list(names), build, int(value), size
        for i, n in enumerate(self.names):
            b = U.Button(n, (lambda i=i: self.select(i)), 'green' if i == self.index else 'grey', size)
            self.items.append(b)

    def select(self, index):
        p = self.popup
        if p is None:
            return
        self.index = int(index)
        for i, b in enumerate(self.items):
            b.color = 'green' if i == self.index else 'grey'
        if self in p.items:
            p.items[:] = p.items[:p.items.index(self) + 1]
        p.fixed[:] = [w for w in p.fixed if getattr(w, '_tab_keep', False)]
        if self.build_page:
            U.flex_call(p.owner, self.build_page, p, self.index)
        p.scroll_y = 0.0
        p.refresh()


def list_popup(title, items, on_pick=None, width=380, height=260, owner='pymodder', base_dir=None, button=None):
    """A GD-style list. items: strings or dicts {title, subtitle, icon, button, value}.
    on_pick(item, index) when a row (or its button) is clicked."""
    p = U.Popup(title, width, height, owner=owner, base_dir=base_dir)
    for i, it in enumerate(items):
        d = it if isinstance(it, dict) else {'title': str(it)}
        cb = (lambda i=i, d=it: (p.close(), U.flex_call(owner, on_pick, d, i))) if on_pick else None
        p.add(Cell(d.get('title', ''), d.get('subtitle', ''), d.get('icon'), d.get('button', button), cb, cb,
                   index=i, base_dir=base_dir))
    p.show()
    return p
