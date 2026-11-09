"""Level objects (GameObject), hitboxes, the level's world layer."""
import struct

from . import _core as K
from . import _mem as M
from . import _native as N
from ._nodes import Node, vcall

OFF_OBJECTS = 0xdd0         # GJBaseGameLayer::m_objects (CCArray*)
OFF_OBJECT_LAYER = 0x10c8   # GJBaseGameLayer::m_objectLayer (moves with the camera)
OFF_TYPE, OFF_ID = 0x3a0, 0x40c
START_POS_ID = 31


def read_array(arr, limit=1000000):
    """CCArray* -> [pointers] (reads the array memory directly, fast)."""
    if not arr:
        return []
    data = M.ptr(arr + 0x38)
    if not data:
        return []
    n = M.u32(data) or 0
    items = M.ptr(data + 0x10)
    if not n or not items:
        return []
    n = min(n, limit)
    raw = M.read(items, 8 * n)
    return list(struct.unpack('<%dQ' % n, raw)) if raw else []


class GameObject(Node):
    """A level object (block, spike, orb, trigger...). It is a Node too (x, y, rotation, scale, visible...)."""
    __slots__ = ()

    @property
    def object_id(self):
        """Object ID (1 = the default block, 8 = spike, 31 = start position...)."""
        return M.i32(self.ptr + OFF_ID)

    @property
    def type(self):
        """GameObjectType number (0 solid, 2 hazard, ...)."""
        return M.i32(self.ptr + OFF_TYPE)

    @property
    def rect(self):
        """Hitbox (x, y, width, height) in level coordinates."""
        p = N.function('GameObject::getObjectRect')(self.ptr)
        return struct.unpack('<4f', M.read(p, 16)) if p else (0.0, 0.0, 0.0, 0.0)

    @property
    def hidden(self):
        return not self.visible

    def __repr__(self):
        return '<GameObject id=%s at (%.0f, %.0f)>' % (self.object_id, self.x, self.y)


def _layer(layer=None):
    if layer is not None:
        return int(layer)
    s = K.state
    if s.layer:
        return s.layer
    from . import _editor as E
    return E.editor_ptr()


def objects(object_id=None, layer=None, where=None):
    """Objects of the open level (or the editor): gd.objects(), gd.objects(31) (start positions)."""
    lay = _layer(layer)
    if not lay:
        return []
    ids = None
    if object_id is not None:
        ids = {object_id} if isinstance(object_id, int) else set(object_id)
    out = []
    for p in read_array(M.ptr(lay + OFF_OBJECTS)):
        if ids is not None and M.i32(p + OFF_ID) not in ids:
            continue
        o = GameObject(p)
        if where is None or where(o):
            out.append(o)
    return out


def object_count(layer=None):
    lay = _layer(layer)
    arr = M.ptr(lay + OFF_OBJECTS) if lay else 0
    data = M.ptr(arr + 0x38) if arr else 0
    return (M.u32(data) or 0) if data else 0


def start_positions(layer=None):
    return sorted(objects(START_POS_ID, layer), key=lambda o: o.x)


def world_layer(layer=None):
    """The node that holds the level objects: add nodes to it and they move with the level."""
    lay = _layer(layer)
    p = M.ptr(lay + OFF_OBJECT_LAYER) if lay else 0
    return Node(p) if p else None


def add_to_world(node, z=100, x=None, y=None):
    w = world_layer()
    if not w:
        raise RuntimeError('no level is open')
    return w.add(node, z, x=x, y=y)


# ---------------------------------------------------------------- hitboxes
_hitbox_owners = set()
_hb_hooked = [False]


def _h_should_draw(orig, this):
    if _hitbox_owners:
        return True
    return orig()


def show_hitboxes(on=True, owner='pymodder'):
    """Show hitboxes in normal mode too (like the practice-mode option)."""
    if not _hb_hooked[0]:
        N.hook('PlayLayer::shouldDrawDebugHitboxes', _h_should_draw, 'pymodder')
        K.attempt_listeners.append(_refresh_debug)
        _hb_hooked[0] = True
    if on:
        _hitbox_owners.add(owner)
    else:
        _hitbox_owners.discard(owner)
    _refresh_debug()


def hitboxes_shown():
    return bool(_hitbox_owners)


def _refresh_debug():
    lay = K.state.layer
    if lay and M.class_name(lay) == 'PlayLayer':
        try:
            N.function('PlayLayer::toggleDebugDraw')(lay)
        except Exception:
            pass


def _forget(owner):
    if owner in _hitbox_owners:
        _hitbox_owners.discard(owner)
        _refresh_debug()


K.cleanup_hooks.append(_forget)
