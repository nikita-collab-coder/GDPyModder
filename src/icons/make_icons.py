"""PyModder icon generator: GD-style tiles (rounded square, gradient, thick black outline, gloss)
with a white glyph (black outline + shadow). 128x128 PNGs.
    python make_icons.py            -> res/icons/*.png, mod icons, preview.png
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageChops

S = 4                    # supersampling
N = 128 * S
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pymodder')

TILES = {   # name -> (top color, bottom color)
    'red': ((255, 112, 112), (140, 38, 38)), 'orange': ((255, 190, 80), (196, 104, 10)),
    'yellow': ((255, 232, 90), (190, 140, 0)), 'green': ((120, 236, 130), (32, 140, 52)),
    'teal': ((80, 226, 214), (12, 130, 132)), 'cyan': ((96, 232, 255), (0, 140, 190)),
    'blue': ((110, 190, 255), (26, 92, 196)), 'navy': ((110, 140, 255), (34, 40, 160)),
    'purple': ((200, 150, 255), (110, 52, 190)), 'pink': ((255, 140, 220), (186, 40, 140)),
    'grey': ((190, 200, 220), (84, 94, 120)), 'sky': ((150, 220, 255), (60, 130, 220)),
    'lime': ((200, 255, 110), (80, 160, 20)), 'magenta': ((255, 120, 255), (150, 30, 170)),
    'brown': ((230, 170, 110), (130, 74, 30)), 'dark': ((120, 130, 160), (36, 40, 60)),
}
WHITE = (255, 255, 255, 255)
GOLD = (255, 214, 60, 255)


def sc(v):
    return v * S


class G:
    """Glyph canvas: layers of (mask, color). Coordinates in 0..128."""

    def __init__(self):
        self.layers = []
        self.new(WHITE)

    def new(self, color=WHITE):
        m = Image.new('L', (N, N), 0)
        self.layers.append([m, color])
        self.d = ImageDraw.Draw(m)
        return self

    def _f(self, cut):
        return 0 if cut else 255

    def circle(self, cx, cy, r, cut=False):
        self.d.ellipse([sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)], fill=self._f(cut))

    def ellipse(self, x0, y0, x1, y1, cut=False):
        self.d.ellipse([sc(x0), sc(y0), sc(x1), sc(y1)], fill=self._f(cut))

    def rect(self, x0, y0, x1, y1, cut=False):
        self.d.rectangle([sc(x0), sc(y0), sc(x1), sc(y1)], fill=self._f(cut))

    def rrect(self, x0, y0, x1, y1, r, cut=False):
        self.d.rounded_rectangle([sc(x0), sc(y0), sc(x1), sc(y1)], radius=sc(r), fill=self._f(cut))

    def poly(self, pts, cut=False):
        self.d.polygon([(sc(x), sc(y)) for x, y in pts], fill=self._f(cut))

    def line(self, pts, w, cut=False, round_=True):
        p = [(sc(x), sc(y)) for x, y in pts]
        self.d.line(p, fill=self._f(cut), width=int(sc(w)), joint='curve')
        if round_:
            for x, y in (p[0], p[-1]):
                r = sc(w) / 2
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=self._f(cut))

    def arc(self, cx, cy, r, a0, a1, w, cut=False):
        self.d.arc([sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)], a0, a1, fill=self._f(cut), width=int(sc(w)))
        for a in (a0, a1):     # round caps
            x = cx + (r - w / 2) * math.cos(math.radians(a))
            y = cy + (r - w / 2) * math.sin(math.radians(a))
            self.circle(x, y, w / 2, cut)

    def star(self, cx, cy, r, inner=0.45, n=5, rot=-90, cut=False):
        pts = []
        for i in range(n * 2):
            a = math.radians(rot + i * 180 / n)
            rr = r if i % 2 == 0 else r * inner
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.poly(pts, cut)


def _vgrad(top, bottom):
    g = Image.new('RGBA', (1, N))
    for y in range(N):
        t = y / (N - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g.resize((N, N))


def tile(color):
    top, bottom = TILES[color] if isinstance(color, str) else color
    out = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    m = Image.new('L', (N, N), 0)
    ImageDraw.Draw(m).rounded_rectangle([sc(3), sc(3), sc(125), sc(125)], radius=sc(22), fill=255)
    out.paste((0, 0, 0, 255), (0, 0), m)
    inner = Image.new('L', (N, N), 0)
    ImageDraw.Draw(inner).rounded_rectangle([sc(9), sc(9), sc(119), sc(119)], radius=sc(16), fill=255)
    rim = _vgrad(tuple(min(255, c + 40) for c in top), tuple(min(255, c + 25) for c in bottom))
    out.paste(rim, (0, 0), inner)
    body = Image.new('L', (N, N), 0)
    ImageDraw.Draw(body).rounded_rectangle([sc(11), sc(11), sc(117), sc(117)], radius=sc(14), fill=255)
    out.paste(_vgrad(top, bottom), (0, 0), body)
    gloss = Image.new('L', (N, N), 0)
    ImageDraw.Draw(gloss).rounded_rectangle([sc(13), sc(12), sc(115), sc(58)], radius=sc(12), fill=46)
    gloss = ImageChops.multiply(gloss, body)
    out.alpha_composite(Image.merge('RGBA', [Image.new('L', (N, N), 255)] * 3 + [gloss]))
    return out


def _dilate(m, r):
    size = int(r * 2) | 1
    return m.filter(ImageFilter.MaxFilter(size))


def glyph_image(g, outline=4.5, shadow=(0, 3)):
    union = Image.new('L', (N, N), 0)
    for m, _ in g.layers:
        union = ImageChops.lighter(union, m)
    ol = _dilate(union, sc(outline))
    out = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    sh = ol.transform(ol.size, Image.AFFINE, (1, 0, -sc(shadow[0]), 0, 1, -sc(shadow[1])))
    sh = sh.point(lambda v: v * 0.45).filter(ImageFilter.GaussianBlur(S * 1.2))
    out.paste((0, 0, 0, 255), (0, 0), sh)
    black = Image.new('RGBA', (N, N), (0, 0, 0, 255))
    out.paste(black, (0, 0), ol)
    for m, color in g.layers:
        if isinstance(color, Image.Image):
            out.paste(color, (0, 0), m)
        else:
            out.paste(color, (0, 0), m)
    return out


def render(color, draw, plain=False):
    g = G()
    draw(g)
    img = Image.new('RGBA', (N, N), (0, 0, 0, 0)) if plain else tile(color)
    img.alpha_composite(glyph_image(g))
    return img.resize((128, 128), Image.LANCZOS)


# ---------------------------------------------------------------- glyphs
def skull(g):
    g.ellipse(30, 22, 98, 84)
    g.rrect(42, 70, 86, 104, 6)
    g.circle(50, 60, 9.5, True)
    g.circle(78, 60, 9.5, True)
    g.poly([(64, 70), (58, 82), (70, 82)], True)
    for x in (55.5, 64, 72.5):
        g.rect(x - 1.6, 90, x + 1.6, 106, True)


def star(g):
    g.layers[0][1] = GOLD
    g.star(64, 67, 46, 0.46)


def heart(g):
    g.circle(46, 50, 20)
    g.circle(82, 50, 20)
    g.poly([(27.5, 57), (64, 100), (100.5, 57), (64, 44)])


def clock(g):
    g.circle(64, 64, 42)
    g.circle(64, 64, 32, True)
    g.new()
    g.line([(64, 40), (64, 64), (80, 74)], 8)


def bolt(g):
    g.poly([(72, 18), (34, 72), (60, 72), (52, 110), (94, 52), (67, 52), (80, 18)])


def eye(g):
    g.poly([(18, 64), (34, 44), (52, 36), (76, 36), (94, 44), (110, 64), (94, 84), (76, 92), (52, 92), (34, 84)])
    g.circle(64, 64, 22, True)
    g.new()
    g.circle(64, 64, 15)
    g.circle(64, 64, 6, True)


def gear(g):
    for i in range(8):
        a = math.radians(i * 45)
        ca, sa = math.cos(a), math.sin(a)
        w, r0, r1 = 9.5, 30, 46
        px, py = -sa, ca
        g.poly([(64 + ca * r0 + px * w, 64 + sa * r0 + py * w), (64 + ca * r1 + px * w * 0.8, 64 + sa * r1 + py * w * 0.8),
                (64 + ca * r1 - px * w * 0.8, 64 + sa * r1 - py * w * 0.8), (64 + ca * r0 - px * w, 64 + sa * r0 - py * w)])
    g.circle(64, 64, 36)
    g.circle(64, 64, 14, True)


def flag(g):
    g.rrect(30, 18, 39, 110, 3)
    g.poly([(39, 22), (62, 16), (80, 26), (100, 22), (100, 66), (80, 70), (62, 60), (39, 66)])


def trophy(g):
    g.layers[0][1] = GOLD
    g.poly([(34, 22), (94, 22), (90, 56), (78, 72), (50, 72), (38, 56)])
    g.arc(34, 42, 15, 90, 270, 7)
    g.arc(94, 42, 15, -90, 90, 7)
    g.rect(58, 70, 70, 88)
    g.rrect(42, 86, 86, 104, 4)


def music(g):
    g.ellipse(26, 78, 54, 102)
    g.ellipse(74, 68, 102, 92)
    g.rect(46, 30, 54, 90)
    g.rect(94, 20, 102, 80)
    g.poly([(46, 30), (102, 20), (102, 38), (46, 48)])


def shield(g):
    g.poly([(64, 16), (104, 30), (100, 70), (86, 92), (64, 110), (42, 92), (28, 70), (24, 30)])
    g.poly([(64, 30), (90, 40), (87, 68), (64, 96)], True)


def fire(g):
    g.poly([(64, 112), (40, 104), (28, 84), (30, 62), (42, 44), (46, 60), (54, 30), (68, 14), (70, 40), (84, 34),
            (96, 54), (100, 80), (90, 102)])
    g.new((255, 170, 40, 255))
    g.poly([(64, 106), (50, 98), (46, 84), (54, 70), (58, 80), (64, 60), (76, 76), (80, 90), (74, 102)])


def crown(g):
    g.layers[0][1] = GOLD
    g.poly([(22, 44), (42, 70), (64, 30), (86, 70), (106, 44), (98, 96), (30, 96)])
    g.circle(22, 40, 8)
    g.circle(64, 26, 8)
    g.circle(106, 40, 8)
    g.new((255, 80, 80, 255))
    g.circle(64, 80, 7)


def target(g):
    g.circle(64, 64, 44)
    g.new((255, 80, 80, 255))
    g.circle(64, 64, 33)
    g.new()
    g.circle(64, 64, 22)
    g.new((255, 80, 80, 255))
    g.circle(64, 64, 11)


def play(g):
    g.poly([(40, 24), (100, 64), (40, 104)])


def ghost(g):
    g.ellipse(32, 18, 96, 80)
    g.rect(32, 50, 96, 96)
    for i, x in enumerate((32, 53.3, 74.6)):
        g.poly([(x, 96), (x + 10.7, 110), (x + 21.3, 96)])
    g.ellipse(48, 46, 60, 62, True)
    g.ellipse(70, 46, 82, 62, True)


def mouse(g):
    g.rrect(36, 14, 92, 114, 28)
    g.rect(62.5, 10, 65.5, 54, True)      # narrow cuts become black lines
    g.rect(30, 52.5, 98, 55.5, True)
    g.new()
    g.rrect(60, 26, 68, 42, 4)


def palette(g):
    g.ellipse(18, 22, 110, 106)
    g.circle(78, 82, 12, True)
    for c, (x, y) in zip([(255, 80, 80, 255), (255, 210, 60, 255), (80, 210, 90, 255), (70, 150, 255, 255)],
                         [(42, 52), (60, 38), (82, 42), (94, 62)]):
        g.new(c)
        g.circle(x, y, 8)


def chart(g):
    g.rrect(22, 72, 40, 106, 3)
    g.rrect(46, 52, 64, 106, 3)
    g.rrect(70, 34, 88, 106, 3)
    g.rrect(94, 18, 108, 106, 3)


def wrench(g):
    g.line([(40, 92), (80, 52)], 16)
    g.circle(86, 44, 22)
    g.poly([(86, 44), (96, 20), (112, 34)], True)
    g.circle(40, 92, 12)
    g.circle(40, 92, 4.5, True)


def door(g):
    g.rrect(26, 16, 74, 112, 4)
    g.rect(34, 24, 66, 112, True)
    g.new()
    g.poly([(34, 26), (60, 34), (60, 112), (34, 112)])
    g.circle(52, 72, 4, True)
    g.new()
    g.line([(72, 64), (102, 64)], 12)
    g.poly([(92, 46), (112, 64), (92, 82)])


def chat(g):
    g.rrect(16, 22, 112, 88, 30)
    g.poly([(36, 78), (30, 108), (62, 84)])
    for x in (44, 64, 84):
        g.circle(x, 55, 7.5, True)


def unlock(g):
    g.rrect(28, 58, 100, 112, 10)
    g.arc(64, 44, 28, 180, 340, 11)
    g.rect(36, 44, 47, 62)
    g.circle(64, 80, 8, True)
    g.rect(61, 82, 67, 98, True)


def rainbow(g):
    cols = [(255, 70, 70), (255, 160, 40), (255, 230, 60), (90, 220, 90), (60, 160, 255), (150, 90, 240)]
    g.layers = []
    w = 7
    for i, c in enumerate(cols):
        g.new(c + (255,))
        r = 50 - i * w
        g.d.pieslice([sc(64 - r), sc(84 - r), sc(64 + r), sc(84 + r)], 180, 360, fill=255)
        g.new(c + (255,))
    g.layers = g.layers[::2]
    for i in range(len(cols)):          # cut the next ring out of every ring
        r = 50 - (i + 1) * w
        if i + 1 < len(cols):
            ImageDraw.Draw(g.layers[i][0]).pieslice([sc(64 - r), sc(84 - r), sc(64 + r), sc(84 + r)], 180, 360, fill=0)
    m = g.layers[-1][0]
    r = 50 - len(cols) * w
    ImageDraw.Draw(m).pieslice([sc(64 - r), sc(84 - r), sc(64 + r), sc(84 + r)], 180, 360, fill=0)
    for lm, _ in g.layers:
        ImageDraw.Draw(lm).rectangle([0, sc(84), N, N], fill=0)
    g.new()
    g.ellipse(12, 78, 40, 98)
    g.ellipse(24, 70, 46, 92)
    g.ellipse(88, 78, 116, 98)
    g.ellipse(82, 70, 104, 92)


def speed(g):
    g.rrect(66, 34, 108, 76, 5)
    g.rect(76, 44, 98, 66, True)
    g.new()
    g.circle(87, 55, 5)
    g.new()
    for y, x0 in ((40, 22), (55, 14), (70, 26)):
        g.line([(x0, y), (54, y)], 7)
    g.line([(22, 94), (108, 94)], 7)


def puzzle(g):
    g.rect(30, 46, 84, 100)
    g.circle(57, 40, 12)
    g.circle(90, 73, 12)
    g.circle(57, 100, 10, True)
    g.circle(26, 73, 10, True)


def keyboard(g):
    g.rrect(14, 36, 114, 94, 10)
    for row, (y, n) in enumerate(((46, 7), (60, 7))):
        for i in range(n):
            x = 22 + i * 12.6
            g.rrect(x, y, x + 9, y + 9, 2, True)
    g.rrect(36, 74, 92, 84, 2, True)


def bug(g):
    g.ellipse(40, 40, 88, 106)
    g.ellipse(48, 22, 80, 50)
    g.rect(63, 54, 65, 104, True)
    for y in (58, 74, 90):
        g.line([(42, y), (22, y - 6)], 6)
        g.line([(86, y), (106, y - 6)], 6)
    g.line([(56, 26), (46, 12)], 5)
    g.line([(72, 26), (82, 12)], 5)


def rocket(g):
    g.poly([(64, 12), (82, 34), (84, 84), (44, 84), (46, 34)])
    g.circle(64, 50, 9, True)
    g.poly([(44, 60), (26, 86), (28, 100), (44, 86)])
    g.poly([(84, 60), (102, 86), (100, 100), (84, 86)])
    g.new((255, 170, 40, 255))
    g.poly([(50, 88), (78, 88), (64, 116)])


# name -> (tile, glyph)
BUILTIN = {
    'skull': ('red', skull), 'star': ('navy', star), 'heart': ('pink', heart), 'clock': ('teal', clock),
    'bolt': ('orange', bolt), 'eye': ('purple', eye), 'gear': ('grey', gear), 'flag': ('green', flag),
    'trophy': ('blue', trophy), 'music': ('magenta', music), 'shield': ('blue', shield), 'fire': ('red', fire),
    'crown': ('purple', crown), 'target': ('grey', target), 'play': ('green', play), 'ghost': ('purple', ghost),
    'mouse': ('orange', mouse), 'palette': ('sky', palette), 'chart': ('lime', chart), 'wrench': ('brown', wrench),
    'door': ('yellow', door), 'chat': ('blue', chat), 'unlock': ('pink', unlock), 'rainbow': ('sky', rainbow),
    'speed': ('cyan', speed), 'puzzle': ('grey', puzzle), 'keyboard': ('dark', keyboard), 'bug': ('lime', bug),
    'rocket': ('navy', rocket),
}

MOD_ICONS = {     # file -> builtin name
    'mods/confirm_exit.png': 'door', 'mods/cps.png': 'mouse', 'mods/death_counter.png': 'skull',
    'mods/hello.png': 'chat', 'mods/icon_unlock.png': 'unlock', 'mods/noclip.png': 'ghost',
    'mods/rainbow.png': 'rainbow', 'mods/slowmo.png': 'clock', 'mods/trail.png': 'speed',
    'mods/sprite_demo/icon.png': 'star', 'res/mod_icon.png': 'puzzle',
}


def macro_icon():
    def draw(g):
        play(g)
        g.new((255, 60, 60, 255))
        g.circle(98, 100, 11)
    return render('green', draw)


def main():
    out_dir = os.path.join(ROOT, 'res', 'icons')
    os.makedirs(out_dir, exist_ok=True)
    imgs = {}
    for name, (color, draw) in BUILTIN.items():
        im = render(color, draw)
        im.save(os.path.join(out_dir, name + '.png'))
        imgs[name] = im
    for rel, name in MOD_ICONS.items():
        imgs[name].save(os.path.join(ROOT, rel))
    macro_icon().save(os.path.join(ROOT, 'mods', 'macro_bot.png'))
    # preview: a grid with captions
    from PIL import ImageFont
    cols = 6
    names = list(BUILTIN)
    rows = (len(names) + cols - 1) // cols
    cw, ch = 150, 170
    prev = Image.new('RGBA', (cols * cw + 20, rows * ch + 20), (34, 52, 110, 255))
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
    except OSError:
        try:
            font = ImageFont.truetype('/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf', 20)
        except OSError:
            font = ImageFont.load_default()
    d = ImageDraw.Draw(prev)
    for i, n in enumerate(names):
        x, y = 10 + (i % cols) * cw + 11, 10 + (i // cols) * ch + 4
        prev.alpha_composite(imgs[n], (x, y))
        tw = d.textlength(n, font=font)
        d.text((x + 64 - tw / 2, y + 134), n, fill=(255, 255, 255), font=font)
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview.png')
    prev.save(path)
    print('icons:', len(names), '->', out_dir, 'preview:', path)


if __name__ == '__main__':
    main()
