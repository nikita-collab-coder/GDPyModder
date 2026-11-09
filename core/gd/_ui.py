"""PyModder UI: popups, buttons, toggles, sliders, text fields.
Drawn with cocos2d nodes; all input (mouse, keys, text, wheel) is handled here in Python."""
import ctypes
import inspect
import os
import time

from . import _cocos as C
from . import _mem as M

Z_POPUP = 20000
GAP = 6
stack = []              # open popups, last = top
screen_buttons = []     # ScreenButton (buttons on game layers, e.g. the pause menu)
is_overlay = lambda node: False      # set by _core: PyModder labels / drawings / sprites on the scene
_route = {}             # CCTouch* -> 'ui' | 'game' | ScreenButton
_dedup = {'esc': 0.0, 'back': 0.0}
_capture = [None]       # waiting for "press a key"
_pending_char = [None]
_ime_seen = [False]
CFG = {'menu_key': 0x75, 'invert_scroll': False}
hooks = {'report': None, 'menu_key': None}

ESC, BACKSPACE, ENTER, TAB, KEY_V = 0x1B, 0x08, 0x0D, 0x09, 0x56
TEXTURES = {'green': 'GJ_button_01.png', 'pink': 'GJ_button_02.png', 'blue': 'GJ_button_03.png',
            'grey': 'GJ_button_04.png', 'gray': 'GJ_button_04.png', 'red': 'GJ_button_05.png',
            'dark': 'GJ_button_06.png'}


def _user32():
    return ctypes.windll.user32


def _report(owner, where):
    if hooks['report']:
        hooks['report'](owner, where)
    else:
        import traceback
        traceback.print_exc()


_argc = {}


def flex_call(owner, func, *args):
    """Call func with as many args as it accepts (so `def cb():` and `def cb(value):` both work)."""
    if func is None:
        return None
    try:
        n = _argc.get(func)
        if n is None:
            try:
                ps = inspect.signature(func).parameters.values()
                if any(p.kind == p.VAR_POSITIONAL for p in ps):
                    n = 99
                else:
                    n = sum(1 for p in ps if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))
            except (TypeError, ValueError):
                n = 99
            _argc[func] = n
        return func(*args[:n])
    except Exception:
        _report(owner, 'ui')
    return None


def _texture(color):
    if isinstance(color, int):
        return 'GJ_button_%02d.png' % color
    return TEXTURES.get(str(color).lower(), str(color))


# ================================================================ widgets
class Widget:
    """Base of all popup elements. x, y = center on screen; w, h = size."""
    interactive = False
    flex = False          # takes the free width of the row

    def __init__(self, width=None, x=None, y=None):
        self.popup = None
        self.req_w = width
        self.w, self.h = width or 0, 0
        self.x = self.y = 0.0
        self.fixed = None if x is None and y is None else (x or 0, y or 0)
        self.nodes = []
        self.shown = True
        self.enabled = True

    # --- building
    @property
    def alive(self):
        return bool(self.popup and self.popup.box)

    def _add(self, node, dx=0.0, dy=0.0, z=2, parent=None):
        if node:
            C.fn('add_child')(parent or self.popup.box, node, z)
            self.nodes.append([node, dx, dy])
        return node

    def _set_offset(self, node, dx, dy):
        for n in self.nodes:
            if n[0] == node:
                n[1], n[2] = dx, dy
        C.fn('set_pos')(node, float(self.x + dx), float(self.y + dy))

    def build(self, width):
        """Create cocos nodes. width = available width (for flex widgets)."""

    def place(self, x, y):
        self.x, self.y = x, y
        for node, dx, dy in self.nodes:
            C.fn('set_pos')(node, float(x + dx), float(y + dy))

    def show(self, visible):
        visible = bool(visible)
        if visible != self.shown:
            self.shown = visible
            for node, _, _ in self.nodes:
                C.fn('set_visible')(node, visible)

    def contains(self, x, y, pad=2):
        return abs(x - self.x) <= self.w / 2 + pad and abs(y - self.y) <= self.h / 2 + pad

    def widget_at(self, x, y):
        return self if self.interactive and self.shown and self.enabled and self.contains(x, y) else None

    # --- input
    def down(self, x, y): pass
    def drag(self, x, y): pass
    def up(self, x, y, inside): pass
    def cancel(self): pass
    def tick(self, dt): pass

    def _call(self, func, *args):
        owner = self.popup.owner if self.popup else 'pymodder'
        return flex_call(owner, func, *args)


class Space(Widget):
    def __init__(self, height=8):
        super().__init__()
        self.h = height


class Line(Widget):
    def __init__(self, color=(255, 255, 255, 50)):
        super().__init__()
        self.color, self.h = color, 6
        self.flex = True

    def build(self, width):
        self.w = width
        self._add(C.layer_color(self.color, width, 1), -width / 2, 0, z=1)


class Text(Widget):
    def __init__(self, text, size=0.5, color=(255, 255, 255), align='center', font=None, width=None, wrap=True,
                 x=None, y=None):
        super().__init__(width, x, y)
        self._text, self.size, self.color, self.align, self.font, self.wrap = str(text), size, color, align, font, wrap
        self.flex = wrap and width is None
        self.lb = None

    def build(self, width):
        self.w = self.req_w or width
        ax = {'left': 0.0, 'right': 1.0}.get(self.align, 0.5)
        mk = lambda wrap_w: C.Label(self._text, 0, 0, self.size, self.font, self.color, z=2, parent=self.popup.box,
                                    width=wrap_w, align=self.align, anchor_xy=(ax, 0.5))
        self.lb = mk(None)
        tw, th = self.lb.size()
        if self.wrap and self.w > 0 and tw > self.w:
            C.remove(self.lb.node)
            self.lb = mk(self.w)
            self.lb.fit(self.w)          # a single very long word
            tw, th = self.lb.size()
        if not self.wrap:
            self.w = tw
        self.h = max(th, 8)
        self.nodes.append([self.lb.node, (ax - 0.5) * self.w, 0])

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)
        if self.alive and self.lb:
            old = self.lb.node
            self.lb.text = self._text
            if self.lb.node != old:
                for n in self.nodes:
                    if n[0] == old:
                        n[0] = self.lb.node
                self.place(self.x, self.y)
                if not self.shown:
                    C.fn('set_visible')(self.lb.node, False)

    def set_color(self, rgb):
        self.color = rgb
        if self.alive and self.lb:
            self.lb.color = rgb


class Button(Widget):
    """GD style button. text — caption; image — sprite frame / .png instead of a caption."""
    interactive = True

    def __init__(self, text='', callback=None, color='green', size=0.8, width=None, image=None, font='goldFont.fnt',
                 x=None, y=None, base_dir=None):
        super().__init__(width, x, y)
        self._text, self.callback, self.color, self.size, self.image, self.font = \
            str(text), callback, color, size, image, font
        self.base_dir = base_dir
        self.spr = None
        self._pressed = False

    def build(self, width):
        spr = None
        if self.image:
            spr = C.sprite(self.image, self.base_dir)
            if spr and self.req_w:
                sw, sh = C.node_size(spr)
                self.size = self.req_w / max(sw, sh, 1)
        if not spr:
            text = self._text or ' '
            if text.isascii():
                w = int(self.req_w / self.size) if self.req_w else 0
                spr = C.button_sprite(text, w, _texture(self.color), self.font, 1.0, 0.0, bool(w))
            else:
                probe = C.Label(text, 0, 0, 0.55, 'Arial')
                tw, th = probe.size()
                w = int(max(tw + 26, (self.req_w or 0) / self.size, 40))
                spr = C.button_sprite(' ', w, _texture(self.color), self.font, 1.0, 0.0, True)
                if spr:
                    bw, bh = C.node_size(spr)
                    probe.move(bw / 2, bh / 2 + 1)
                    C.fn('add_child')(spr, probe.node, 5)
        if not spr:
            raise RuntimeError('cannot create button %r' % self._text)
        self.spr = spr
        C.fn('set_scale')(spr, float(self.size))
        bw, bh = C.node_size(spr)
        self.w, self.h = bw * self.size, bh * self.size
        self._add(spr)

    def down(self, x, y):
        self._pressed = True
        C.scale_bounce(self.spr, self.size * 1.2)

    def drag(self, x, y):
        inside = self.contains(x, y, 6)
        if inside != self._pressed:
            self._pressed = inside
            if inside:
                C.scale_bounce(self.spr, self.size * 1.2)
            else:
                C.scale_back(self.spr, self.size)

    def cancel(self):
        self._pressed = False
        C.scale_back(self.spr, self.size)

    def up(self, x, y, inside):
        self.cancel()
        if inside:
            self._call(self.callback)


class Image(Button):
    def __init__(self, name, callback=None, size=None, x=None, y=None, base_dir=None):
        super().__init__('', callback, image=name, x=x, y=y, base_dir=base_dir, size=1.0, width=size)
        self.interactive = callback is not None

    def down(self, x, y):
        if self.callback:
            super().down(x, y)


class _Check:
    """Checkbox sprite (GD frames, or drawn if they are missing)."""
    ON, OFF = 'GJ_checkOn_001.png', 'GJ_checkOff_001.png'

    def __init__(self, value, size=26):
        self.size = size
        self.frames = C.frame_exists(self.ON) and C.frame_exists(self.OFF)
        if self.frames:
            self.node = C.sprite(self.ON if value else self.OFF)
            w, h = C.node_size(self.node)
            self.scale = size / max(w, h, 1)
            C.fn('set_scale')(self.node, float(self.scale))
        else:
            self.node = C.draw_node()
            self.scale = 1.0
        self.set(value)

    def set(self, value):
        if self.frames:
            fr = C.fn('sfc_get')(C.fn('sfc')(), (self.ON if value else self.OFF).encode())
            if fr:
                C.fn('spr_frame_set')(self.node, fr)
        else:
            s = self.size / 2
            C.fn('dn_clear')(self.node)
            C.draw_poly(self.node, [(-s, -s), (s, -s), (s, s), (-s, s)], (0, 0, 0, 120), 2, (255, 255, 255, 220))
            if value:
                C.draw_line(self.node, -s * .5, 0, -s * .1, -s * .45, (120, 255, 80), 4)
                C.draw_line(self.node, -s * .1, -s * .45, s * .55, s * .5, (120, 255, 80), 4)


class Toggle(Widget):
    interactive = True
    flex = True

    def __init__(self, text, value=False, callback=None, width=None, x=None, y=None, size=0.45):
        super().__init__(width, x, y)
        self.flex = width is None
        self._text, self._value, self.callback, self.size = str(text), bool(value), callback, size
        self.check = None

    def build(self, width):
        self.w = self.req_w or width
        self.h = 30
        self.check = _Check(self._value)
        self._add(self.check.node, self.w / 2 - 15, 0)
        self.lb = C.Label(self._text, 0, 0, self.size, None, (255, 255, 255), z=2, parent=self.popup.box,
                          anchor_xy=(0, 0.5))
        self.lb.fit(self.w - 40)
        self.nodes.append([self.lb.node, -self.w / 2 + 2, 0])

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = bool(v)
        if self.alive and self.check:
            self.check.set(self._value)

    def down(self, x, y):
        if self.check.frames:
            C.scale_bounce(self.check.node, self.check.scale * 1.2)

    def cancel(self):
        if self.check.frames:
            C.scale_back(self.check.node, self.check.scale)

    def up(self, x, y, inside):
        self.cancel()
        if inside:
            self.value = not self._value
            self._call(self.callback, self._value)


class Slider(Widget):
    """GD slider: "slidergroove.png" + "sliderBar.png" fill + "sliderthumb.png" (as GD's own Slider class).
    Falls back to a drawn slider if the textures are missing."""
    interactive = True
    flex = True
    TRAVEL = 200.0       # thumb path in GD's Slider, in groove points (scaled with the groove)

    def __init__(self, text, value=0.0, min=0.0, max=1.0, callback=None, step=None, fmt=None, width=None,
                 on_move=None, x=None, y=None):
        super().__init__(width, x, y)
        self.flex = width is None
        self._text, self.min, self.max, self.callback, self.on_move = str(text), min, max, callback, on_move
        self.is_int = step is None and all(isinstance(v, int) and not isinstance(v, bool) for v in (min, max, value))
        self.step = step if step is not None else (1 if self.is_int else None)
        self.fmt = fmt
        self._value = self._clamp(value)
        self.dn = self.lb = None
        self.groove = self.bar = self.thumb = self.thumb_sel = None
        self.scale, self.bar_w, self._dragging = 1.0, 0.0, False

    def _clamp(self, v):
        lo, hi = (self.min, self.max) if self.min <= self.max else (self.max, self.min)
        v = lo if v is None else max(lo, min(hi, v))
        if self.step:
            v = round(lo + round((v - lo) / self.step) * self.step, 9)
            v = max(lo, min(hi, v))
        return int(round(v)) if self.is_int else float(v)

    def _caption(self):
        if self.fmt:
            val = self.fmt(self._value) if callable(self.fmt) else self.fmt % self._value
        elif self.is_int:
            val = str(self._value)
        else:
            val = ('%.2f' % self._value).rstrip('0').rstrip('.')
        return '%s: %s' % (self._text, val) if self._text else val

    def _gd_parts(self):
        """groove, bar, thumb, thumb_sel - GD textures; None if any is missing."""
        names = ('slidergroove.png', 'sliderBar.png', 'sliderthumb.png', 'sliderthumbsel.png')
        if not C.res_path('sliderBar.png') or not all(C.res_path(n) or C.frame_exists(n) for n in names):
            return None          # the bar must be its own texture (it is tiled with GL_REPEAT)
        C.repeat_texture('sliderBar.png')
        # GD creates them from the Resources files (CCSprite::create / CCMenuItemImage::create)
        parts = [C.fn('spr_create')(n.encode()) if C.res_path(n) else C.sprite(n) for n in names]
        return parts if all(parts) else None

    def build(self, width):
        self.w = self.req_w or width
        dy = -9 if self._text else 0
        if self._text:
            self.lb = C.Label(self._caption(), 0, 0, 0.42, None, (255, 255, 255), z=2, parent=self.popup.box,
                              anchor_xy=(0, 0.5))
            self.nodes.append([self.lb.node, -self.w / 2 + 2, 10])
        parts = None
        try:
            parts = self._gd_parts()
        except Exception:
            parts = None
        if parts:
            self.groove, self.bar, self.thumb, self.thumb_sel = parts
            gw, gh = C.node_size(self.groove)
            self.bar_w = max(gw - 4, 1)
            self.scale = s = max(0.3, min(1.0, (self.w - 12) / max(gw, 1)))
            C.fn('set_scale')(self.groove, float(s))
            self._add(self.groove, 0, dy, z=2)
            C.fn('set_anchor')(self.bar, C.point(0, 0))
            C.fn('add_child')(self.groove, self.bar, -1)
            C.fn('set_pos')(self.bar, 2.0, 4.0)
            for t in (self.thumb, self.thumb_sel):
                C.fn('set_scale')(t, float(s))
                self._add(t, 0, dy, z=3)
            C.fn('set_visible')(self.thumb_sel, False)
            self.h = (44 if self._text else 30) if gh * s < 22 else gh * s + (24 if self._text else 8)
        else:
            self.h = 40 if self._text else 26
            self.dn = C.draw_node()
            self._add(self.dn, 0, dy)
        self._dy = dy
        self._redraw()

    def _ratio(self):
        span = (self.max - self.min) or 1
        return max(0.0, min(1.0, (self._value - self.min) / span))

    def _half(self):
        return self.TRAVEL * self.scale / 2 if self.groove else self.w / 2 - 10

    def _redraw(self):
        if not self.alive:
            return
        r = self._ratio()
        if self.groove:
            tx = (r - 0.5) * self.TRAVEL * self.scale
            for t in (self.thumb, self.thumb_sel):
                self._set_offset(t, tx, self._dy)
            C.fn('set_visible')(self.thumb, self.shown and not self._dragging)
            C.fn('set_visible')(self.thumb_sel, self.shown and self._dragging)
            C.texture_rect(self.bar, 0, 0, min(self.bar_w, self.bar_w * r), 8)
        else:
            dn, x0, x1 = self.dn, -self.w / 2 + 10, self.w / 2 - 10
            xv = x0 + (x1 - x0) * r
            C.fn('dn_clear')(dn)
            C.draw_line(dn, x0, 0, x1, 0, (0, 0, 0, 140), 10)
            C.draw_line(dn, x0, 0, xv, 0, (110, 230, 90, 255), 6)
            C.draw_dot(dn, xv, 0, 9, (255, 255, 255, 255))
            C.draw_dot(dn, xv, 0, 6, (90, 200, 70, 255))
        if self.lb:
            self.lb.text = self._caption()

    def show(self, visible):
        super().show(visible)
        if self.groove and self.alive:
            C.fn('set_visible')(self.thumb, self.shown and not self._dragging)
            C.fn('set_visible')(self.thumb_sel, self.shown and self._dragging)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = self._clamp(v)
        self._redraw()

    def _set_from_x(self, x):
        half = self._half()
        x0, x1 = self.x - half, self.x + half
        r = 0.0 if x1 <= x0 else max(0.0, min(1.0, (x - x0) / (x1 - x0)))
        old = self._value
        self._value = self._clamp(self.min + (self.max - self.min) * r)
        if self._value != old:
            self._redraw()
            self._call(self.on_move, self._value)

    def down(self, x, y):
        self._start = self._value
        self._dragging = True
        self._set_from_x(x)
        self._redraw()

    def drag(self, x, y):
        self._set_from_x(x)

    def cancel(self):
        if self._dragging:
            self._dragging = False
            self._redraw()

    def up(self, x, y, inside):
        self.cancel()
        if self._value != getattr(self, '_start', None):
            self._call(self.callback, self._value)


class Input(Widget):
    """Text field. callback(text) on Enter / when focus is lost, on_change(text) on every edit."""
    interactive = True
    flex = True

    def __init__(self, value='', placeholder='', callback=None, on_change=None, width=None, numeric=False,
                 max_len=100, x=None, y=None):
        super().__init__(width, x, y)
        self.flex = width is None
        self._text, self.placeholder, self.callback, self.on_change = str(value), str(placeholder), callback, on_change
        self.numeric, self.max_len = numeric, max_len
        self.focused = False
        self.on_enter = None        # func(text) when Enter is pressed
        self._blink = 0.0
        self.lb = self.cursor = self.bg = None

    def build(self, width):
        self.w = self.req_w or width
        self.h = 30
        self.bg = self._add(C.layer_color((0, 0, 0, 100), self.w, 26), -self.w / 2, -13, z=1)
        self.lb = C.Label(' ', 0, 0, 0.42, None, (255, 255, 255), z=2, parent=self.popup.box, anchor_xy=(0, 0.5))
        self.nodes.append([self.lb.node, -self.w / 2 + 6, 0])
        self.cursor = self._add(C.layer_color((255, 255, 255, 230), 2, 16), 0, -8, z=3)
        C.fn('set_visible')(self.cursor, False)
        self._refresh()

    def _refresh(self):
        if not self.alive:
            return
        old = self.lb.node
        maxw = self.w - 14
        if self._text:
            shown = self._text
            self.lb.text = shown
            self.lb.color = (255, 255, 255)
            while self.lb.size()[0] > maxw and len(shown) > 1:
                shown = shown[max(1, len(shown) // 8):]
                self.lb.text = shown
        else:
            self.lb.text = self.placeholder or ' '
            self.lb.color = (150, 150, 150)
        if self.lb.node != old:
            for n in self.nodes:
                if n[0] == old:
                    n[0] = self.lb.node
            C.fn('set_pos')(self.lb.node, float(self.x - self.w / 2 + 6), float(self.y))
            C.fn('set_visible')(self.lb.node, self.shown)
        tw = self.lb.size()[0] if self._text else 0
        self._set_offset(self.cursor, -self.w / 2 + 7 + tw, -8)
        self.bg and C.set_opacity(self.bg, 150 if self.focused else 100, 'layer')

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)[:self.max_len]
        self._refresh()

    value = text

    def focus(self, on=True):
        if self.focused == on:
            return
        if on and self.popup:
            for w in self.popup.all_widgets():
                if isinstance(w, Input) and w is not self:
                    w.focus(False)
        self.focused = on
        self._blink = 0.0
        if self.alive:
            C.fn('set_visible')(self.cursor, on and self.shown)
            self._refresh()
        if not on:
            self._call(self.callback, self._text)

    def insert(self, s):
        s = ''.join(ch for ch in s if ch >= ' ' and ch != '\x7f')
        if self.numeric:
            s = ''.join(ch for ch in s if ch in '0123456789.-')
        if not s:
            return
        self._text = (self._text + s)[:self.max_len]
        self._refresh()
        self._call(self.on_change, self._text)

    def backspace(self):
        if self._text:
            self._text = self._text[:-1]
            self._refresh()
            self._call(self.on_change, self._text)

    def tick(self, dt):
        if self.focused and self.alive:
            self._blink += dt
            C.fn('set_visible')(self.cursor, self.shown and (self._blink % 1.0) < 0.55)

    def show(self, visible):
        super().show(visible)
        if self.alive and not (visible and self.focused):
            C.fn('set_visible')(self.cursor, False)

    def up(self, x, y, inside):
        if inside:
            self.focus(True)


class Choice(Widget):
    """Text on the left, a button on the right that cycles through options."""
    interactive = True
    flex = True

    def __init__(self, text, options, value=None, callback=None, width=None, x=None, y=None):
        super().__init__(width, x, y)
        self.flex = width is None
        self._text, self.options, self.callback = str(text), list(options), callback
        self._value = value if value in self.options else (self.options[0] if self.options else None)
        self.btn = None

    def _make_button(self):
        if self.btn:
            for n in list(self.nodes):
                if n[0] == self.btn.spr:
                    self.nodes.remove(n)
            C.remove(self.btn.spr)
        b = Button(str(self._value), None, 'grey', 0.6, font='bigFont.fnt')
        b.popup = self.popup
        b.build(0)
        self.btn = b
        self.nodes.append([b.spr, self.w / 2 - b.w / 2 - 2, 0])
        C.fn('set_pos')(b.spr, float(self.x + self.w / 2 - b.w / 2 - 2), float(self.y))
        C.fn('set_visible')(b.spr, self.shown)

    def build(self, width):
        self.w = self.req_w or width
        self.h = 30
        self.btn = None
        self.lb = C.Label(self._text, 0, 0, 0.45, None, (255, 255, 255), z=2, parent=self.popup.box,
                          anchor_xy=(0, 0.5))
        self.nodes.append([self.lb.node, -self.w / 2 + 2, 0])
        self._make_button()
        self.lb.fit(self.w - self.btn.w - 12)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
        if self.alive:
            self._make_button()

    def down(self, x, y):
        self.btn.down(x, y)

    def cancel(self):
        self.btn.cancel()

    def up(self, x, y, inside):
        self.btn.cancel()
        if inside and self.options:
            i = self.options.index(self._value) if self._value in self.options else -1
            self.value = self.options[(i + 1) % len(self.options)]
            self._call(self.callback, self._value)


class KeyBind(Choice):
    """Text on the left, a button with a key name; click it and press a key."""

    def __init__(self, text, value='F1', callback=None, width=None, x=None, y=None):
        super().__init__(text, [value], value, callback, width, x, y)

    def up(self, x, y, inside):
        self.btn.cancel()
        if not inside:
            return
        old = self._value
        self.value = '...'

        def got(name):
            if name is None or name == 'ESC':
                self.value = old
            else:
                self.value = name
                if name != old:
                    self._call(self.callback, name)
        capture_key(got)


def parse_color(v):
    """(r, g, b) from a tuple / list or "#rrggbb"."""
    if isinstance(v, str):
        h = v.strip().lstrip('#')
        if len(h) == 3:
            h = ''.join(c * 2 for c in h)
        if len(h) != 6:
            raise ValueError('color must be "#rrggbb" or (r, g, b)')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    if isinstance(v, (tuple, list)) and len(v) >= 3:
        return tuple(max(0, min(255, int(round(float(c))))) for c in v[:3])
    raise ValueError('color must be "#rrggbb" or (r, g, b)')


def hex_color(rgb):
    return '#%02X%02X%02X' % tuple(rgb[:3])


class Swatch(Widget):
    """A color sample (rectangle with a light frame)."""
    flex = True

    def __init__(self, value=(255, 255, 255), width=None, height=30, x=None, y=None):
        super().__init__(width, x, y)
        self.flex = width is None
        self._value, self.sh = parse_color(value), height
        self.inner = None

    def build(self, width):
        self.w = self.req_w or width
        self.h = self.sh + 4
        w, h = self.w, self.sh
        self._add(C.layer_color((255, 255, 255, 220), w, h), -w / 2, -h / 2, z=2)
        self._add(C.layer_color((0, 0, 0, 255), w - 4, h - 4), -w / 2 + 2, -h / 2 + 2, z=3)
        self.inner = self._add(C.layer_color(self._value + (255,), w - 8, h - 8), -w / 2 + 4, -h / 2 + 4, z=4)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = parse_color(v)
        if self.alive and self.inner:
            C.set_color(self.inner, self._value, 'layer')


class ColorButton(Widget):
    """"Title  [color]" - a click opens the color picker. callback((r, g, b)) after OK."""
    interactive = True
    flex = True

    def __init__(self, text, value=(255, 255, 255), callback=None, width=None, x=None, y=None, size=0.45):
        super().__init__(width, x, y)
        self.flex = width is None
        self._text, self._value, self.callback, self.size = str(text), parse_color(value), callback, size
        self.sw = None
        self.lb = None

    def build(self, width):
        self.w = self.req_w or width
        self.h = 30
        self.sw = Swatch(self._value, 40, 22)
        self.sw.popup = self.popup
        self.sw.build(40)
        for n in self.sw.nodes:
            n[1] += self.w / 2 - 22
        self.nodes.extend(self.sw.nodes)
        self.lb = C.Label(self._text, 0, 0, self.size, None, (255, 255, 255), z=2, parent=self.popup.box,
                          anchor_xy=(0, 0.5))
        self.lb.fit(self.w - 54)
        self.nodes.append([self.lb.node, -self.w / 2 + 2, 0])

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = parse_color(v)
        if self.sw:
            self.sw.value = self._value

    def down(self, x, y):
        if self.sw and self.sw.inner:
            C.set_opacity(self.sw.inner, 170, 'layer')

    def cancel(self):
        if self.sw and self.sw.inner and self.alive:
            C.set_opacity(self.sw.inner, 255, 'layer')

    def up(self, x, y, inside):
        self.cancel()
        if inside:
            def done(rgb):
                self.value = rgb
                self._call(self.callback, self._value)
            pick_color(self._value, done, self._text or 'Color', owner=self.popup.owner if self.popup else 'pymodder')


def pick_color(value=(255, 255, 255), on_done=None, title='Color', owner='pymodder', on_cancel=None):
    """Color picker popup: red / green / blue sliders, a preview and a #hex field. on_done((r, g, b))."""
    rgb = list(parse_color(value))
    p = Popup(title or 'Color', 300, owner=owner)
    sw = p.add(Swatch(rgb, height=34))
    sliders = []
    hexf = [None]

    def refresh(skip_hex=False):
        sw.value = rgb
        if hexf[0] and not skip_hex:
            hexf[0].text = hex_color(rgb)

    def mover(i):
        def f(v):
            rgb[i] = int(v)
            refresh()
        return f

    for i, name in enumerate(('Red', 'Green', 'Blue')):
        sliders.append(p.slider(name, rgb[i], 0, 255, mover(i), on_move=mover(i)))

    def from_hex(text):
        try:
            c = parse_color(text)
        except ValueError:
            hexf[0].text = hex_color(rgb)
            return
        rgb[:] = list(c)
        for sl, v in zip(sliders, rgb):
            sl.value = v
        refresh(True)

    def ok():
        p.close()
        flex_call(owner, on_done, tuple(rgb))

    def cancel():
        p.close()
        flex_call(owner, on_cancel)

    p.space(2)
    with p.row(8):
        hexf[0] = p.input(hex_color(rgb), '#RRGGBB', from_hex, width=96, max_len=7)
        p.button('Cancel', cancel, 'grey', 0.6)
        p.button('OK', ok, size=0.6)
    return p.show()


class Row(Widget):
    """Widgets side by side (use `with popup.row():`)."""
    interactive = True

    def __init__(self, gap=8, x=None, y=None):
        super().__init__(None, x, y)
        self.items, self.gap = [], gap

    def build(self, width):
        fixed = [w for w in self.items if not w.flex]
        flex = [w for w in self.items if w.flex]
        for w in fixed:
            w.popup = self.popup
            w.build(0)
        used = sum(w.w for w in fixed) + self.gap * (len(self.items) - 1)
        each = max(40, (width - used) / len(flex)) if flex else 0
        for w in flex:
            w.popup = self.popup
            w.build(each)
        self.w = sum(w.w for w in self.items) + self.gap * (len(self.items) - 1)
        self.h = max([w.h for w in self.items] or [0])

    def place(self, x, y):
        self.x, self.y = x, y
        cx = x - self.w / 2
        for w in self.items:
            w.place(cx + w.w / 2, y)
            cx += w.w + self.gap

    def show(self, visible):
        self.shown = visible
        for w in self.items:
            w.show(visible)

    def widget_at(self, x, y):
        for w in self.items:
            r = w.widget_at(x, y)
            if r:
                return r
        return None

    def tick(self, dt):
        for w in self.items:
            w.tick(dt)


class _RowCtx:
    def __init__(self, popup, row):
        self.popup, self.row = popup, row

    def __enter__(self):
        self.popup._rows.append(self.row)
        return self.row

    def __exit__(self, *exc):
        self.popup._rows.pop()


# ================================================================ popup
class Popup:
    """A window on top of the game.

        p = gd.Popup("My mod")
        p.text("Hello!")
        p.toggle("Enabled", True, lambda v: print(v))
        p.button("OK", p.close)
        p.show()
    """

    def __init__(self, title='', width=320, height=None, on_close=None, bg='GJ_square01.png', dim=120,
                 close_button=True, owner='pymodder', base_dir=None, footer=0):
        self.title, self.width, self.height = str(title or ''), width, height
        self.footer = footer
        self.on_close, self.bg_file, self.dim, self.close_button = on_close, bg, dim, close_button
        self.owner, self.base_dir = owner, base_dir
        self.items = []         # flow widgets
        self.fixed = []         # widgets with explicit x/y
        self._rows = []
        self.root = self.box = None
        self.scroll_y = 0.0
        self.max_scroll = 0.0
        self.is_open = False
        self._active = None
        self._drag = None
        self._close_spr = None
        self._close_pressed = False
        self._scrollbar = None

    # ------------------------------------------------ builders
    def add(self, widget):
        widget.popup = self
        if self._rows and widget.fixed is None:
            self._rows[-1].items.append(widget)
        elif widget.fixed is not None:
            self.fixed.append(widget)
        else:
            self.items.append(widget)
        return widget

    def text(self, text, size=0.5, color=(255, 255, 255), align='center', font=None, **kw):
        return self.add(Text(text, size, color, align, font, **kw))

    def button(self, text, callback=None, color='green', size=0.8, **kw):
        kw.setdefault('base_dir', self.base_dir)
        return self.add(Button(text, callback, color, size, **kw))

    def image(self, name, callback=None, size=None, **kw):
        kw.setdefault('base_dir', self.base_dir)
        return self.add(Image(name, callback, size, **kw))

    def toggle(self, text, value=False, callback=None, **kw):
        return self.add(Toggle(text, value, callback, **kw))

    def slider(self, text, value=0.0, min=0.0, max=1.0, callback=None, **kw):
        return self.add(Slider(text, value, min, max, callback, **kw))

    def input(self, value='', placeholder='', callback=None, **kw):
        return self.add(Input(value, placeholder, callback, **kw))

    def choice(self, text, options, value=None, callback=None, **kw):
        return self.add(Choice(text, options, value, callback, **kw))

    def keybind(self, text, value='F1', callback=None, **kw):
        return self.add(KeyBind(text, value, callback, **kw))

    def color(self, text, value=(255, 255, 255), callback=None, **kw):
        """A color row: a click opens the color picker, callback((r, g, b))."""
        return self.add(ColorButton(text, value, callback, **kw))

    def swatch(self, value=(255, 255, 255), **kw):
        return self.add(Swatch(value, **kw))

    def space(self, height=8):
        return self.add(Space(height))

    def line(self):
        return self.add(Line())

    def row(self, gap=8, x=None, y=None):
        r = Row(gap, x, y)
        self.add(r)
        return _RowCtx(self, r)

    def clear(self):
        """Remove all elements (call refresh()/show() after adding new ones)."""
        if self.box:
            for w in self.all_widgets():
                for n, _, _ in w.nodes:
                    C.remove(n)
                w.nodes = []
        self.items, self.fixed, self._active, self._rows = [], [], None, []

    def all_widgets(self, top_level=False):
        out = []
        for w in self.items + self.fixed:
            out.append(w)
            if isinstance(w, Row) and not top_level:
                out.extend(w.items)
        return out

    # ------------------------------------------------ show / close
    def show(self):
        """Show the window (can be called from anywhere)."""
        if self.is_open:
            return self
        self.is_open = True
        from . import _core
        _core.when_scene_ready(self._build)
        return self

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        for w in self.all_widgets():
            if isinstance(w, Input) and w.focused:
                w.focused = False
        if self in stack:
            stack.remove(self)
        if self.root:
            root, self.root, self.box = self.root, None, None
            C.remove(root, True)
            C.fn('release')(root)
        if self.on_close:
            flex_call(self.owner, self.on_close)

    def _build(self):
        if not self.is_open or self.root:
            return
        scene = C.running_scene()
        if not scene:
            self.is_open = False
            return
        W, H = C.win_size()
        self.root = C.layer_color((0, 0, 0, 0), W, H)
        C.fn('retain')(self.root)
        C.fn('add_child')(scene, self.root, Z_POPUP + len(stack))
        if self.dim:
            C.run(self.root, C.fn('fade_to')(0.14, int(self.dim)))
        self.box = C.layer_color((0, 0, 0, 0), W, H)
        C.fn('add_child')(self.root, self.box, 1)
        stack.append(self)
        try:
            self._layout(first=True)
        except Exception:
            _report(self.owner, 'popup')
            self.close()
            return
        C.fn('set_scale')(self.box, 0.1)
        C.run(self.box, C.fn('ease_elastic_out')(C.fn('scale_to')(0.5, 1.0), 0.6))

    def refresh(self):
        """Rebuild the popup after changing its elements."""
        if not self.box:
            return
        # drop all nodes of the box and build again
        box = self.box
        W, H = C.win_size()
        self.box = C.layer_color((0, 0, 0, 0), W, H)
        C.fn('add_child')(self.root, self.box, 1)
        C.remove(box, True)
        for w in self.all_widgets():
            w.nodes = []
        self._active = None
        self._layout(first=False)

    def _layout(self, first):
        W, H = C.win_size()
        cx, cy = W / 2, H / 2
        cw = self.width - 32
        for w in self.items + self.fixed:
            w.popup = self
            w.nodes = []
            w.shown = True
            w.build(cw)
        gaps = GAP * max(0, len(self.items) - 1)
        content_h = sum(w.h for w in self.items) + gaps
        head = 42 if self.title else 18
        foot = 14 + self.footer
        height = self.height or min(H - 24, max(110, content_h + head + foot))
        self.cur_h = height
        top, bottom = cy + height / 2, cy - height / 2
        self.area = (top - head + 4, bottom + foot - 4)      # (top, bottom) of the scroll area
        area_h = self.area[0] - self.area[1] - 8
        self.max_scroll = max(0.0, content_h - area_h)
        self.scroll_y = min(self.scroll_y, self.max_scroll)
        # background
        bg = C.scale9(self.bg_file, self.width, height) if self.bg_file else None
        if bg:
            C.fn('add_child')(self.box, bg, 0)
            C.fn('set_pos')(bg, float(cx), float(cy))
        else:
            dn = C.draw_node()
            C.fn('add_child')(self.box, dn, 0)
            x0, x1 = cx - self.width / 2, cx + self.width / 2
            C.draw_poly(dn, [(x0, bottom), (x1, bottom), (x1, top), (x0, top)], (28, 32, 64, 245), 2,
                        (255, 255, 255, 90))
        if self.title:
            font = 'goldFont.fnt' if self.title.isascii() else None
            t = C.Label(self.title, cx, top - 22, 0.8 if font else 0.7, font, z=3, parent=self.box)
            tw, _ = t.size()
            if tw > self.width - 70:
                C.fn('set_scale')(t.node, float(t._scale * (self.width - 70) / tw))
        self._close_spr = None
        if self.close_button:
            spr = C.sprite('GJ_closeBtn_001.png')
            if spr:
                C.fn('set_scale')(spr, 0.8)
                C.fn('add_child')(self.box, spr, 10)
                C.fn('set_pos')(spr, float(cx - self.width / 2 + 6), float(top - 6))
                self._close_spr = spr
        # scroll bar
        self._scrollbar = None
        if self.max_scroll > 0:
            self._scrollbar = C.draw_node()
            C.fn('add_child')(self.box, self._scrollbar, 8)
        # place widgets
        self._content_h, self._cx, self._cy = content_h, cx, cy
        for w in self.fixed:
            w.place(cx + w.fixed[0], cy + w.fixed[1])
        self._place_flow()

    def _place_flow(self):
        top, bottom = self.area
        area_h = top - bottom - 8
        if self.max_scroll > 0 or self._content_h > area_h * 0.6:
            y = top - 4                                             # from the top
        else:
            y = (top + bottom) / 2 + self._content_h / 2            # centered
        y += self.scroll_y
        for w in self.items:
            cy = y - w.h / 2
            w.place(self._cx, cy)
            w.show(cy + w.h / 2 <= top + 2 and cy - w.h / 2 >= bottom - 2)
            y -= w.h + GAP
        if self._scrollbar:
            sb = self._scrollbar
            C.fn('dn_clear')(sb)
            x = self._cx + self.width / 2 - 9
            C.draw_line(sb, x, bottom + 4, x, top - 4, (0, 0, 0, 90), 4)
            frac = area_h / (area_h + self.max_scroll)
            length = max(16, (top - bottom - 8) * frac)
            pos = self.scroll_y / self.max_scroll if self.max_scroll else 0
            y1 = top - 4 - pos * (top - bottom - 8 - length)
            C.draw_line(sb, x, y1, x, y1 - length, (255, 255, 255, 160), 4)

    def scroll_to(self, value):
        value = max(0.0, min(self.max_scroll, value))
        if value != self.scroll_y and self.box:
            self.scroll_y = value
            self._place_flow()

    # ------------------------------------------------ input
    def _widget_at(self, x, y):
        for w in self.fixed + self.items:
            if not w.shown:
                continue
            r = w.widget_at(x, y)
            if r:
                return r
        return None

    def touch_down(self, x, y):
        if self._close_spr:
            bx, by = C.position(self._close_spr)
            if abs(x - bx) < 20 and abs(y - by) < 20:
                self._close_pressed = True
                C.scale_bounce(self._close_spr, 0.8 * 1.2)
                return
        w = self._widget_at(x, y)
        for i in self.all_widgets():
            if isinstance(i, Input) and i.focused and i is not w:
                i.focus(False)
        self._active = w
        if w:
            w.down(x, y)
        top, bottom = self.area
        self._drag = [x, y, self.scroll_y, False] if self.max_scroll > 0 and bottom <= y <= top else None

    def touch_move(self, x, y):
        if self._close_pressed:
            return
        a = self._active
        if isinstance(a, Slider):
            a.drag(x, y)
            return
        d = self._drag
        if d and (d[3] or abs(y - d[1]) > 8):
            if not d[3]:
                d[3] = True
                if a:
                    a.cancel()
                    self._active = None
            self.scroll_to(d[2] + (y - d[1]))
            return
        if a:
            a.drag(x, y)

    def touch_up(self, x, y):
        if self._close_pressed:
            self._close_pressed = False
            C.scale_back(self._close_spr, 0.8)
            bx, by = C.position(self._close_spr)
            if abs(x - bx) < 22 and abs(y - by) < 22:
                self.close()
            return
        a, self._active, self._drag = self._active, None, None
        if a:
            a.up(x, y, a.contains(x, y, 6))

    def focused_input(self):
        for w in self.all_widgets():
            if isinstance(w, Input) and w.focused:
                return w
        return None

    def tick(self, dt):
        for w in self.items + self.fixed:
            w.tick(dt)


# ================================================================ screen buttons (on game layers)
class ScreenButton:
    def __init__(self, node, callback, owner='pymodder', scale=1.0):
        self.node, self.callback, self.owner, self.scale = node, callback, owner, scale
        C.fn('retain')(node)
        self._pressed = False
        screen_buttons.append(self)

    def alive(self):
        return bool(self.node and C.fn('parent')(self.node))

    def on_top(self):
        scene = C.running_scene()
        n, top = self.node, None
        while n:
            p = C.fn('parent')(n)
            if p == scene:
                top = n
                break
            if not C.fn('is_visible')(n):
                return False
            n = p
        if not top:
            return False
        kids = [k for k in C.children(scene) if C.fn('is_visible')(k)
                and (k == top or not (is_overlay(k) or
                                      (M.class_name(k) or '').startswith(('cocos2d::CCLabel', 'cocos2d::CCDrawNode'))))]
        return bool(kids) and kids[-1] == top

    def hit(self, x, y):
        x0, y0, x1, y1 = C.world_rect(self.node)
        return x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4

    def down(self):
        self._pressed = True
        C.scale_bounce(self.node, self.scale * 1.2)

    def up(self, x, y):
        self._pressed = False
        if not self.node:
            return
        C.scale_back(self.node, self.scale)
        if self.hit(x, y):
            flex_call(self.owner, self.callback)

    def remove(self):
        if self in screen_buttons:
            screen_buttons.remove(self)
        if self.node:
            node, self.node = self.node, None
            C.remove(node, True)
            C.fn('release')(node)


def cleanup_screen_buttons():
    for b in list(screen_buttons):
        if not b.alive():
            b.remove()


# ================================================================ input routing (called from hooks)
def busy():
    return bool(stack) or _capture[0] is not None


def touch(kind, tid, x, y):
    """kind: 0 began, 1 moved, 2 ended, 3 cancelled. Returns True if the game must not see it."""
    if kind == 0:
        p = stack[-1] if stack else None
        if p is not None:
            _route[tid] = 'ui'
            p.touch_down(x, y)
            return True
        for b in reversed(screen_buttons):
            if b.alive() and b.hit(x, y) and b.on_top():
                _route[tid] = b
                b.down()
                return True
        _route[tid] = 'game'
        return False
    r = _route.get(tid)
    if kind >= 2:
        _route.pop(tid, None)
    if r == 'game' or (r is None and (kind >= 2 or not stack)):
        return False
    if isinstance(r, ScreenButton):
        if kind == 2:
            r.up(x, y)
        elif kind == 3:
            r.up(-1e9, -1e9)
        return True
    p = stack[-1] if stack else None
    if p is not None and r == 'ui':
        if kind == 1:
            p.touch_move(x, y)
        elif kind == 2:
            p.touch_up(x, y)
        else:
            p.touch_up(-1e9, -1e9)
    return True


def _recent(key, window):
    now = time.perf_counter()
    if now - _dedup[key] < window:
        return True
    _dedup[key] = now
    return False


def esc_recent():
    """True right after ESC closed something (the same key press arrives twice: keyboard + keypad)."""
    return time.perf_counter() - _dedup['esc'] < 0.25


def back():
    """ESC / keypad back. Returns True when something was closed."""
    if esc_recent():
        return True
    handled = False
    if _capture[0]:
        cb, _capture[0] = _capture[0], None
        cb(None)
        handled = True
    elif stack:
        p = stack[-1]
        inp = p.focused_input()
        if inp:
            inp.focus(False)
        else:
            p.close()
        handled = True
    if handled:
        _dedup['esc'] = time.perf_counter()
    return handled


def _char_for(code):
    shift = _user32().GetKeyState(0x10) & 0x8000
    if 0x41 <= code <= 0x5A:
        return chr(code) if shift else chr(code + 32)
    if 0x30 <= code <= 0x39:
        return ')!@#$%^&*('[code - 0x30] if shift else chr(code)
    if 0x60 <= code <= 0x69:
        return chr(code - 0x30)
    return {0x20: ' ', 0xBD: '_' if shift else '-', 0xBE: '>' if shift else '.', 0xBC: '<' if shift else ',',
            0xBB: '+' if shift else '=', 0x6D: '-', 0x6E: '.', 0xBF: '?' if shift else '/'}.get(code)


def key(code, down, repeat, key_name):
    """Keyboard while a popup is open. Always swallowed."""
    if not down:
        return
    if code == ESC:
        back()
        return
    if _capture[0]:
        if not repeat:
            cb, _capture[0] = _capture[0], None
            cb(key_name)
        return
    p = stack[-1] if stack else None
    if not p:
        return
    inp = p.focused_input()
    if inp:
        if code == BACKSPACE:
            if not _recent('back', 0.03):
                inp.backspace()
        elif code == ENTER:
            if not repeat:
                inp.focus(False)
                if inp.on_enter:
                    inp._call(inp.on_enter, inp.text)
        elif code == KEY_V and _user32().GetKeyState(0x11) & 0x8000:
            if not repeat:
                inp.insert(clipboard())
        elif not _ime_seen[0]:
            ch = _char_for(code)
            if ch:
                _pending_char[0] = (inp, ch)
        return
    if code == hooks.get('menu_key_code') and not repeat:
        close_all()
        return
    mk = hooks.get('mod_menu_key')
    if mk and not repeat and mk(code, p):
        return
    if code in (0x26, 0x21):        # up / page up
        p.scroll_to(p.scroll_y - (30 if code == 0x26 else 120))
    elif code in (0x28, 0x22):      # down / page down
        p.scroll_to(p.scroll_y + (30 if code == 0x28 else 120))


def insert_text(text):
    """Typed text from the game (IME). Returns True to swallow."""
    if not stack:
        return False
    _ime_seen[0] = True
    _pending_char[0] = None
    inp = stack[-1].focused_input()
    if inp:
        inp.insert(text)
    return True


def delete_backward():
    if not stack:
        return False
    inp = stack[-1].focused_input()
    if inp and not _recent('back', 0.03):
        inp.backspace()
    return True


def scroll(a, b):
    if not stack:
        return False
    v = a if a else b
    if CFG.get('invert_scroll'):
        v = -v
    step = 30 if abs(v) < 5 else min(120, abs(v))
    p = stack[-1]
    p.scroll_to(p.scroll_y + (step if v > 0 else -step))
    return True


def capture_key(callback):
    """Next key press -> callback(key_name or None if ESC)."""
    _capture[0] = callback


def clipboard():
    u, k = _user32(), ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    text = ''
    if u.OpenClipboard(None):
        try:
            h = u.GetClipboardData(13)       # CF_UNICODETEXT
            if h:
                p = k.GlobalLock(h)
                if p:
                    text = ctypes.wstring_at(p)
                    k.GlobalUnlock(h)
        finally:
            u.CloseClipboard()
    return text.replace('\r', '').replace('\n', ' ')


def set_clipboard(text):
    """Put text into the Windows clipboard."""
    u, k = _user32(), ctypes.windll.kernel32
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k.GlobalFree.argtypes = [ctypes.c_void_p]
    u.SetClipboardData.restype = ctypes.c_void_p
    u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    data = (str(text) + '\0').encode('utf-16-le')
    if not u.OpenClipboard(None):
        return False
    try:
        u.EmptyClipboard()
        h = k.GlobalAlloc(2, len(data))          # GMEM_MOVEABLE
        p = k.GlobalLock(h) if h else None
        if not p:
            return False
        ctypes.memmove(p, data, len(data))
        k.GlobalUnlock(h)
        if not u.SetClipboardData(13, h):        # CF_UNICODETEXT
            k.GlobalFree(h)
            return False
        return True
    finally:
        u.CloseClipboard()


def tick(dt):
    pc = _pending_char[0]
    if pc:
        _pending_char[0] = None
        inp, ch = pc
        if inp.focused:
            inp.insert(ch)
    scene = C.running_scene()
    for p in list(stack):
        if p.root and C.fn('parent')(p.root) != scene:
            p.close()            # scene changed under the popup
        else:
            p.tick(dt)
    if screen_buttons:
        cleanup_screen_buttons()


def close_all():
    for p in list(stack):
        p.close()


def close_owner(owner):
    for p in list(stack):
        if p.owner == owner:
            p.close()
    for b in list(screen_buttons):
        if b.owner == owner:
            b.remove()


# ================================================================ ready-made dialogs
def alert(text, title='Info', button='OK', on_close=None, owner='pymodder', width=300):
    p = Popup(title, width, on_close=on_close, owner=owner)
    p.text(text, 0.5)
    p.space(4)
    p.button(button, p.close)
    return p.show()


def confirm(text, on_yes=None, title='Are you sure?', yes='Yes', no='No', on_no=None, owner='pymodder', width=300,
            yes_color='green', no_color='grey'):
    """Yes / No. Closing it with ESC or the X counts as "No"."""
    done = []

    def closed():
        if not done:
            done.append(0)
            flex_call(owner, on_no)
    p = Popup(title, width, owner=owner, on_close=closed)
    p.text(text, 0.5)
    p.space(4)

    def ok():
        done.append(1)
        p.close()
        flex_call(owner, on_yes)
    with p.row(16):
        p.button(no, p.close, no_color)
        p.button(yes, ok, yes_color)
    return p.show()


def prompt(text, on_done=None, title='', default='', placeholder='', button='OK', numeric=False, on_cancel=None,
           owner='pymodder', width=300):
    """A text box: on_done(text) after OK / Enter."""
    done = []

    def closed():
        if not done:
            done.append(0)
            flex_call(owner, on_cancel)
    p = Popup(title, width, owner=owner, on_close=closed)
    if text:
        p.text(text, 0.5)
    box = p.input(str(default), placeholder, numeric=numeric)
    box.focus(True)

    def ok(*_):
        if done:
            return
        done.append(1)
        value = box.value
        p.close()
        if numeric:
            try:
                value = float(value) if '.' in str(value) else int(value)
            except ValueError:
                value = 0
        flex_call(owner, on_done, value)
    box.on_enter = ok
    p.space(4)
    p.button(button, ok)
    return p.show()


def choose(options, on_pick=None, title='Choose', text='', owner='pymodder', width=280, cancel='Cancel'):
    """A list of buttons: on_pick(index, option)."""
    p = Popup(title, width, owner=owner)
    if text:
        p.text(text, 0.5)
    for i, opt in enumerate(options):
        def pick(i=i, opt=opt):
            p.close()
            flex_call(owner, on_pick, i, opt)
        p.button(str(opt), pick, 'blue', 0.6, width=width - 60)
    if cancel:
        p.space(2)
        p.button(cancel, p.close, 'grey', 0.6)
    return p.show()
