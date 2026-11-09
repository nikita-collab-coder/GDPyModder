"""Internet: simple HTTP requests (in a background thread, the callback runs on the game thread) and
the Geometry Dash servers (users, icons, levels)."""
import gzip
import http.client
import json as _json
import os
import ssl
import threading
import traceback
import urllib.parse
import zlib

from . import _core as K

_ctx = [None]


def _ssl_ctx():
    if _ctx[0] is None:
        try:
            _ctx[0] = ssl.create_default_context()
        except Exception:
            _ctx[0] = ssl._create_unverified_context()
    return _ctx[0]


class Response:
    """Result of a request: .ok, .status, .data (bytes), .text, .json(), .headers, .error, .url"""

    def __init__(self, url, status=0, data=b'', headers=None, error=None):
        self.url, self.status, self.data, self.headers, self.error = url, status, data, headers or {}, error

    @property
    def ok(self):
        return self.error is None and 200 <= self.status < 300

    @property
    def text(self):
        ct = self.headers.get('content-type', '')
        enc = 'utf-8'
        if 'charset=' in ct:
            enc = ct.split('charset=')[-1].split(';')[0].strip() or 'utf-8'
        try:
            return self.data.decode(enc, 'replace')
        except LookupError:
            return self.data.decode('utf-8', 'replace')

    def json(self):
        return _json.loads(self.text)

    def __repr__(self):
        return '<Response %s %s%s>' % (self.status, self.url, ' error=%s' % self.error if self.error else '')

    def __bool__(self):
        return self.ok


def request(method, url, data=None, headers=None, timeout=20, max_redirects=5, user_agent='PyModder'):
    """Blocking request (use it in gd.background or pass a callback to get / post)."""
    body = None
    hdrs = {'Accept-Encoding': 'gzip, deflate', 'Connection': 'close'}
    if user_agent:
        hdrs['User-Agent'] = user_agent
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
        hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
    elif isinstance(data, str):
        body = data.encode('utf-8')
        hdrs['Content-Type'] = 'text/plain; charset=utf-8'
    elif data is not None:
        body = bytes(data)
    for k, v in (headers or {}).items():
        if v is None:
            hdrs.pop(k, None)
        else:
            hdrs[k] = v
    for _ in range(max_redirects + 1):
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ('http', 'https'):
            return Response(url, error='bad url: ' + url)
        cls = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
        kw = {'context': _ssl_ctx()} if u.scheme == 'https' else {}
        conn = cls(u.hostname, u.port, timeout=timeout, **kw)
        try:
            path = (u.path or '/') + ('?' + u.query if u.query else '')
            conn.putrequest(method, path, skip_accept_encoding=True)
            for k, v in hdrs.items():
                conn.putheader(k, v)
            if body is not None:
                conn.putheader('Content-Length', str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            raw = r.read()
            h = {k.lower(): v for k, v in r.getheaders()}
            if r.status in (301, 302, 303, 307, 308) and h.get('location'):
                url = urllib.parse.urljoin(url, h['location'])
                if r.status == 303:
                    method, body = 'GET', None
                continue
            enc = h.get('content-encoding', '')
            if 'gzip' in enc:
                raw = gzip.decompress(raw)
            elif 'deflate' in enc:
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -15)
            return Response(url, r.status, raw, h)
        except Exception as e:
            return Response(url, error='%s: %s' % (type(e).__name__, e))
        finally:
            conn.close()
    return Response(url, error='too many redirects')


def _async(owner, work, on_done, keep=None):
    """Run work() in a thread, then on_done(result) on the game thread. keep: a node kept alive meanwhile."""
    from . import _cocos as C
    from . import _ui as U
    kp = int(keep) if keep else 0
    if kp:
        C.fn('retain')(kp)

    def run():
        try:
            res = work()
        except Exception as e:
            traceback.print_exc()
            res = Response('', error='%s: %s' % (type(e).__name__, e))

        def done():
            try:
                if on_done is not None:
                    U.flex_call(owner, on_done, res)
            finally:
                if kp:
                    C.fn('release')(kp)
        K.later(done)
    t = threading.Thread(target=run, daemon=True, name='pymodder-net')
    t.start()
    return t


def get(url, on_done=None, headers=None, timeout=20, keep=None, owner=None):
    """gd.http.get(url, on_done): on_done(response) runs on the game thread. Without on_done it blocks."""
    if on_done is None:
        return request('GET', url, None, headers, timeout)
    return _async(owner or K.caller_owner(), lambda: request('GET', url, None, headers, timeout), on_done, keep)


def post(url, data=None, on_done=None, headers=None, timeout=20, keep=None, owner=None):
    if on_done is None:
        return request('POST', url, data, headers, timeout)
    return _async(owner or K.caller_owner(), lambda: request('POST', url, data, headers, timeout), on_done, keep)


def download(url, path, on_done=None, keep=None, owner=None):
    """Save a URL to a file. on_done(ok, path)."""
    owner = owner or K.caller_owner()

    def work():
        r = request('GET', url, timeout=60)
        if r.ok:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(r.data)
        return r
    if on_done is None:
        return work().ok
    return _async(owner, work, lambda r: on_done(r.ok, path), keep)


class _Http:
    get = staticmethod(get)
    post = staticmethod(post)
    download = staticmethod(download)
    request = staticmethod(request)
    Response = Response


http = _Http()

# ---------------------------------------------------------------- Geometry Dash servers
SERVER = 'https://www.boomlings.com/database/'
SECRET = 'Wmfd2893gb7'
COMMON = {'gameVersion': '22', 'binaryVersion': '45', 'secret': SECRET}
USER_KEYS = {'1': 'name', '2': 'user_id', '3': 'stars', '4': 'demons', '8': 'creator_points', '10': 'color1',
             '11': 'color2', '13': 'coins', '16': 'account_id', '17': 'user_coins', '21': 'cube', '22': 'ship',
             '23': 'ball', '24': 'ufo', '25': 'wave', '26': 'robot', '28': 'glow', '30': 'rank', '43': 'spider',
             '46': 'diamonds', '48': 'death', '51': 'glow_color', '52': 'moons', '53': 'swing', '54': 'jetpack',
             '14': 'icon_type', '15': 'special', '20': 'youtube', '44': 'twitter', '45': 'twitch'}
LEVEL_KEYS = {'1': 'id', '2': 'name', '3': 'description_raw', '4': 'level_string_raw', '5': 'version',
              '6': 'user_id', '8': 'difficulty_denominator', '9': 'difficulty_numerator', '10': 'downloads',
              '12': 'official_song', '13': 'game_version', '14': 'likes', '15': 'length', '17': 'demon',
              '18': 'stars', '19': 'featured', '25': 'auto', '30': 'original_id', '31': 'two_player',
              '35': 'song_id', '37': 'coins', '38': 'coins_verified', '39': 'requested_stars', '42': 'epic',
              '43': 'demon_type', '45': 'object_count', '46': 'edit_time', '47': 'edit_time_copies'}


def parse_kv(text, sep=':'):
    """GD server answer "1:abc:2:15" -> {'1': 'abc', '2': '15'}."""
    a = text.split(sep)
    return {a[i]: a[i + 1] for i in range(0, len(a) - 1, 2)}


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def _named(d, keys):
    out = {}
    for k, v in d.items():
        out[keys.get(k, k)] = _num(v)
    return out


def _gd(endpoint, params):
    data = dict(COMMON)
    data.update(params)
    r = request('POST', SERVER + endpoint, data, headers={'Accept': '*/*'}, user_agent='')
    if not r.ok:
        return None, r.error or 'HTTP %s' % r.status
    t = r.text.strip()
    if not t or t.lstrip('-').isdigit() and t.startswith('-'):
        return None, 'server answered %s' % (t or 'nothing')
    return t, None


def _user_info(t):
    d = _named(parse_kv(t.split('#')[0]), USER_KEYS)
    if 'glow' in d:
        d['glow'] = bool(d['glow'])
    return d


def _level_info(t):
    from . import _levels as L
    d = _named(parse_kv(t), LEVEL_KEYS)
    if isinstance(d.get('description_raw'), str):
        d['description'] = L.decode_b64(d['description_raw'])
    num, den = d.get('difficulty_numerator') or 0, d.get('difficulty_denominator') or 0
    if d.get('auto'):
        d['difficulty'] = 'Auto'
    elif d.get('demon'):
        d['difficulty'] = L.DEMONS.get(d.get('demon_type'), 'Hard Demon')
    else:
        i = num // den if isinstance(num, int) and isinstance(den, int) and den else 0
        d['difficulty'] = L.DIFFICULTIES[i] if 0 <= i < 6 else 'N/A'
    ln = d.get('length')
    d['length_name'] = L.LENGTHS[ln] if isinstance(ln, int) and 0 <= ln < 6 else '?'
    return d


class _Servers:
    """gd.servers.get_user("RobTop", on_done) etc. on_done(result, error) runs on the game thread;
    result is a dict (or a list), None on error."""

    def _call(self, work, on_done, keep, owner):
        owner = owner or K.caller_owner(3)
        if on_done is None:
            return work()

        def wrap(res):
            from . import _ui as U
            U.flex_call(owner, on_done, *res)
        return _async(owner, work, wrap, keep)

    def get_user(self, name_or_id, on_done=None, keep=None, owner=None):
        """Search a player by name: {'name', 'account_id', 'user_id', 'stars', 'cube', ...}."""
        def work():
            t, err = _gd('getGJUsers20.php', {'str': str(name_or_id), 'page': '0'})
            if err:
                return None, err
            return _user_info(t.split('|')[0]), None
        return self._call(work, on_done, keep, owner)

    def get_user_info(self, account_id, on_done=None, keep=None, owner=None):
        """Full profile with all icons: {'cube', 'ship', 'ball', ..., 'color1', 'color2', 'glow', ...}."""
        def work():
            t, err = _gd('getGJUserInfo20.php', {'targetAccountID': str(int(account_id))})
            if err:
                return None, err
            return _user_info(t), None
        return self._call(work, on_done, keep, owner)

    def search_levels(self, query='', on_done=None, page=0, kind=0, keep=None, owner=None, **filters):
        """Levels by name or id: [dict]. kind: 0 search, 1 most downloaded, 2 most liked, 3 trending,
        4 recent, 5 by user (query = user id), 6 featured, 16 hall of fame..."""
        def work():
            p = {'str': str(query), 'type': str(kind), 'page': str(page)}
            p.update({k: str(v) for k, v in filters.items()})
            t, err = _gd('getGJLevels21.php', p)
            if err:
                return None, err
            sections = t.split('#')
            levels = [_level_info(x) for x in sections[0].split('|') if x]
            users = {}
            if len(sections) > 1:
                for u in sections[1].split('|'):
                    a = u.split(':')
                    if len(a) >= 3:
                        users[_num(a[0])] = {'name': a[1], 'account_id': _num(a[2])}
            for lv in levels:
                u = users.get(lv.get('user_id'))
                if u:
                    lv['creator'], lv['account_id'] = u['name'], u['account_id']
            return levels, None
        return self._call(work, on_done, keep, owner)

    def get_level(self, level_id, on_done=None, keep=None, owner=None):
        def work():
            res, err = self.search_levels(str(level_id), None, owner='pymodder')
            if err or not res:
                return None, err or 'not found'
            return res[0], None
        return self._call(work, on_done, keep, owner)

    def download_level(self, level_id, on_done=None, keep=None, owner=None):
        """Level with its data: dict with 'level_string' (decoded object string)."""
        def work():
            from . import _levels as L
            t, err = _gd('downloadGJLevel22.php', {'levelID': str(int(level_id))})
            if err:
                return None, err
            d = _level_info(t.split('#')[0])
            try:
                d['level_string'] = L.decode_level_string(d.get('level_string_raw') or '')
            except Exception:
                d['level_string'] = ''
            return d, None
        return self._call(work, on_done, keep, owner)

    def request(self, endpoint, params, on_done=None, keep=None, owner=None):
        """Any endpoint: gd.servers.request("getGJScores20.php", {...}, on_done) -> (text, error)."""
        return self._call(lambda: _gd(endpoint, params), on_done, keep, owner)


servers = _Servers()
