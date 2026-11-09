"""Files of a mod on disk: pymodder/saves/<mod>/. Only .json and .macro files are allowed."""
import atexit
import json
import os
import re
import traceback

from . import _core as K

ALLOWED = ('.json', '.macro')
_BAD = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM%d' % i for i in range(1, 10)} | {'LPT%d' % i for i in range(1, 10)}
_files = []          # open JsonFile objects (saved on unload / exit)


def folder(owner, create=True):
    d = os.path.join(K.ROOT or '.', 'saves', K.mod_name(owner))
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def check_name(name):
    """Relative file name inside the mod folder; subfolders are ok ("runs/best.macro")."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError('the file name must be a string, e.g. "data.json"')
    n = name.replace('\\', '/').strip()
    if n.startswith('/') or ':' in n or _BAD.search(n):
        raise ValueError('bad file name: %r' % name)
    parts = [x for x in n.split('/') if x not in ('', '.')]
    if not parts or any(x == '..' for x in parts):
        raise ValueError('cannot leave the mod folder: %r' % name)
    if any(os.path.splitext(x)[0].upper() in _RESERVED for x in parts):
        raise ValueError('the name is reserved by Windows: %r' % name)
    if os.path.splitext(parts[-1])[1].lower() not in ALLOWED:
        raise ValueError('only .json and .macro files are allowed: %r' % name)
    return '/'.join(parts)


def path(owner, name, create=False):
    p = os.path.join(folder(owner, create), *check_name(name).split('/'))
    if create:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _plain(data):
    to_dict = getattr(data, 'to_dict', None)
    return to_dict() if callable(to_dict) else data


def dumps(name, data):
    data = _plain(data)
    if isinstance(data, dict) and name.lower().endswith('.macro') and isinstance(data.get('inputs'), list):
        # one input per line: readable and diff-friendly
        items = ['%s: %s' % (json.dumps(str(k)), json.dumps(v, ensure_ascii=False))
                 for k, v in data.items() if k != 'inputs']
        rows = [json.dumps(r, separators=(',', ':')) for r in data['inputs']]
        items.append('"inputs": [' + ('\n  ' + ',\n  '.join(rows) + '\n ]' if rows else ']'))
        return '{\n ' + ',\n '.join(items) + '\n}\n'
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def save(owner, name, data):
    p = path(owner, name, create=True)
    text = dumps(name, data)          # fails before the old file is touched
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, p)
    return p


def load(owner, name, default=None):
    p = path(owner, name)
    if not os.path.isfile(p):
        return default
    try:
        with open(p, encoding='utf-8-sig') as f:
            return json.load(f)
    except ValueError as e:
        print('[PyModder] %s: file %s is broken (%s)' % (K.mod_name(owner), name, e))
        return default


def exists(owner, name):
    return os.path.isfile(path(owner, name))


def delete(owner, name):
    p = path(owner, name)
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def list_files(owner, ext=None):
    d = folder(owner, create=False)
    out = []
    if not os.path.isdir(d):
        return out
    for root, _, files in os.walk(d):
        for fn in files:
            e = os.path.splitext(fn)[1].lower()
            if e in ALLOWED and (ext is None or e == ext.lower() or e == '.' + ext.lower().lstrip('.')):
                out.append(os.path.relpath(os.path.join(root, fn), d).replace('\\', '/'))
    return sorted(out, key=str.lower)


class JsonFile(dict):
    """dict that lives in a .json file and saves itself (on the next frame after a change).

        stats = gd.storage.file("stats.json", {"runs": 0})
        stats["runs"] += 1          # saved automatically
        stats["list"].append(5)     # nested change -> call stats.save()
    """

    def __init__(self, owner, name, default=None):
        if not check_name(name).lower().endswith('.json'):
            raise ValueError('gd.storage.file works only with .json')
        super().__init__()
        self.owner, self.name = owner, name
        self._dirty = False
        data = load(owner, name, None)
        if isinstance(default, dict):
            dict.update(self, default)
        if isinstance(data, dict):
            dict.update(self, data)
        _files.append(self)

    @property
    def path(self):
        return path(self.owner, self.name)

    def save(self):
        self._dirty = False
        try:
            save(self.owner, self.name, dict(self))
        except Exception:
            print('[PyModder] %s: cannot save %s' % (K.mod_name(self.owner), self.name))
            traceback.print_exc()

    def reload(self):
        data = load(self.owner, self.name, {})
        dict.clear(self)
        if isinstance(data, dict):
            dict.update(self, data)

    def _changed(self):
        if not self._dirty:
            self._dirty = True
            K.later(lambda: self._dirty and self.save())

    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        self._changed()

    def __delitem__(self, k):
        dict.__delitem__(self, k)
        self._changed()

    def update(self, *a, **kw):
        dict.update(self, *a, **kw)
        self._changed()

    def setdefault(self, k, default=None):
        if k not in self:
            self[k] = default
        return dict.__getitem__(self, k)

    def pop(self, *a):
        r = dict.pop(self, *a)
        self._changed()
        return r

    def popitem(self):
        r = dict.popitem(self)
        self._changed()
        return r

    def clear(self):
        dict.clear(self)
        self._changed()

    def __repr__(self):
        return '<JsonFile %s %s>' % (self.name, dict.__repr__(self))


def flush(owner=None):
    for f in list(_files):
        if owner is None or f.owner == owner:
            if f._dirty:
                f.save()
            if owner is not None:
                _files.remove(f)


K.cleanup_hooks.append(flush)
atexit.register(flush)
