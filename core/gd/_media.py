"""Custom pictures: textures from files, sprite frames (incl. replacing GD frames), sprites on screen / level."""
import os
import traceback

from . import _core as K
from . import _cocos as C
from . import _mem as M
from . import _ui as U

IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tga', '.tif', '.tiff')
_replaced = {}       # frame name -> [original CCSpriteFrame* (retained) or 0, owner]
_added = {}          # frame name -> [our CCSpriteFrame* (retained), owner]
_world = []          # world sprites (dropped when the level closes)


def mod_dir(owner):
    import sys
    m = sys.modules.get(owner)
    return getattr(m, 'MOD_DIR', None) or os.path.join(K.ROOT or '.', 'mods')


def find_file(name, owner):
    p = str(name)
    if not os.path.isabs(p):
        p = os.path.join(mod_dir(owner), p)
    return p if os.path.isfile(p) else None


class Texture:
    """A picture from a file, loaded into video memory (shared by all sprites that use it)."""

    def __init__(self, path, smooth=True):
        self.path = os.path.abspath(path)
        self.ptr = C.texture(self.path)
        if not self.ptr:
            raise OSError('cannot load the picture: %s' % path)
        self.smooth = smooth

    @property
    def size(self):
        """Size in pixels (width, height)."""
        w, h = C.texture_size(self.ptr)
        k = C.content_scale()
        return round(w * k), round(h * k)

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    @property
    def smooth(self):
        return self._smooth

    @smooth.setter
    def smooth(self, on):
        self._smooth = bool(on)
        C.texture_smooth(self.ptr, self._smooth)

    def __repr__(self):
        return '<Texture %s %dx%d>' % (os.path.basename(self.path), *self.size)


def texture(name, smooth=True, owner=None):
    owner = owner or K.caller_owner()
    p = find_file(name, owner)
    if not p:
        raise FileNotFoundError('no file %s (looked in the mod folder %s)' % (name, mod_dir(owner)))
    return Texture(p, smooth)


# ---------------------------------------------------------------- sprite frames
def add_frame(name, image, smooth=True, owner=None):
    """Register a picture as a GD frame called name. If GD already has such a frame, it is replaced
    (like a texture pack) for everything created after this."""
    owner = owner or K.caller_owner()
    tex = image if isinstance(image, Texture) else texture(image, smooth, owner)
    frame = C.frame_from_texture(tex.ptr)
    if not frame:
        raise OSError('cannot make a frame from %s' % image)
    name = str(name)
    if name not in _replaced and name not in _added:
        old = C.fn('sfc_get')(C.fn('sfc')(), C._enc(name)) or 0
        if old:
            C.fn('retain')(old)
            _replaced[name] = [old, owner]
    C.fn('retain')(frame)
    prev = _added.get(name)
    C.add_frame(name, frame)
    if prev:
        C.fn('release')(prev[0])
    _added[name] = [frame, owner]
    if name in _replaced:
        _replaced[name][1] = owner
    return name


def restore_frame(name):
    """Bring back the original GD frame (or remove an added one)."""
    name = str(name)
    ours = _added.pop(name, None)
    orig = _replaced.pop(name, None)
    if orig and orig[0]:
        C.add_frame(name, orig[0])
        C.fn('release')(orig[0])
    elif ours:
        C.remove_frame(name)
    if ours:
        C.fn('release')(ours[0])


def load_frames(plist, owner=None):
    """Load a sprite sheet (.plist + the .png next to it) - its frames can be used by name."""
    owner = owner or K.caller_owner()
    p = find_file(plist, owner)
    if not p:
        raise FileNotFoundError('no file %s' % plist)
    C.add_frames_plist(p)


def frame_exists(name):
    return C.frame_exists(str(name))


# ---------------------------------------------------------------- sprites
class _SpriteButton(U.ScreenButton):
    """Click handling for a Sprite; the node itself belongs to the sprite."""

    def __init__(self, sprite):
        super().__init__(sprite.node, sprite._on_click, sprite.owner, sprite._base * sprite._scale)
        self.sprite = sprite

    def alive(self):
        return self.sprite.node is not None and not self.sprite._removed

    def remove(self):
        if self in U.screen_buttons:
            U.screen_buttons.remove(self)
        if self.node:
            node, self.node = self.node, None
            C.fn('release')(node)


def _make_node(image, owner, smooth=True):
    """(node, base_scale). Mod files are shown with 2 pixels = 1 point (like GD's -hd textures)."""
    if isinstance(image, Texture):
        node = C.sprite_from_texture(image.ptr)
        return node, C.content_scale() / 2.0
    name = str(image)
    if C.frame_exists(name):
        return C.fn('spr_frame')(C._enc(name)), 1.0
    p = find_file(name, owner)
    if p and os.path.splitext(p)[1].lower() in IMAGE_EXT:
        tex = C.texture(p)
        if tex:
            C.texture_smooth(tex, smooth)
            return C.sprite_from_texture(tex), C.content_scale() / 2.0
    if C.res_path(name):
        return C.fn('spr_create')(C._enc(name)), 1.0
    raise FileNotFoundError('no picture %r (a GD frame, a file in the mod folder or in Resources)' % name)


class Sprite:
    """A picture on the screen or in the level.

        s = gd.Sprite("star.png", x=100, y=100)              # a file from the mod folder or a GD frame
        s = gd.Sprite("GJ_starsIcon_001.png", world=True)    # in level coordinates
        s.x += 5; s.rotation = 45; s.opacity = 128; s.color = (255, 0, 0)
        s.move_to(200, 150, 0.5); s.spin(90); s.remove()
    """

    def __init__(self, image, x=None, y=None, scale=1.0, world=False, z=None, rotation=0.0, opacity=255,
                 color=None, visible=True, smooth=True, width=None, height=None, flip_x=False, anchor=None,
                 on_click=None, owner=None):
        self.owner = owner or K.caller_owner()
        self.world = bool(world)
        self.z = z if z is not None else (10000 if world else 8000)
        self._image, self._smooth = image, smooth
        w, h = C.win_size() if not world else (0, 0)
        self._x = float(w / 2 if x is None else (w + x if (x < 0 and not world) else x))
        self._y = float(h / 2 if y is None else (h + y if (y < 0 and not world) else y))
        self._scale, self._rot, self._opacity = float(scale), float(rotation), int(opacity)
        self._color = tuple(color)[:3] if color else None
        self._visible, self._flip, self._anchor = bool(visible), bool(flip_x), anchor
        self._fit = (width, height)
        self._on_click = on_click
        self._button = None
        self.node = None
        self._base = 1.0
        self._removed = False
        if self.world:
            self._ensure()
        else:
            self._build()
            K.when_scene_ready(self._attach)

    # --- node life
    def _build(self):
        node, base = _make_node(self._image, self.owner, self._smooth)
        if not node:
            raise OSError('cannot create a sprite from %r' % (self._image,))
        C.fn('retain')(node)
        self.node, self._base = node, base
        fw, fh = self._fit
        if fw or fh:
            nw, nh = C.node_size(node)
            ks = [v / s for v, s in ((fw, nw), (fh, nh)) if v and s]
            if ks:
                self._base = min(ks)
                self._scale = 1.0
        self._apply_all()

    def _apply_all(self):
        n = self.node
        C.fn('set_pos')(n, self._x, self._y)
        C.fn('set_scale')(n, self._base * self._scale)
        C.fn('set_rot')(n, self._rot)
        if self._anchor:
            C.anchor(n, *self._anchor)
        if self._opacity != 255:
            C.fn('spr_opacity')(n, max(0, min(255, self._opacity)))
        if self._color:
            C.fn('spr_color')(n, C.color3(self._color))
        if self._flip:
            C.fn('spr_flipx')(n, True)
        if not self._visible:
            C.fn('set_visible')(n, False)

    def _make_button(self):
        if self._on_click and self.node and not self._button:
            self._button = _SpriteButton(self)

    @property
    def on_click(self):
        return self._on_click

    @on_click.setter
    def on_click(self, func):
        """A function called when the picture is clicked (None - remove)."""
        self._on_click = func
        if self._button:
            self._button.callback = func
            if func is None:
                self._button.remove()
                self._button = None
        elif func and self.node and C.fn('parent')(self.node):
            self._make_button()

    def _attach(self):
        if self._removed or not self.node:
            return
        scene = C.running_scene()
        if scene and not C.fn('parent')(self.node):
            C.fn('add_child')(scene, self.node, self.z)
        if self not in K._persistent:
            K._persistent.append(self)
        self._make_button()

    def _ensure(self):
        """World sprites are created when a level is open (and again in the next level)."""
        if self.node or self._removed:
            return self.node
        if not self.world:
            return None
        st = K.state
        if not (st.started and st.player):
            return None
        parent = C.fn('parent')(st.player.ptr)
        if not parent:
            return None
        self._build()
        C.fn('add_child')(parent, self.node, self.z)
        _world.append(self)
        self._make_button()
        return self.node

    def _drop(self):
        if self in _world:
            _world.remove(self)
        if self in K._persistent:
            K._persistent.remove(self)
        if self._button:
            b, self._button = self._button, None
            b.remove()
        if self.node:
            node, self.node = self.node, None
            C.remove(node, True)
            C.fn('release')(node)

    def remove(self):
        self._removed = True
        self._drop()

    def _set(self, fn_name, *args):
        n = self.node or self._ensure()
        if n:
            C.fn(fn_name)(n, *args)

    # --- properties
    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self.move(v, self._y)

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, v):
        self.move(self._x, v)

    def move(self, x, y):
        self._x, self._y = float(x), float(y)
        self._set('set_pos', self._x, self._y)

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, v):
        self._scale = float(v)
        self._set('set_scale', self._base * self._scale)
        if self._button:
            self._button.scale = self._base * self._scale

    @property
    def rotation(self):
        return self._rot

    @rotation.setter
    def rotation(self, v):
        self._rot = float(v)
        self._set('set_rot', self._rot)

    @property
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, v):
        self._opacity = max(0, min(255, int(v)))
        self._set('spr_opacity', self._opacity)

    @property
    def color(self):
        return self._color or (255, 255, 255)

    @color.setter
    def color(self, rgb):
        self._color = tuple(rgb)[:3]
        n = self.node or self._ensure()
        if n:
            C.fn('spr_color')(n, C.color3(self._color))

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, v):
        self._visible = bool(v)
        self._set('set_visible', self._visible)

    @property
    def flip_x(self):
        return self._flip

    @flip_x.setter
    def flip_x(self, v):
        self._flip = bool(v)
        self._set('spr_flipx', self._flip)

    @property
    def size(self):
        """Size on the screen (in game points)."""
        if not self.node:
            return 0.0, 0.0
        w, h = C.node_size(self.node)
        k = self._base * self._scale
        return w * k, h * k

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, image):
        """Change the picture (position, size and the rest stay)."""
        self._image = image
        if not self.node:
            return
        parent = C.fn('parent')(self.node)
        click, self._on_click = self._on_click, None
        self._drop()
        self._removed = False
        self._on_click = click
        self._build()
        if parent:
            C.fn('add_child')(parent, self.node, self.z)
        if self.world:
            _world.append(self)
        else:
            K._persistent.append(self)
        if parent:
            self._make_button()

    def contains(self, x, y):
        """Is the screen point inside the picture."""
        if not self.node:
            return False
        x0, y0, x1, y1 = C.world_rect(self.node)
        return x0 <= x <= x1 and y0 <= y <= y1

    # --- animations (cocos actions)
    def _run(self, action):
        n = self.node or self._ensure()
        if n and action:
            C.run(n, action)

    def stop(self):
        """Stop animations."""
        if self.node:
            C.fn('stop_all')(self.node)

    def move_to(self, x, y, seconds=0.3):
        self._x, self._y = float(x), float(y)
        self._run(C.fn('ease_sine_out')(C.fn('move_to')(float(seconds), C.point(x, y))))

    def scale_to(self, scale, seconds=0.3):
        self._scale = float(scale)
        self._run(C.fn('scale_to')(float(seconds), float(self._base * scale)))

    def fade_to(self, opacity, seconds=0.3):
        self._opacity = max(0, min(255, int(opacity)))
        self._run(C.fn('fade_to')(float(seconds), self._opacity))

    def rotate_by(self, degrees, seconds=0.3):
        self._rot += float(degrees)
        self._run(C.fn('rotate_by')(float(seconds), float(degrees)))

    def spin(self, degrees_per_second=180):
        """Spin forever (stop() - stop)."""
        self._run(C.fn('repeat_forever')(C.fn('rotate_by')(1.0, float(degrees_per_second))))

    def __repr__(self):
        return '<Sprite %r x=%.1f y=%.1f>' % (self._image, self._x, self._y)


def _on_leave():
    for s in list(_world):
        s._drop()          # created again in the next level when used


def _cleanup(owner):
    for s in list(_world) + [o for o in K._persistent if isinstance(o, Sprite)]:
        if s.owner == owner:
            s.remove()
    for name in [n for n, v in list(_added.items()) if v[1] == owner]:
        try:
            restore_frame(name)
        except Exception:
            traceback.print_exc()


K.leave_hooks.append(_on_leave)
K.cleanup_hooks.append(_cleanup)
