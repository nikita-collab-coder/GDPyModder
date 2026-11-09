"""Parser for Geode .bro binding files -> {"Class::method": [rva, ret, [params], flags]}.

Only Windows addresses are used. flags: "s" static, "v" virtual, "c" const.
"""
import re

_CLASS = re.compile(r'^\s*class\s+([\w:]+)\s*(?::\s*([^{]*))?\{')
_FUNC = re.compile(r'^\s*((?:(?:static|virtual|callback)\s+)*)(.*?)\b(~?[A-Za-z_]\w*)\s*\((.*)\)\s*(const)?\s*=\s*([^;{]*)')
_WIN = re.compile(r'\bwin\s+(0x[0-9a-fA-F]+)')


def _split_params(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '<([':
            depth += 1
        elif ch in '>)]':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [p.strip() for p in out]


_KEYWORDS = {'int', 'char', 'long', 'short', 'double', 'float', 'bool', 'unsigned', 'signed', 'const', 'void'}


def param_type(p):
    p = p.split('=')[0].strip()
    m = re.match(r'^(.*?[\s*&>])([A-Za-z_]\w*)$', p)
    if m and m.group(2) not in _KEYWORDS and m.group(1).strip() not in ('', 'unsigned', 'signed', 'const'):
        p = m.group(1)
    return re.sub(r'\s+', ' ', p.replace(' *', '*').replace(' &', '&')).strip()


def parse(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    funcs, classes = {}, set()
    cls, depth = None, 0
    for raw in text.split('\n'):
        line = raw.split('//')[0]
        if depth == 0:
            m = _CLASS.match(line)
            if m:
                cls = m.group(1)
                classes.add(cls)
        elif depth == 1 and cls:
            m = _FUNC.match(line)
            if m:
                w = _WIN.search(m.group(6))
                if w:
                    quals, ret, name, params, const = m.group(1), m.group(2).strip(), m.group(3), m.group(4), m.group(5)
                    flags = ('s' if 'static' in quals else '') + ('v' if 'virtual' in quals else '') + ('c' if const else '')
                    plist = [param_type(p) for p in _split_params(params) if p.strip() and p.strip() != 'void']
                    if name == cls.split('::')[-1] or name.startswith('~'):
                        ret = 'void'
                    key = cls + '::' + name
                    entry = [int(w.group(1), 16), re.sub(r'\s+', ' ', ret.replace(' *', '*')), plist, flags]
                    if key in funcs:  # overloads: key with signature
                        key = key + '(' + ', '.join(plist) + ')'
                    funcs[key] = entry
        depth += line.count('{') - line.count('}')
        if depth <= 0:
            depth, cls = 0, None
    return funcs, sorted(classes)
