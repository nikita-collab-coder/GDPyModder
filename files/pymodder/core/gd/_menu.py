"""PyModder in-game menu: button in the main menu / pause menu, mod list, mod settings."""
import ctypes
import os
import subprocess
import traceback
from ctypes import c_void_p

from . import _cocos as C
from . import _core as K
from . import _mem as M
from . import _native as N
from . import _ui as U

menu_buttons = []     # {'image', 'callback', 'owner', 'base_dir'}
pause_buttons = []
_menu = {'layer': None, 'menu': None, 'row': [], 'ours': [], 'spacing': 50.0, 'y': 0.0, 'center': 0.0,
         'h': 40.0, 'own_menu': False}
_item_cbs = {}        # CCMenuItemSpriteExtra* -> (callback, owner)
_popup = [None]

# ---------------------------------------------------------------- menu item callback (SEL_MenuHandler)
_SEL = ctypes.CFUNCTYPE(None, c_void_p, c_void_p)


def _on_item(this, sender):
    try:
        cb = _item_cbs.get(sender)
        if cb:
            K.later(lambda: U.flex_call(cb[1], cb[0]))
    except Exception:
        traceback.print_exc()


_sel = _SEL(_on_item)
_sel_addr = ctypes.cast(_sel, c_void_p).value


def icon_path():
    return os.path.join(K.ROOT, 'res', 'icon_gd.png')


def default_mod_icon():
    return os.path.join(K.ROOT, 'res', 'mod_icon.png')


def _mod_icon(info, height):
    """Sprite of a mod's icon (ICON / icon.png / <name>.png / the default one), scaled to `height`."""
    spr = None
    icon = info.get('icon')
    if icon:
        try:
            spr = C.sprite(icon, os.path.dirname(info['path']))
        except Exception:
            spr = None
    if not spr:
        spr = C.sprite(default_mod_icon())
    if not spr:
        return None
    w, h = C.node_size(spr)
    C.fn('set_scale')(spr, float(height / max(w, h, 1)))
    return spr


def has_menu(owner):
    return bool(K.settings.get(owner) or K.mod_menus.get(owner))


def _icon(image, base_dir, height):
    """Sprite for a button: frame name / .png / text caption. Scaled to `height`."""
    spr = C.sprite(image or icon_path(), base_dir)
    if not spr and image and K.builtin_icon(image):
        spr = C.sprite(K.builtin_icon(image))
    if not spr and image and not str(image).lower().endswith('.png'):
        spr = C.button_sprite(str(image) if str(image).isascii() else '?', 0, 'GJ_button_01.png', 'bigFont.fnt')
    if not spr:
        return None, 1.0
    w, h = C.node_size(spr)
    s = height / max(w, h, 1)
    C.fn('set_scale')(spr, float(s))
    return spr, s


# ---------------------------------------------------------------- main menu
def _bottom_row(layer):
    """The bottom row of round buttons in MenuLayer: (menu, [items])."""
    W, H = C.win_size()
    best = None
    for m in C.find_children(layer, 'cocos2d::CCMenu', 2):
        items = C.children(m)
        if len(items) < 3:
            continue
        ys = [round(C.fn('get_y')(i)) for i in items]
        y = max(set(ys), key=ys.count)
        row = [i for i, yy in zip(items, ys) if yy == y]
        if len(row) < 3:
            continue
        sizes = [C.node_size(i) for i in row]
        if min(s[0] for s in sizes) < 25 or max(s[0] for s in sizes) > 120:
            continue
        xs = [C.fn('get_x')(i) for i in row]
        wx, wy = C.to_world(m, (min(xs) + max(xs)) / 2, y)
        if wy > H / 2 or abs(wx - W / 2) > W * 0.15:
            continue            # not the centered bottom row (e.g. social buttons in the corner)
        if best is None or wy < best[0]:
            best = (wy, m, row)
    return (best[1], best[2]) if best else (None, [])


def _layout_row():
    row = _menu['row']
    if not row:
        return
    W, _ = C.win_size()
    n = len(row)
    sp = _menu['spacing']
    if n > 1:
        sp = min(sp, (W - 90) / (n - 1))
    if _menu['own_menu']:
        _, H = C.win_size()
        for i, it in enumerate(row):
            C.fn('set_pos')(it, float(W - 30), float(H - 30 - i * (_menu['h'] + 8)))
        return
    x0 = _menu['center'] - sp * (n - 1) / 2
    for i, it in enumerate(row):
        C.fn('set_pos')(it, float(x0 + sp * i), float(_menu['y']))


def _add_menu_item(image, callback, owner, base_dir=None):
    menu = _menu['menu']
    spr, _ = _icon(image, base_dir, _menu['h'] * 0.95)
    if not spr or not menu:
        return None
    item = N.function('CCMenuItemSpriteExtra::create')(spr, None, _menu['layer'], _sel_addr)
    if not item:
        return None
    _item_cbs[item] = (callback, owner)
    C.fn('add_child')(menu, item, 5)
    _menu['row'].append(item)
    _menu['ours'].append((item, owner))
    return item


def on_menu_layer(layer):
    _item_cbs.clear()
    _menu.update(layer=layer, menu=None, row=[], ours=[], own_menu=False)
    menu, row = _bottom_row(layer)
    if menu:
        xs = sorted(C.fn('get_x')(i) for i in row)
        diffs = sorted(b - a for a, b in zip(xs, xs[1:]))
        _menu.update(menu=menu, row=sorted(row, key=lambda i: C.fn('get_x')(i)),
                     spacing=diffs[len(diffs) // 2] if diffs else 50.0, y=C.fn('get_y')(row[0]),
                     center=(xs[0] + xs[-1]) / 2, h=max(28.0, min(70.0, C.node_size(row[0])[1])))
    else:
        menu = C.fn('menu_create')()
        C.fn('add_child')(layer, menu, 20)
        C.fn('set_pos')(menu, 0.0, 0.0)
        _menu.update(menu=menu, row=[], own_menu=True, h=40.0)
        print('[PyModder] bottom menu not found - the button goes to the top right corner')
    if K.CFG.get('menu_button', True):
        _add_menu_item(None, toggle_menu, 'pymodder')
    for b in menu_buttons:
        _add_menu_item(b['image'], b['callback'], b['owner'], b['base_dir'])
    _layout_row()


def _menu_alive():
    layer = _menu['layer']
    return bool(layer) and layer in C.children(C.running_scene())


def on_stable_scene(scene):
    for ch in C.children(scene):
        if M.class_name(ch) == 'MenuLayer' and ch != _menu['layer']:
            on_menu_layer(ch)       # PyModder started after the first menu was built
            break


def add_menu_button(image, callback, owner, base_dir):
    b = {'image': image, 'callback': callback, 'owner': owner, 'base_dir': base_dir}
    menu_buttons.append(b)

    def sync():
        if _menu_alive() and _menu['menu']:
            _add_menu_item(image, callback, owner, base_dir)
            _layout_row()
    K.when_scene_ready(sync)
    return b


def add_pause_button(image, callback, owner, base_dir):
    b = {'image': image, 'callback': callback, 'owner': owner, 'base_dir': base_dir}
    pause_buttons.append(b)
    return b


def forget_owner(owner):
    menu_buttons[:] = [b for b in menu_buttons if b['owner'] != owner]
    pause_buttons[:] = [b for b in pause_buttons if b['owner'] != owner]
    for item in [i for i, o in _menu['ours'] if o == owner]:
        _item_cbs.pop(item, None)
        if _menu_alive():
            C.remove(item)
            if item in _menu['row']:
                _menu['row'].remove(item)
    _menu['ours'] = [(i, o) for i, o in _menu['ours'] if o != owner]
    if _menu_alive():
        _layout_row()


# ---------------------------------------------------------------- pause menu
def on_pause_layer(layer):
    entries = []
    if K.CFG.get('pause_button', True):
        entries.append((None, toggle_menu, 'pymodder', None))
    entries += [(b['image'], b['callback'], b['owner'], b['base_dir']) for b in pause_buttons]
    for i, (image, cb, owner, base) in enumerate(entries):
        spr, s = _icon(image, base, 34)
        if not spr:
            continue
        C.fn('add_child')(layer, spr, 50)
        C.fn('set_pos')(spr, 34.0, float(52 + i * 44))
        U.ScreenButton(spr, cb, owner, s)


# ---------------------------------------------------------------- mod list
GREEN, YELLOW, RED, GREY = (90, 230, 90), (255, 200, 60), (255, 85, 85), (150, 150, 150)


class ModRow(U.Widget):
    interactive = True
    flex = True

    def __init__(self, info, index):
        super().__init__()
        self.info, self.index = info, index
        self.part = None

    def _status(self):
        i = self.info
        if not i['enabled']:
            return GREY, 'Disabled'
        if i['error']:
            return RED, 'Load error - click for details'
        if i['runtime_error']:
            return YELLOW, 'Error while running - click for details'
        sub = []
        if i['version']:
            sub.append('v' + i['version'].lstrip('vV'))
        if i['author']:
            sub.append('by ' + i['author'])
        return GREEN, '  '.join(sub) or i['name'] + '.py'

    def build(self, width):
        self.w, self.h = width, 40
        w = width
        color, sub = self._status()
        self._add(C.layer_color((0, 0, 0, 70 if self.index % 2 else 40), w, 38), -w / 2, -19, z=1)
        icon = _mod_icon(self.info, 28)
        if icon:
            if not self.info['enabled']:
                C.set_color(icon, (110, 110, 110))
            self._add(icon, -w / 2 + 20, 0, z=2)
        if self.info['enabled'] and (self.info['error'] or self.info['runtime_error']):
            badge = C.draw_node()
            C.draw_dot(badge, 0, 0, 6, color + (255,))
            self._add(badge, -w / 2 + 31, -10, z=3)
            mark = C.Label('!', 0, 0, 0.32, 'bigFont.fnt', (255, 255, 255), z=4, parent=self.popup.box)
            self.nodes.append([mark.node, -w / 2 + 31, -10])
        right = 34
        self.check = U._Check(self.info['enabled'], 24)
        self._add(self.check.node, w / 2 - 18, 0)
        self.gear = None
        if has_menu(self.info['id']) and self.info['ok']:
            g, s = _icon('GJ_optionsBtn_001.png', None, 24)
            if g:
                self.gear, self.gear_s = g, s
                self._add(g, w / 2 - 50, 0)
                right = 64
        t = C.Label(self.info['title'], 0, 0, 0.5, None, (255, 255, 255) if self.info['enabled'] else GREY,
                    z=2, parent=self.popup.box, anchor_xy=(0, 0.5))
        t.fit(w - 46 - right)
        self.nodes.append([t.node, -w / 2 + 40, 7])
        lb = C.Label(sub, 0, 0, 0.32, None, color if color != GREEN else (200, 200, 200), z=2,
                     parent=self.popup.box, anchor_xy=(0, 0.5))
        lb.fit(w - 46 - right)
        self.nodes.append([lb.node, -w / 2 + 40, -10])

    def _part(self, x):
        if abs(x - (self.x + self.w / 2 - 18)) < 17:
            return 'check'
        if self.gear and abs(x - (self.x + self.w / 2 - 50)) < 16:
            return 'gear'
        return 'info'

    def down(self, x, y):
        self.part = self._part(x)
        if self.part == 'check' and self.check.frames:
            C.scale_bounce(self.check.node, self.check.scale * 1.2)
        elif self.part == 'gear':
            C.scale_bounce(self.gear, self.gear_s * 1.2)

    def cancel(self):
        if self.part == 'check' and self.check.frames:
            C.scale_back(self.check.node, self.check.scale)
        elif self.part == 'gear':
            C.scale_back(self.gear, self.gear_s)

    def up(self, x, y, inside):
        self.cancel()
        part, self.part = self.part, None
        if not inside or part != self._part(x):
            return
        owner = self.info['id']
        if part == 'check':
            on = not self.info['enabled']
            K.set_mod_enabled(owner, on)
            K.notify(('Mod enabled: ' if on else 'Mod disabled: ') + self.info['title'], 2,
                     GREEN if on else GREY)
            refresh_menu()
        elif part == 'gear':
            open_mod_menu(owner)
        else:
            open_info(owner)


def _open_file(path):
    try:
        if path.lower().endswith(('.py', '.md', '.txt', '.log', '.json')):
            subprocess.Popen(['notepad.exe', path])
        else:
            os.startfile(path)
    except Exception as e:
        U.alert('Cannot open:\n%s\n\n%s' % (path, e), 'Error')


def _fill(p):
    mods = list(K.mods.values())
    if not mods:
        p.space(10)
        p.text('No mods yet', 0.6)
        p.text('Put .py files into the folder\nGeometry Dash/pymodder/mods\nand press Reload (F5)', 0.4,
               (210, 210, 210))
    for i, info in enumerate(mods):
        p.add(ModRow(info, i))
    good = sum(1 for m in mods if m['ok'])
    with p.row(10, 0, -p.height / 2 + 26):
        p.button('Reload', _reload, size=0.62)
        p.button('Mods folder', lambda: _open_file(os.path.join(K.ROOT, 'mods')), 'grey', 0.62)
        p.button('Log', lambda: _open_file(os.path.join(K.ROOT, 'logs', 'python.log')), 'grey', 0.62)
        p.button('API', lambda: _open_file(os.path.join(K.ROOT, 'docs', 'API.md')), 'grey', 0.62)
    p.title = 'PyModder - %d/%d mods' % (good, len(mods)) if mods else 'PyModder'


def _reload():
    K.reload_mods()


def open_menu():
    if K.state.started and not K.state.paused:
        K.pause_game()
    p = U.Popup('PyModder', 420, 290, owner='pymodder', footer=38)
    _fill(p)
    _popup[0] = p
    p.show()


def toggle_menu():
    p = _popup[0]
    if p and p.is_open:
        p.close()
    else:
        open_menu()


def refresh_menu():
    p = _popup[0]
    if p and p.is_open and p.box:
        sy = p.scroll_y
        p.clear()
        _fill(p)
        p.scroll_y = sy
        p.refresh()


# ---------------------------------------------------------------- mod details / settings
def open_info(owner):
    info = K.mods.get(owner)
    if not info:
        return
    p = U.Popup(info['title'], 380, owner='pymodder')
    meta = []
    if info['version']:
        meta.append('v' + info['version'].lstrip('vV'))
    if info['author']:
        meta.append('by ' + info['author'])
    if meta:
        p.text('  '.join(meta), 0.4, (200, 200, 200))
    if info['description']:
        p.text(info['description'], 0.42)
    rel = os.path.relpath(info['path'], os.path.dirname(K.ROOT))
    p.text(rel, 0.55, (170, 170, 170), font='chatFont.fnt')
    if info['error']:
        p.text('Load error:', 0.45, RED)
        p.text(info['traceback'] or info['error'], 0.5, (255, 200, 200), 'left', 'chatFont.fnt')
    elif info['runtime_error']:
        p.text('Error while running:', 0.45, YELLOW)
        p.text(info['runtime_error'], 0.5, (255, 230, 180), 'left', 'chatFont.fnt')
    p.space(2)
    with p.row(12):
        p.button('Open file', lambda: _open_file(info['path']), 'grey', 0.6)
        if has_menu(owner) and info['ok']:
            p.button('Settings' if owner not in K.mod_menus else 'Menu', lambda: (p.close(), open_mod_menu(owner)),
                     'blue', 0.6)
        p.button('OK', p.close, size=0.6)
    p.show()


def open_mod_menu(owner):
    """The mod's own menu (gd.mod_menu) or its settings. Pauses the level first."""
    info = K.mods.get(owner)
    if not info or not info['ok'] or not has_menu(owner):
        return
    if K.state.started and not K.state.paused:
        K.pause_game()
    custom = K.mod_menus.get(owner)
    if custom:
        U.flex_call(owner, custom)
    else:
        open_settings(owner)


def _menu_popup_of(owner):
    for p in reversed(U.stack):
        if getattr(p, 'menu_of', None) == owner or p.owner == owner:
            return p
    return None


def toggle_mod_menu(owner):
    p = _menu_popup_of(owner)
    if p:
        p.close()
    else:
        open_mod_menu(owner)


def open_settings(owner):
    info = K.mods.get(owner)
    lst = K.settings.get(owner, [])
    if not info or not lst:
        return
    p = U.Popup(info['title'], 360, owner='pymodder')
    p.menu_of = owner
    controls = []
    first = True
    for s in lst:
        def setter(v, s=s):
            try:
                s.value = v
            except Exception as e:
                U.alert('%s: %s' % (s.title, e), 'Error')
        k = s.kind
        if k == 'header':
            if not first:
                p.space(6)
            p.text(s.title, 0.55, (255, 255, 255), 'center', 'goldFont.fnt')
            p.line()
            w = None
        elif k == 'label':
            p.text(s.title, 0.5, s.color if isinstance(s.color, tuple) else (220, 220, 220), 'left',
                   'chatFont.fnt')
            w = None
        elif k == 'space':
            p.space(10)
            w = None
        elif k == 'button':
            p.button(s.title, lambda s=s: U.flex_call(owner, s.callback), s.color or 'green', 0.6)
            w = None
        elif k == 'bool':
            w = p.toggle(s.title, s.value, setter)
        elif k in ('int', 'float') and s.min is not None and s.max is not None:
            mn, mx = (int(s.min), int(s.max)) if k == 'int' else (float(s.min), float(s.max))
            w = p.slider(s.title, s.value, mn, mx, setter, step=s.step)
        elif k == 'choice':
            w = p.choice(s.title, s.options, s.value, setter)
        elif k == 'key':
            w = p.keybind(s.title, s.value, setter)
        elif k == 'color':
            w = p.add(U.ColorButton(s.title, s.value, setter))
        else:
            p.text(s.title, 0.42, align='left')
            w = p.input(str(s.value), str(s.default), setter, numeric=k in ('int', 'float'))
        if w is not None:
            controls.append((s, w))
        first = False
        if s.description and k not in ('label', 'space'):
            p.text(s.description, 0.5, (190, 190, 190), 'left', 'chatFont.fnt')

    def reset():
        for s, w in controls:
            s.reset()
            w.value = s.value
    p.space(2)
    with p.row(12):
        if controls:
            p.button('Reset', reset, 'grey', 0.6)
        p.button('OK', p.close, size=0.6)
    p.show()
