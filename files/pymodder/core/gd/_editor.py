"""Level editor: events (open / exit / playtest / objects placed, removed, moved) and helpers."""
import ctypes
import struct
import traceback

from . import _cocos as C
from . import _core as K
from . import _mem as M
from . import _native as N
from ._nodes import Node
from ._objects import GameObject, read_array, OFF_OBJECTS

state = {'editor': None, 'ui': None}
_installed = set()

# event -> hooks it needs
EVENTS = ('editor_open', 'editor_exit', 'editor_playtest', 'editor_stop_playtest', 'editor_object_added',
          'editor_object_removed', 'editor_object_moved', 'editor_paste')


def editor_ptr():
    e = state['editor']
    if e and M.class_name(e) == 'LevelEditorLayer':
        return e
    sc = C.running_scene()
    if sc:
        for ch in C.children(sc):
            if M.class_name(ch) == 'LevelEditorLayer':
                state['editor'] = ch
                return ch
    state['editor'] = None
    return None


def ui_ptr():
    e = editor_ptr()
    if not e:
        return None
    u = state['ui']
    if u and M.class_name(u) == 'EditorUI' and C.fn('parent')(u) == e:
        return u
    for ch in C.children(e):
        if M.class_name(ch) == 'EditorUI':
            state['ui'] = ch
            return ch
    return None


# ---------------------------------------------------------------- hooks (installed when a mod needs them)
def _h_init(orig, this, level, *rest):
    r = orig()
    if r is not False:
        state['editor'], state['ui'] = this, None
        from . import _levels as L
        lv = L.LevelData(level)
        K.later(lambda: K.emit('editor_open', Editor(this), lv))
    return r


def _h_exit(orig, this, sender):
    ed = editor_ptr()
    lv = Editor(ed).level if ed else None
    K.emit('editor_exit', lv)
    r = orig()
    state['editor'] = state['ui'] = None
    return r


def _h_playtest(orig, this):
    r = orig()
    K.emit('editor_playtest')
    return r


def _h_stop_playtest(orig, this):
    r = orig()
    K.emit('editor_stop_playtest')
    return r


def _h_create(orig, this, obj_id, point, no_undo):
    obj = orig()
    if obj and not _quiet[0]:
        K.emit('editor_object_added', GameObject(obj))
    return obj


def _h_remove(orig, this, obj, no_undo):
    if obj and not _quiet[0]:
        K.emit('editor_object_removed', GameObject(obj))
    return orig()


def _h_move(orig, this, obj, point):
    r = orig()
    if obj and point:
        b = M.read(point, 8)
        dx, dy = struct.unpack('<ff', b) if b else (0.0, 0.0)
        K.emit('editor_object_moved', GameObject(obj), dx, dy)
    return r


def _h_paste(orig, this, text, a, b):
    arr = orig()
    if arr and not _quiet[0]:
        K.emit('editor_paste', [GameObject(p) for p in read_array(arr)])
    return arr


_quiet = [False]
_HOOKS = {
    'editor_open': [('LevelEditorLayer::init', _h_init)],
    'editor_exit': [('EditorPauseLayer::onSaveAndExit', _h_exit), ('EditorPauseLayer::onExitNoSave', _h_exit),
                    ('EditorPauseLayer::onSaveAndPlay', _h_exit)],
    'editor_playtest': [('LevelEditorLayer::onPlaytest', _h_playtest)],
    'editor_stop_playtest': [('LevelEditorLayer::onStopPlaytest', _h_stop_playtest)],
    'editor_object_added': [('LevelEditorLayer::createObject', _h_create)],
    'editor_object_removed': [('LevelEditorLayer::removeObject', _h_remove)],
    'editor_object_moved': [('EditorUI::moveObject', _h_move)],
    'editor_paste': [('EditorUI::pasteObjects', _h_paste)],
}


def need(event):
    """Install the hooks of an editor event (once)."""
    for name, h in _HOOKS.get(event, []):
        if name in _installed:
            continue
        try:
            N.hook(name, h, 'pymodder')
            _installed.add(name)
        except Exception as e:
            print('[PyModder] editor hook %s not installed: %s' % (name, e))
    if event == 'editor_exit':
        need('editor_open')


# ---------------------------------------------------------------- Editor
class Editor(Node):
    """The open level editor (a LevelEditorLayer node). gd.editor() returns it (None outside the editor)."""
    __slots__ = ()

    @property
    def ui(self):
        """EditorUI (the editor buttons) as a Node."""
        u = ui_ptr()
        return Node(u) if u else None

    @property
    def level(self):
        from . import _levels as L
        off = M.find_pointer_to(self.ptr, 'GJGameLevel', 0x100, 0x4000)
        return L.LevelData(M.ptr(self.ptr + off)) if off is not None else None

    def objects(self, object_id=None):
        from . import _objects as O
        return O.objects(object_id, self.ptr)

    @property
    def object_count(self):
        from . import _objects as O
        return O.object_count(self.ptr)

    def add_object(self, object_id, x, y, undo=True):
        """Place an object (level coordinates; one grid cell = 30). Returns the GameObject."""
        pt = C.point(x, y)
        _quiet[0] = False
        p = N.function('LevelEditorLayer::createObject')(self.ptr, int(object_id), pt, not undo)
        return GameObject(p) if p else None

    def remove_object(self, obj, undo=True):
        N.function('LevelEditorLayer::removeObject')(self.ptr, int(obj), not undo)

    @property
    def level_string(self):
        """The level as a GD object string (what the game saves)."""
        f = N.function('LevelEditorLayer::getLevelString')
        return M.returned_string(lambda r: f(self.ptr, r))

    def paste(self, objects_string, undo=True):
        """Add objects from a GD object string ("1,1,2,15,3,15;1,8,2,45,3,15;"). Returns [GameObject]."""
        ui = ui_ptr()
        if not ui:
            raise RuntimeError('no EditorUI')
        s = M.StdString(objects_string)
        try:
            arr = N.function('EditorUI::pasteObjects')(ui, s.addr, False, not undo)
        finally:
            s.free()
        return [GameObject(p) for p in read_array(arr)]

    @property
    def selected(self):
        """Selected objects."""
        ui = ui_ptr()
        if not ui:
            return []
        arr = N.function('EditorUI::getSelectedObjects')(ui)
        return [GameObject(p) for p in read_array(arr)]

    def select(self, objs):
        ui = ui_ptr()
        if not ui:
            return
        objs = list(objs)
        if len(objs) == 1:
            N.function('EditorUI::selectObject')(ui, int(objs[0]), True)
            return
        from . import _nodes as Nd
        arr = Nd._x('arr_create')()
        for o in objs:
            Nd._x('arr_add')(arr, int(o))
        N.function('EditorUI::selectObjects')(ui, arr, True)

    def deselect(self):
        ui = ui_ptr()
        if ui:
            N.function('EditorUI::deselectAll')(ui)

    def move_object(self, obj, dx, dy):
        ui = ui_ptr()
        if ui:
            N.function('EditorUI::moveObject')(ui, int(obj), C.point(dx, dy))

    def update_buttons(self):
        ui = ui_ptr()
        if ui:
            N.function('EditorUI::updateButtons')(ui)

    def playtest(self):
        N.function('LevelEditorLayer::onPlaytest')(self.ptr)

    def stop_playtest(self):
        N.function('LevelEditorLayer::onStopPlaytest')(self.ptr)

    def save(self):
        return bool(N.function('LevelEditorLayer::saveLevel')(self.ptr))

    def undo(self):
        N.function('LevelEditorLayer::undoLastAction')(self.ptr)

    def redo(self):
        N.function('LevelEditorLayer::redoLastAction')(self.ptr)


def editor():
    p = editor_ptr()
    return Editor(p) if p else None
