"""Pictures from bytes / files / the internet: PNG, JPG, animated GIF (decoded here, no extra libraries)."""
import hashlib
import os
import struct
import zlib

from . import _core as K

IMG_TYPES = {b'\x89PNG': '.png', b'\xff\xd8\xff': '.jpg', b'GIF8': '.gif', b'II*\x00': '.tiff',
             b'MM\x00*': '.tiff'}


def sniff(data):
    for magic, ext in IMG_TYPES.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    if data[:2] == b'BM':
        return '.bmp'
    return None


# ---------------------------------------------------------------- PNG writer
def encode_png(w, h, rgba, level=6):
    """RGBA bytes (w*h*4) -> PNG file bytes."""
    stride = w * 4
    raw = bytearray()
    mv = memoryview(rgba)
    for y in range(h):
        raw.append(0)
        raw += mv[y * stride:(y + 1) * stride]

    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(bytes(raw), level)) + chunk(b'IEND', b''))


# ---------------------------------------------------------------- GIF reader
def _lzw(data, min_size, npix):
    """GIF LZW decoder -> bytes of palette indices."""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    out = bytearray()
    size = min_size + 1
    table = [bytes((i,)) for i in range(clear)] + [b'', b'']
    prev = None
    bitbuf = nbits = 0
    pos, n = 0, len(data)
    mask = (1 << size) - 1
    while True:
        while nbits < size and pos < n:
            bitbuf |= data[pos] << nbits
            nbits += 8
            pos += 1
        if nbits < size:
            break
        code = bitbuf & mask
        bitbuf >>= size
        nbits -= size
        if code == clear:
            table = table[:clear + 2]
            size = min_size + 1
            mask = (1 << size) - 1
            prev = None
            continue
        if code == eoi:
            break
        if prev is None:
            entry = table[code]
            out += entry
            prev = entry
            continue
        if code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)
        out += entry
        prev = entry
        if len(table) == (1 << size) and size < 12:
            size += 1
            mask = (1 << size) - 1
        if len(out) >= npix:
            break
    if len(out) < npix:
        out += bytes(npix - len(out))
    return bytes(out[:npix])


def _deinterlace(idx, w, h):
    rows = [idx[i * w:(i + 1) * w] for i in range(h)]
    order = list(range(0, h, 8)) + list(range(4, h, 8)) + list(range(2, h, 4)) + list(range(1, h, 2))
    out = [b''] * h
    for src, dst in enumerate(order):
        out[dst] = rows[src]
    return b''.join(out)


def _rgba_tables(palette, transparent):
    n = len(palette) // 3
    r = bytearray(256)
    g = bytearray(256)
    b = bytearray(256)
    a = bytearray(256)
    for i in range(min(n, 256)):
        r[i], g[i], b[i], a[i] = palette[3 * i], palette[3 * i + 1], palette[3 * i + 2], 255
    if transparent is not None:
        a[transparent] = 0
    return bytes(r), bytes(g), bytes(b), bytes(a)


def decode_gif(data, max_frames=300):
    """GIF bytes -> (width, height, [(rgba bytes, delay seconds)]). Every frame is the full picture."""
    if data[:4] != b'GIF8':
        raise ValueError('not a GIF')
    W, H, flags, bg, _ = struct.unpack('<HHBBB', data[6:13])
    pos = 13
    gpal = None
    if flags & 0x80:
        n = 3 << ((flags & 7) + 1)
        gpal = data[pos:pos + n]
        pos += n
    canvas = bytearray(W * H * 4)
    frames = []
    delay, transparent, disposal = 0.1, None, 0
    while pos < len(data) and len(frames) < max_frames:
        block = data[pos]
        pos += 1
        if block == 0x3B:
            break
        if block == 0x21:
            label = data[pos]
            pos += 1
            sub = []
            while pos < len(data):
                ln = data[pos]
                pos += 1
                if not ln:
                    break
                sub.append(data[pos:pos + ln])
                pos += ln
            if label == 0xF9 and sub and len(sub[0]) >= 4:
                pf, d, t = struct.unpack('<BHB', sub[0][:4])
                disposal = (pf >> 2) & 7
                transparent = t if pf & 1 else None
                delay = (d or 10) / 100.0
            continue
        if block != 0x2C:
            break
        fx, fy, fw, fh, ff = struct.unpack('<HHHHB', data[pos:pos + 9])
        pos += 9
        pal = gpal
        if ff & 0x80:
            n = 3 << ((ff & 7) + 1)
            pal = data[pos:pos + n]
            pos += n
        min_size = data[pos]
        pos += 1
        chunks = []
        while pos < len(data):
            ln = data[pos]
            pos += 1
            if not ln:
                break
            chunks.append(data[pos:pos + ln])
            pos += ln
        idx = _lzw(b''.join(chunks), min_size, fw * fh)
        if ff & 0x40:
            idx = _deinterlace(idx, fw, fh)
        before = bytes(canvas) if disposal == 3 else None
        _blit(canvas, W, H, idx, fx, fy, fw, fh, pal or bytes(768), transparent)
        frames.append((bytes(canvas), max(0.02, delay)))
        if disposal == 2:
            _clear(canvas, W, H, fx, fy, fw, fh)
        elif disposal == 3 and before is not None:
            canvas[:] = before
        delay, transparent, disposal = 0.1, None, 0
    if not frames:
        raise ValueError('GIF without frames')
    return W, H, frames


def _blit(canvas, W, H, idx, fx, fy, fw, fh, pal, transparent):
    tr, tg, tb, ta = _rgba_tables(pal, transparent)
    w = min(fw, W - fx)
    if w <= 0:
        return
    mask_tab = None
    if transparent is not None:
        mt = bytearray(b'\xff' * 256)
        mt[transparent] = 0
        mask_tab = bytes(mt)
    row = bytearray(w * 4)
    for y in range(fh):
        cy = fy + y
        if cy >= H:
            break
        line = idx[y * fw:y * fw + w]
        row[0::4] = line.translate(tr)
        row[1::4] = line.translate(tg)
        row[2::4] = line.translate(tb)
        row[3::4] = line.translate(ta)
        start = (cy * W + fx) * 4
        if mask_tab is not None and transparent in line:
            m1 = line.translate(mask_tab)
            m = bytearray(w * 4)
            m[0::4] = m1
            m[1::4] = m1
            m[2::4] = m1
            m[3::4] = m1
            mi = int.from_bytes(m, 'big')
            full = (1 << (w * 32)) - 1
            old = int.from_bytes(canvas[start:start + w * 4], 'big')
            new = (int.from_bytes(row, 'big') & mi) | (old & (full ^ mi))
            canvas[start:start + w * 4] = new.to_bytes(w * 4, 'big')
        else:
            canvas[start:start + w * 4] = row


def _clear(canvas, W, H, fx, fy, fw, fh):
    w = min(fw, W - fx)
    if w <= 0:
        return
    z = bytes(w * 4)
    for y in range(fy, min(fy + fh, H)):
        s = (y * W + fx) * 4
        canvas[s:s + w * 4] = z


def gif_sheet(data, max_size=4096, max_frames=300):
    """GIF -> (png bytes of a grid of frames, frame w, h, columns, [delays])."""
    W, H, frames = decode_gif(data, max_frames)
    step = 1
    while True:
        fr = frames[::step]
        n = len(fr)
        cols = max(1, min(n, max_size // max(W, 1)))
        rows = -(-n // cols)
        if rows * H <= max_size or n == 1:
            break
        step += 1
    delays = [sum(d for _, d in frames[i:i + step]) for i in range(0, len(frames), step)][:n]
    sw, sh = cols * W, rows * H
    sheet = bytearray(sw * sh * 4)
    for i, (px, _) in enumerate(fr):
        cx, cy = (i % cols) * W, (i // cols) * H
        for y in range(H):
            d = ((cy + y) * sw + cx) * 4
            sheet[d:d + W * 4] = px[y * W * 4:(y + 1) * W * 4]
    return encode_png(sw, sh, sheet), W, H, cols, delays


# ---------------------------------------------------------------- cache + textures
def cache_dir():
    d = os.path.join(K.ROOT or '.', 'cache', 'images')
    os.makedirs(d, exist_ok=True)
    return d


def _key(src):
    return hashlib.sha1(src if isinstance(src, bytes) else str(src).encode('utf-8')).hexdigest()[:20]


def prepare(data, key=None):
    """Image bytes -> (path of a file cocos2d can load, gif info or None). Runs in any thread."""
    ext = sniff(data)
    if ext is None:
        raise ValueError('unknown picture format')
    key = key or _key(data)
    d = cache_dir()
    if ext == '.gif':
        path = os.path.join(d, key + '_gif.png')
        meta = path + '.txt'
        if not (os.path.isfile(path) and os.path.isfile(meta)):
            png, w, h, cols, delays = gif_sheet(data)
            with open(path, 'wb') as f:
                f.write(png)
            with open(meta, 'w') as f:
                f.write('%d %d %d %s' % (w, h, cols, ','.join('%.3f' % x for x in delays)))
        w, h, cols, ds = open(meta).read().split(' ')
        return path, (int(w), int(h), int(cols), [float(x) for x in ds.split(',') if x])
    if ext == '.bmp':
        raise ValueError('BMP is not supported (use PNG / JPG / GIF)')
    path = os.path.join(d, key + ext)
    if not os.path.isfile(path):
        with open(path, 'wb') as f:
            f.write(data)
    return path, None


class Picture:
    """A loaded picture: .texture (gd.Texture), .frames (sprite frame pointers; >1 for a GIF),
    .delays, .size. picture.sprite() -> gd.Node (animated if it is a GIF)."""

    def __init__(self, path, gif=None, smooth=True):
        from . import _media as MD
        from . import _cocos as C
        self.path = path
        self.texture = MD.Texture(path, smooth)
        self.frames, self.delays = [], []
        k = C.content_scale()
        if gif:
            w, h, cols, delays = gif
            for i, d in enumerate(delays):
                x, y = (i % cols) * w, (i // cols) * h
                fr = C.frame_from_texture(self.texture.ptr, (x / k, y / k, w / k, h / k))
                if fr:
                    C.fn('retain')(fr)
                    self.frames.append(fr)
                    self.delays.append(d)
            self.size = (w, h)
        else:
            fr = C.frame_from_texture(self.texture.ptr)
            if fr:
                C.fn('retain')(fr)
                self.frames.append(fr)
            self.size = self.texture.size
        self.animated = len(self.frames) > 1

    @property
    def fps(self):
        if not self.delays:
            return 10.0
        return len(self.delays) / max(0.02, sum(self.delays))

    def sprite(self, width=None, height=None):
        """A new sprite node (gd.Node) showing the picture; GIFs play in a loop."""
        from . import _cocos as C
        from . import _nodes as Nd
        p = C.fn('spr_with_tex')(self.texture.ptr)
        n = Nd.Node(p)
        if self.frames:
            n.set_frame(self.frames[0])
        if self.animated:
            n.animate(self.frames, self.fps)
        fit(n, width, height)
        return n

    def add_frame(self, name):
        """Register the first frame under a sprite frame name (replaces a GD frame with this name)."""
        from . import _cocos as C
        C.add_frame(name, self.frames[0])
        return name


def fit(node, width=None, height=None):
    w, h = node.size
    if width and height:
        node.scale = min(width / max(w, 1), height / max(h, 1))
    elif width:
        node.scale = width / max(w, 1)
    elif height:
        node.scale = height / max(h, 1)
    return node


_pictures = {}


def load_bytes(data, key=None, smooth=True):
    """On the game thread: bytes -> Picture."""
    path, gif = prepare(data, key)
    return _picture(path, gif, smooth)


def _picture(path, gif, smooth=True):
    pic = _pictures.get(path)
    if pic is None:
        pic = _pictures[path] = Picture(path, gif, smooth)
    return pic


def load_file(path, smooth=True):
    with open(path, 'rb') as f:
        data = f.read()
    if sniff(data) == '.gif':
        return load_bytes(data, _key(os.path.abspath(path) + str(os.path.getmtime(path))), smooth)
    return _picture(os.path.abspath(path), None, smooth)


def load_url(url, on_done, keep=None, owner=None, smooth=True):
    """Download a picture (cached on disk) -> on_done(picture or None, error)."""
    from . import _net
    from . import _ui as U
    owner = owner or K.caller_owner()
    key = _key(url)

    def work():
        for f in os.listdir(cache_dir()):
            if f.startswith(key) and not f.endswith('.txt'):
                if f.endswith('_gif.png') and os.path.isfile(os.path.join(cache_dir(), f + '.txt')):
                    w, h, cols, ds = open(os.path.join(cache_dir(), f + '.txt')).read().split(' ')
                    return os.path.join(cache_dir(), f), (int(w), int(h), int(cols),
                                                         [float(x) for x in ds.split(',') if x]), None
                if not f.endswith('_gif.png'):
                    return os.path.join(cache_dir(), f), None, None
        r = _net.request('GET', url, timeout=30)
        if not r.ok:
            return None, None, r.error or 'HTTP %s' % r.status
        try:
            path, gif = prepare(r.data, key)
        except Exception as e:
            return None, None, str(e)
        return path, gif, None

    def done(res):
        path, gif, err = res
        pic = None
        if path:
            try:
                pic = _picture(path, gif, smooth)
            except Exception as e:
                err = str(e)
        U.flex_call(owner, on_done, pic, err)
    return _net._async(owner, work, done, keep)
