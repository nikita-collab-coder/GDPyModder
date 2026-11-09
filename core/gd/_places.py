"""Buttons that mods put on game screens: gd.screen_button("level", ...) and the shortcuts
(gd.level_button, gd.editor_button, gd.end_button ...). The buttons are PyModder screen buttons
(they get the click before GD, so they work on popups too) placed at a corner / side of the screen
or of the popup window, several buttons at one place are stacked."""
import traceback

from . import _cocos as C
from . import _core as K
from . import _mem as M
from . import _nodes as ND
from . import _ui as U

# place -> (class, entry function or None = Class::init, 'screen' | 'popup', default position)
PLACES = {
    'menu': ('MenuLayer', None, 'screen', 'top-left'),
    'level': ('LevelInfoLayer', None, 'screen', 'bottom-left'),
    'my_level': ('EditLevelLayer', None, 'screen', 'bottom-left'),
    'levels': ('LevelBrowserLayer', None, 'screen', 'bottom-left'),
    'main_levels': ('LevelSelectLayer', None, 'screen', 'bottom-left'),
    'search': ('LevelSearchLayer', None, 'screen', 'bottom-left'),
    'level_list': ('LevelListLayer', None, 'screen', 'bottom-left'),
    'creator': ('CreatorLayer', None, 'screen', 'bottom-left'),
    'garage': ('GJGarageLayer', None, 'screen', 'bottom-left'),
    'editor': ('EditorUI', None, 'screen', 'top'),
    'editor_pause': ('EditorPauseLayer', 'EditorPauseLayer::customSetup', 'screen', 'bottom-left'),
    'pause': ('PauseLayer', 'PauseLayer::customSetup', 'screen', 'top-left'),
    'end': ('EndLevelLayer', 'EndLevelLayer::customSetup', 'popup', 'bottom-left'),
    'profile': ('ProfilePage', 'ProfilePage::init', 'popup', 'bottom-left'),
    'options': ('OptionsLayer', 'OptionsLayer::customSetup', 'popup', 'bottom-left'),
}
ALIASES = {'level_page': 'level', 'online_level': 'level', 'end_screen': 'end', 'complete': 'end',
           'editor_ui': 'editor', 'icons': 'garage', 'main_menu': 'menu', 'browser': 'levels',
           'level_browser': 'levels', 'create': 'creator', 'settings': 'options', 'my_levels_page': 'my_level',
           'edit_level': 'my_level'}
POSITIONS = ('top-left', 'top-right', 'bottom-left', 'bottom-right', 'left', 'right', 'top', 'bottom')

_buttons = []          # registered: dict(cls, entry, kind, position, image, text, color, size, func, owner, ...)
_hooked = set()        # (cls, entry) with our layer handler
_cell_buttons = []     # LevelCell buttons


def place_info(place):
    """'level' / 'LevelInfoLayer' / any layer class -> (class, entry, kind, default position)."""
    p = str(place)
    key = ALIASES.get(p.lower().replace(' ', '_').replace('-', '_'), p.lower().replace(' ', '_').replace('-', '_'))
    if key in PLACES:
        return PLACES[key]
    for v in PLACES.values():
        if v[0] == p:
            return v
    kind = 'popup' if p.endswith(('Popup', 'Page', 'Alert')) else 'screen'
    return (p, ND.layer_entry(p), kind, 'bottom-left')


def _norm_pos(position):
    p = str(position).lower().replace('_', '-').replace(' ', '-')
    p = {'topleft': 'top-left', 'topright': 'top-right', 'bottomleft': 'bottom-left',
         'bottomright': 'bottom-right', 'left-top': 'top-left', 'right-top': 'top-right',
         'left-bottom': 'bottom-left', 'right-bottom': 'bottom-right'}.get(p.replace('-', ''), p)
    if p not in POSITIONS:
        raise ValueError('position must be one of %s, not %r' % (', '.join(POSITIONS), position))
    return p


def add(place, image, func, owner, base_dir, position=None, offset=(0, 0), size=None, text=None, color='green'):
    cls, entry, kind, default = place_info(place)
    b = dict(cls=cls, entry=entry, kind=kind, position=_norm_pos(position or default), image=image, text=text,
             color=color, size=float(size or (28 if kind == 'popup' else 32)), func=func, owner=owner,
             base_dir=base_dir, offset=(float(offset[0]), float(offset[1])) if offset else (0.0, 0.0))
    _buttons.append(b)
    key = (cls, entry)
    if key not in _hooked:
        _hooked.add(key)
        ND.on_layer(cls, _handler(cls), 'pymodder', entry)     # also runs for a layer that is open now
    else:
        K.later(lambda: _rescan(b))
    return b


def _handler(cls):
    def built(layer, *args):
        for b in [b for b in _buttons if b['cls'] == cls]:
            try:
                _make(layer.ptr, b, args)
            except Exception:
                K.report(b['owner'], 'screen button')
    return built


def _rescan(b):
    if b not in _buttons:
        return
    sc = C.running_scene()
    if not sc:
        return
    for n in ND.Node(sc).walk(5):
        name = n.class_name or ''
        if name == b['cls'] or name.split('::')[-1] == b['cls']:
            got = ND._layer_args.get(n.ptr)
            args = got[1] if got and got[0] == M.ptr(n.ptr) else ()
            try:
                _make(n.ptr, b, args)
            except Exception:
                K.report(b['owner'], 'screen button')


# ---------------------------------------------------------------- building
def _main_layer(layer):
    """The moving / scaling window layer of a popup (FLAlertLayer / GJDropDownLayer m_mainLayer)."""
    for ch in C.children(layer):
        if M.class_name(ch) == 'cocos2d::CCLayer':
            return ch
    return layer


def _frame(layer, kind):
    """(parent node for the buttons, (x0, y0, x1, y1) rect in the parent's space, margin)."""
    W, H = C.win_size()
    if kind != 'popup':
        return layer, (0.0, 0.0, W, H), 8.0
    main = _main_layer(layer)
    best = None
    for ch in C.children(main):
        if 'Scale9' not in (M.class_name(ch) or ''):
            continue
        w, h = C.node_size(ch)
        n = ND.Node(ch)
        sx, sy = n.scale_x, n.scale_y
        if w * sx < 150 or h * sy < 100:
            continue
        if best is None or w * sx * h * sy > best[0]:
            ax, ay = n.anchor
            x, y = n.pos
            best = (w * sx * h * sy, (x - w * sx * ax, y - h * sy * ay, x + w * sx * (1 - ax), y + h * sy * (1 - ay)))
    if best:
        return main, best[1], 10.0
    return main, (0.0, 0.0, W, H), 8.0


def _sprite(b):
    from . import _menu as MN
    size = b['size']
    if b['text'] is not None:
        t = str(b['text'])
        spr = C.button_sprite(t if t.isascii() else '?', 0, U._texture(b['color']), 'goldFont.fnt', 1.0, 0.0, False)
        if not spr:
            return None, 1.0
        w, h = C.node_size(spr)
        s = size / max(h, 1)
        C.fn('set_scale')(spr, float(s))
        return spr, s
    return MN._icon(b['image'], b['base_dir'], size)


def _make(layer, b, args):
    parent, rect, margin = _frame(layer, b['kind'])
    spr, s = _sprite(b)
    if not spr:
        raise ValueError('cannot make a button image from %r' % (b['image'] if b['text'] is None else b['text']))
    C.fn('add_child')(parent, spr, 100)
    node, func, owner = ND.Node(layer), b['func'], b['owner']
    btn = U.ScreenButton(spr, lambda: U.flex_call(owner, func, node, *args), owner, s)
    btn.place = (parent, b['position'])
    btn.place_info = (rect, margin, b['offset'])
    _layout(btn.place)


def _slot(btn):
    w, h = C.node_size(btn.node)
    return max(w, h) * btn.scale


def _layout(place):
    group = [x for x in U.screen_buttons if getattr(x, 'place', None) == place and x.alive()]
    if not group:
        return
    pos = place[1]
    rect, margin, _ = group[0].place_info
    x0, y0, x1, y1 = rect
    gap = 6.0
    slots = [_slot(x) for x in group]
    total = sum(slots) + gap * (len(group) - 1)
    vertical = pos not in ('top', 'bottom')
    if vertical:
        if pos.startswith('top'):
            cur, sign = y1 - margin, -1
        elif pos.startswith('bottom'):
            cur, sign = y0 + margin, 1
        else:
            cur, sign = (y0 + y1) / 2 + total / 2, -1
    else:
        cur, sign = (x0 + x1) / 2 - total / 2, 1
    for btn, sl in zip(group, slots):
        c = cur + sign * sl / 2
        cur += sign * (sl + gap)
        if vertical:
            x = x0 + margin + sl / 2 if pos.endswith('left') else x1 - margin - sl / 2
            y = c
        else:
            x = c
            y = y1 - margin - sl / 2 if pos == 'top' else y0 + margin + sl / 2
        dx, dy = btn.place_info[2]
        C.fn('set_pos')(btn.node, float(x + dx), float(y + dy))


# ---------------------------------------------------------------- level cells (lists of levels)
def add_cell_button(image, func, owner, base_dir, size=None, text=None, color='green'):
    b = dict(image=image, text=text, color=color, size=float(size or 26), func=func, owner=owner, base_dir=base_dir,
             kind='cell')
    _cell_buttons.append(b)
    if 'cell' not in _hooked:
        _hooked.add('cell')
        ND.on_layer('LevelCell', _cell_built, 'pymodder', 'LevelCell::loadFromLevel')
    return b


def _cell_menu(cell):
    menus = [m for m in ND.Node(cell).find_all(cls='CCMenu', depth=3) if m.child_count]
    return max(menus, key=lambda m: m.child_count) if menus else None


def _cell_built(cell, level=None, *rest):
    if not _cell_buttons:
        return
    menu = _cell_menu(cell.ptr)
    if menu is None:
        return
    items = [i for i in menu.children if i.is_button and not (i.id or '').startswith('pymodder-cell-')]
    view = max(items, key=lambda i: i.x) if items else None
    if view is not None:
        x, y = view.x - view.width / 2 - 6, view.y
    else:
        w, h = cell.size
        x, y = w - 110, h / 2
    for i, b in enumerate(list(_cell_buttons)):
        try:
            func, owner = b['func'], b['owner']
            bid = 'pymodder-cell-%d' % i
            old = menu.find(id=bid, depth=1)
            if old is not None:          # the cell was loaded again
                old.remove()
            nb = ND.add_button(menu, b['image'] if b['text'] is None else None,
                               lambda func=func, owner=owner: U.flex_call(owner, func, cell, level),
                               x - b['size'] / 2, y, size=b['size'], text=b['text'], color=b['color'], id=bid,
                               owner=owner)
            x -= max(nb.width, b['size']) + 6
        except Exception:
            K.report(b['owner'], 'level cell button')


def _cleanup(owner):
    _buttons[:] = [b for b in _buttons if b['owner'] != owner]
    _cell_buttons[:] = [b for b in _cell_buttons if b['owner'] != owner]


K.cleanup_hooks.append(_cleanup)
