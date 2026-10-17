#!/usr/bin/env python3
"""Draws all the pixel art for the game into ../art.

Run again after changing anything here:   python3 tools/make_art.py
Pass a file name to also get one overview sheet of everything:
                                          python3 tools/make_art.py sheet.png
The PNGs are plain pixel art at their real size, so they can also be opened
and edited by hand in any pixel editor.
"""
import math, os, random, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'art')


def col(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


CLEAR = (0, 0, 0, 0)
# one shared palette; the letters are what the sprite grids below are written in
P = {k: col(v) for k, v in {
    'k': '#2a1a2e', 'D': '#1a1420', 'd': '#3b2a2a',
    'w': '#f7f1e1', 'W': '#d6cdb8', 'g': '#b3aea4', 'G': '#6e6a68',
    'r': '#c9362c', 'R': '#8c1f24', 'o': '#ef8a2b', 'O': '#c55f1a', 'y': '#f6cf4f', 'Y': '#fff0a6',
    'b': '#3f8fd6', 'B': '#235a9c', 'c': '#8fd3ee', 'C': '#d6f1fa',
    'n': '#8b5a33', 'N': '#5b3920', 't': '#d8a465', 'T': '#f1c79b', 's': '#cf9a6c', 'S': '#a8744c',
    'e': '#4e9c45', 'E': '#2e6934', 'l': '#93cf56', 'L': '#c8eb9c',
    'p': '#8a5ec6', 'q': '#583a8a', 'm': '#e77aae',
    'a': '#e2b23f', 'A': '#a9791f',
}.items()}

ART = {}   # name -> image


# ── drawing helpers ─────────────────────────────────────────────

def new(w, h, fill=CLEAR):
    return Image.new('RGBA', (w, h), fill)


def outline(img, c):
    """Adds a 1px outline around everything opaque (grows the image by 1px each side)."""
    w, h = img.size
    out = new(w + 2, h + 2)
    out.paste(img, (1, 1))
    src = out.copy().load()
    px = out.load()
    for y in range(h + 2):
        for x in range(w + 2):
            if src[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w + 2 and 0 <= ny < h + 2 and src[nx, ny][3]:
                        px[x, y] = c
                        break
    return out


def grid(rows, mirror=False, edge='k'):
    """Builds a sprite from rows of palette letters ('.' = transparent)."""
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, '.') for r in rows]
    if mirror:
        rows = [r + r[::-1] for r in rows]
    img = new(len(rows[0]), len(rows))
    px = img.load()
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != '.':
                px[x, y] = P[ch]
    return outline(img, P[edge]) if edge else img


def dots(img, pts, c):
    px = img.load()
    for x, y in pts:
        if 0 <= x < img.size[0] and 0 <= y < img.size[1]:
            px[x, y] = c


def disc(img, cx, cy, r, c, only=None):
    px = img.load()
    w, h = img.size
    for y in range(int(cy - r - 1), int(cy + r + 2)):
        for x in range(int(cx - r - 1), int(cx + r + 2)):
            if 0 <= x < w and 0 <= y < h and (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                if only is None or px[x, y] == only:
                    px[x, y] = c


def shade_under(img, base, dark, n=2):
    """Darkens the bottom n pixels of every vertical run of `base`."""
    px = img.load()
    w, h = img.size
    for x in range(w):
        for y in range(h):
            if px[x, y] == base and (y + 1 == h or px[x, y + 1] != base):
                for k in range(n):
                    if y - k >= 0 and px[x, y - k] == base:
                        px[x, y - k] = dark


def recolor(img, mapping):
    out = img.copy()
    px = out.load()
    for y in range(out.size[1]):
        for x in range(out.size[0]):
            if px[x, y] in mapping:
                px[x, y] = mapping[px[x, y]]
    return out


def flip(img):
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def put(dst, src, x, y):
    dst.alpha_composite(src, (x, y)) if x >= 0 and y >= 0 else dst.alpha_composite(
        src.crop((max(0, -x), max(0, -y), src.size[0], src.size[1])), (max(0, x), max(0, y)))


BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def vgrad(img, y0, y1, cols, x0=0, x1=None):
    """Vertical gradient through `cols`, with ordered dithering between the bands."""
    px = img.load()
    x1 = img.size[0] if x1 is None else x1
    n = len(cols) - 1
    for y in range(y0, y1):
        f = (y - y0) / max(1, y1 - y0 - 1) * n
        i = min(int(f), n - 1)
        frac = f - i
        for x in range(x0, x1):
            px[x, y] = cols[i + 1] if frac > (BAYER[y % 4][x % 4] + .5) / 16 else cols[i]


def ridge(img, y_base, amp, c, seed, top=None, bottom=None):
    """A rolling silhouette (hills, dunes, mountains) filled down to `bottom`."""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in range(4)]
    fr = [rnd.uniform(.02, .05), rnd.uniform(.06, .11), rnd.uniform(.15, .25), rnd.uniform(.3, .5)]
    am = [1, .5, .22, .1]
    px = img.load()
    w, h = img.size
    tops = []
    for x in range(w):
        y = int(round(y_base - amp * sum(a * math.sin(f * x + p) for a, f, p in zip(am, fr, ph)) / 1.4))
        tops.append(y)
        for yy in range(max(0, y), bottom or h):
            px[x, yy] = c
        if top and 0 <= y < h:
            px[x, y] = top
    return tops


def blob(img, cx, cy, rx, ry, c, seed, rough=.18, only=None):
    """A lumpy ellipse: islands, continents, patches."""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    px = img.load()
    w, h = img.size
    for y in range(int(cy - ry * 1.4), int(cy + ry * 1.4) + 1):
        for x in range(int(cx - rx * 1.4), int(cx + rx * 1.4) + 1):
            if 0 <= x < w and 0 <= y < h:
                dx, dy = (x - cx) / rx, (y - cy) / ry
                a = math.atan2(dy, dx)
                r = 1 + rough * (math.sin(3 * a + ph[0]) * .5 + math.sin(5 * a + ph[1]) * .3 + math.sin(9 * a + ph[2]) * .2)
                if dx * dx + dy * dy <= r * r and (only is None or px[x, y] == only):
                    px[x, y] = c


def spline(pts, n=24):
    out = []
    q = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(q) - 2):
        p0, p1, p2, p3 = q[i - 1], q[i], q[i + 1], q[i + 2]
        for j in range(n):
            t = j / n
            out.append(tuple(.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t
                                   + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t ** 3) for k in (0, 1)))
    out.append(pts[-1])
    return out


# ── small sprites, written as letter grids ──────────────────────

ART['fireball'] = grid([
    '....ooo.............',
    '..oooyyoo..oo.......',
    '.ooyyYYyyoooo..o....',
    'ooyyYYYYyyyoooo.....',
    'oyyYYwwYYyyyoooo.oo.',
    'oyyYwwwwYYyyyyooooo.',
    'oyyYYwwYYyyyoooo....',
    'ooyyYYYYyyyooo..o...',
    '.ooyyYYyyoooo.......',
    '..oooyyoo..oo.......',
    '....ooo.............',
], edge='R')

ART['card'] = grid([
    '.aaaaaa',
    'aaRRRRR',
    'aRRrrrr',
    'aRrrrrr',
    'aRrrrra',
    'aRrrraa',
    'aRrraay',
    'aRraayy',
    'aRraayY',
    'aRraayY',
    'aRraayY',
    'aRraayy',
    'aRrraay',
    'aRrrraa',
    'aRrrrra',
    'aRrrrrr',
    'aRRrrrr',
    'aaRRRRR',
    '.aaaaaa',
], mirror=True, edge='A')

ART['cabbage'] = grid([
    '....eeeeee....',
    '..eelllllle...',
    '.elLLlllellle.',
    '.elLllleellle.',
    'elLllleelllele',
    'elllleelllelle',
    'ellleellleelle',
    'elleelllellele',
    'elleellellleEe',
    '.eleelllllEEe.',
    '.eelellllEEe..',
    '..eeelllEee...',
    '....eeeeee....',
], edge='E')

ART['cactus'] = grid([
    '..........mm..........',
    '.........mYYm.........',
    '........eemmee........',
    '........elLeeE........',
    '........elleeE........',
    '........elleeE...ee...',
    '........elLeeE..elEE..',
    '........elleeE..eLEE..',
    '........elleeE..elEE..',
    '..ee....elLeeE..elEE..',
    '.elEE...elleeE..eLEE..',
    '.eLEE...elleeEeeelEE..',
    '.elEE...elLeeeeeeeEE..',
    '.elEE...elleeEEEEEE...',
    '.eLEE...elleeE........',
    '.elEEeeeelLeeE........',
    '.eleeeeeelleeE........',
    '..EEEEEEelleeE........',
    '........elLeeE........',
    '........elleeE........',
    '........elleeE........',
    '........elLeeE........',
    '........elleeE........',
    '........elleeE........',
    '........elLeeE........',
    '........elleeE........',
], edge='k')

MUSHROOM = [
    '..........rrrr',
    '.......rrrrrrr',
    '.....rrrrrwwrr',
    '....rrrrrwwwwr',
    '...rrwwrrrwwrr',
    '..rrwwwwrrrrrr',
    '.rrrwwwwrrrrrw',
    '.rrrrwwrrrrrww',
    'rrrrrrrrrrrrrw',
    'rrrrrrrwwrrrrr',
    'rrwwrrwwwwrrrr',
    'rrwwrrrwwrrrrr',
    'RrrrrrrrrrrrrR',
    '.RRRRRRRRRRRRR',
    '......WWwwwwww',
    '.......Wwwwwww',
    '.......WwwDDww',
    '.......WwwDDww',
    '.......Wwwwwww',
    '.......WwmDwww',
    '.......WwwwDDD',
    '.......Wwwwwww',
    '......WWwwwwww',
    '.....WWWwwwwww',
]
ART['mushroom'] = grid(MUSHROOM, mirror=True)

# the decoys: same mushroom, wrong colour, bad attitude
grumpy = MUSHROOM[:]
grumpy[15], grumpy[19], grumpy[20] = '.......WwDDwww', '.......WwwwDDD', '.......WwwDwww'
ART['shroom-bad'] = grid([r.replace('r', 'p').replace('R', 'q') for r in grumpy], mirror=True)
ART['shroom-bad2'] = grid([r.replace('r', 'b').replace('R', 'B') for r in grumpy], mirror=True)

ART['torch'] = grid([
    '....y',
    '...yy',
    '...yY',
    '..oyY',
    '..oyY',
    '.ooyY',
    '.oyyY',
    'ooyYY',
    'ooyYw',
    'ooyYw',
    '.ooyY',
    '.rooy',
    '..rro',
    '.NNNN',
    '.Nttt',
    '.NNNN',
    '..nnn',
    '..nnn',
    '..nnn',
    '..nnn',
    '..nnn',
    '..nnn',
    '..nnn',
    '...nn',
], mirror=True, edge='D')

ART['crystal'] = grid([
    '......L',
    '.....Ll',
    '.....Ll',
    '....LLl',
    '....Lll',
    '.L..Lll',
    '.Ll.Lll',
    'LLl.Lle',
    'Lll.Lle',
    'Lle.Lle',
    'Lle.Lle',
    'LleLlle',
    'LleLlee',
    '.eeLlee',
    '.EeelEe',
    '..EEEEE',
], mirror=True, edge='E')

ART['cake'] = grid([
    '.....y.....y',
    '.....o.....o',
    '.....b.....m',
    '.....b.....m',
    '...wwwwwwwww',
    '..wwwwwwwwww',
    '.wwwwwwwwwww',
    '.wWwwwWwwwWw',
    '.mWmmmWmmmWm',
    '.mmmmmmmmmmm',
    '.mmmmmmmmmmm',
    '.nnnnnnnnnnn',
    '.ttttttttttt',
    '.ttttttttttt',
    '.ttttttttttt',
    'gggggggggggg',
], mirror=True)

ART['island'] = grid([
    '..............e...............',
    '.............eee......e.......',
    '............eeeee....eee......',
    '.............n.e....eeeee.....',
    '.............n........n.......',
    '.........eeeenleee....n.......',
    '......eelllllllllleeeenee.....',
    '....eellllllllllllllllllee....',
    '..ttlllllllllllllllllllllltt..',
    '.tttttttttttttttttttttttttttt.',
    'bbccbbbbccbbbbbbccbbbbccbbbbcc',
])

ART['cloud'] = grid([
    '.........wwwwww',
    '.......wwwwwwww',
    '....wwwwwwwwwww',
    '...wwwwwwwwwwww',
    '.wwwwwwwwwwwwww',
    'wwwwwwwwwwwwwww',
    'wwwwwwwwwwwwwww',
    '.CCCwwwwwwwwwww',
    '...CCCCCCCCCCCC',
], mirror=True, edge=None)

ART['world'] = grid([
    '.nttttttttttttttttttttn.',
    'nnTTTTTTTTTTTTTTTTTTTTnn',
    'nnTTTTTwwwwwTTTTTTTTTTnn',
    'nnTTTTTTTTTTTTTeeeTTTTnn',
    'nnTTrTTTTTTTeeeeeeeeTTnn',
    'nnTrrrTTTTTeeeeeeeeeeTnn',
    'nnTrrTTTTTeeeeeyyeeeeTnn',
    'nnTTrrTTTTTeeeyyyyeeTTnn',
    'nnTTTTTTTTTTeeeyyeeeTTnn',
    'nnTTTTTTTTTTTeeeeeTTTTnn',
    'nnTTTTTTTwwwwTTTTTTTTTnn',
    'nnTTTTTTTTTTTTTTTTTTTTnn',
    '.nttttttttttttttttttttn.',
], edge='N')

ART['logo'] = grid([
    '......BBBB',
    '....BBBBBB',
    '...BBBBBcc',
    '..BBBBBBcc',
    '.BBBBBBBcc',
    '.BBBBBBBcc',
    'BBBBBBBBcc',
    'BBBBBBBBcc',
    'BBBBBBBBcc',
    'BBBBBccccc',
    'BBBBBBcccc',
    '.BBBBBBccc',
    '.BBBBBBBcc',
    '..BBBBBBBc',
    '...BBBBBBB',
    '....BBBBBB',
    '......BBBB',
], mirror=True, edge='D')

ART['heart'] = grid([
    '.rr...rr.',
    'rmrr.rrrr',
    'rmrrrrrrr',
    'rrrrrrrrr',
    '.rrrrrrr.',
    '..rrrrr..',
    '...rrr...',
    '....r....',
], edge='R')

ART['check'] = grid([
    '......l',
    '.....ll',
    'l...ll.',
    'll.ll..',
    '.lll...',
    '..l....',
], edge='E')

ART['eye'] = grid([
    '...wwww',
    '.wwwwbb',
    'wwwwbbD',
    'wwwwbbD',
    '.wwwwbb',
    '...wwww',
], mirror=True)

ART['lizard'] = grid([
    '..............ll..',
    '.l..........lllll.',
    '.ll..llllllllllDl.',
    '..lllllllllllllll.',
    '...lllleelllell...',
    '...l.l.....l.l....',
    '..ll.ll...ll.ll...',
], edge='E')

MINI_APPA = [                                               # a sky bison seen from far away
    '..........tt....',
    '....wwwwwwwwww..',
    'nnwwnnnnnnnnnwww',
    'wwwwwwwwwwwwwwwD',
    '.WWWWWWWWWWWWWW.',
    '..WW.WW..WW.....',
]

# the four element stones
ART['el-water'] = grid([
    '......b',
    '.....bc',
    '.....bc',
    '....bcc',
    '...bccc',
    '..bcccC',
    '.bccccC',
    '.bcccCC',
    'bccccCC',
    'bccccCC',
    'bcccccc',
    '.bccccc',
    '..bbccc',
    '....bbb',
], mirror=True, edge='B')

ART['el-fire'] = grid([
    '......r',
    '.....rr',
    '.....ro',
    '..r.rro',
    '..rrroo',
    '.rrrooy',
    '.rrooyy',
    'rrrooyy',
    'rrooyyY',
    'rrooyYY',
    'rrooyYY',
    '.rrooyY',
    '..rrooy',
    '....rrr',
], mirror=True, edge='R')

ART['el-earth'] = grid([
    '....eee',
    '..eeeee',
    '.eeeeee',
    '.eeEEEE',
    'eeeElll',
    'eeeElll',
    'eeeEllE',
    'eeeEllE',
    'eeeElll',
    'eeeElll',
    '.eeEEEE',
    '.eeeeee',
    '..eeeee',
    '....eee',
], mirror=True, edge='E')

ART['el-air'] = grid([
    '.....yyyy.....',
    '...yyYYYYyy...',
    '..yYYyyyyYYy..',
    '.yYyy....yYYy.',
    '.yYy..yy..yYy.',
    'yYy..yYYy..yYy',
    'yYy.yYyyYy.yYy',
    'yYy.yYy.yy.yYy',
    'yYy..yYy...yYy',
    '.yYy..yYyyyYy.',
    '.yYYy..yYYYy..',
    '..yYYy..yyy...',
    '...yyYy.......',
    '.....yy.......',
], edge='A')

# map pins
ART['pin-water'] = grid([
    '........c',
    '.......cC',
    '.......cC',
    '......cCC',
    '....c.cCC',
    '...cC.cCw',
    '...cCccCw',
    '..cCCcCww',
    '..cCCcCww',
    '.cCCwcCwB',
    '.cCwwcCwB',
    'cCCwwcwwB',
    'cCwwwwwwB',
], mirror=True, edge='B')

ART['pin-university'] = grid([
    '........a',
    '.......ee',
    '.....eeee',
    '...eeeeee',
    '....tttTT',
    '....tttTT',
    '..eeeeeee',
    'eeeeeeeee',
    '..ttttTTT',
    '..ttttTnn',
    '..ttttTnn',
    '.gggggggg',
], mirror=True)

ART['pin-tea'] = grid([
    '....w...w',
    '...w...w.',
    '....w...w',
    '.........',
    'wwwwwwwww',
    'weeeeeeee',
    'wwwwwwwww',
    '.wwwwwwww',
    '.wwlllwww',
    '..wwwwwww',
    '...wwwwww',
    '....WWWWW',
], mirror=True)

ART['pin-desert'] = grid([
    '.............yy...',
    '............yyyy..',
    '....e.......yyyy..',
    '....e.e......yy...',
    '..e.e.e...........',
    '..e.eee...........',
    '..eee.....tttt....',
    '....e...tttTTTtt..',
    '....e.tttTTTTTTTtt',
    '..ttttTTTTTTTTTTTt',
    'ttTTTTTTTTTTTTTTTT',
], edge='N')

ART['pin-swamp'] = grid([                                  # the banyan-grove tree, roots hanging into the water
    '....lllll',
    '..llleeee',
    '.lleeeeee',
    'leeeeeEee',
    'EEeEEEEEE',
    '.N..N..nn',
    '.N..N..nn',
    '....N..nn',
    '......nNN',
    'EEEEEnNNN',
], mirror=True)

ART['pin-cave'] = grid([
    '........w',
    '.......ww',
    '......wSS',
    '.....SSSS',
    '....SSSSS',
    '...SSSSSN',
    '..SSSSSDD',
    '.SSSSNDDD',
    '.SSSSDDDD',
    'SSSSNDDDD',
    'SSSSNDDDD',
], mirror=True)


# arrow for buttons (points up; the game rotates it)
ART['arrow'] = grid([
    '....w',
    '...ww',
    '..www',
    '.wwww',
    'wwwww',
    '...ww',
    '...ww',
    '...ww',
    '...ww',
], mirror=True)


def pin_sun():
    im = new(19, 19)
    for i in range(8):
        a = i * math.pi / 4
        for r in (6, 7, 8, 9):
            dots(im, [(round(9 + r * math.cos(a)), round(9 + r * math.sin(a)))], P['y'])
    disc(im, 9, 9, 5.2, P['a'])
    disc(im, 9, 9, 4.2, P['y'])
    disc(im, 8, 8, 2, P['Y'])
    return outline(im, P['A'])


ART['pin-sun'] = pin_sun()


# ── bigger sprites, drawn from shapes ───────────────────────────

def appa():
    im = new(66, 40)
    d = ImageDraw.Draw(im)
    w, W, n, t, D = (P[c] for c in 'wWntD')
    d.ellipse((0, 11, 18, 20), fill=w)                     # flat beaver tail
    for x in (22, 34):                                     # far legs
        d.rectangle((x, 27, x + 3, 35), fill=W)
    d.ellipse((11, 6, 50, 31), fill=w)                     # body
    d.ellipse((41, 7, 63, 32), fill=w)                     # head
    px = im.load()
    for x in range(2, 53):                                 # brown stripe: tail, spine, top of the head
        y = next(y for y in range(40) if px[x, y][3])
        for yy in range(y + 1, y + (3 if x < 12 else 4)):
            px[x, yy] = n
    d.polygon([(51, 8), (61, 14), (58, 19), (52, 16)], fill=n)   # ...ending in the arrow on his forehead
    for x in (15, 27, 39):                                 # near legs with toes
        d.rectangle((x, 26, x + 6, 37), fill=w)
        d.rectangle((x, 36, x + 6, 37), fill=t)
        dots(im, [(x + 2, 37), (x + 4, 37)], P['N'])
    d.polygon([(45, 9), (43, 3), (44, 1), (46, 1), (49, 9)], fill=t)   # horn
    dots(im, [(44, 3), (45, 5), (46, 7)], P['S'])
    d.rectangle((52, 21, 53, 23), fill=D)                  # eye
    dots(im, [(52, 21)], w)
    d.rectangle((59, 21, 63, 25), fill=D)                  # big flat nose
    d.line((50, 28, 61, 28), fill=P['G'])                  # mouth
    dots(im, [(49, 27)], P['G'])
    for x, y in ((18, 14), (24, 20), (31, 13), (36, 22), (20, 24)):   # fluff
        dots(im, [(x, y), (x + 1, y + 1), (x + 2, y)], W)
    shade_under(im, w, W, 2)
    return outline(im, P['k'])


ART['appa'] = appa()


def cart():
    im = new(38, 30)
    d = ImageDraw.Draw(im)
    n, N, t = P['n'], P['N'], P['t']
    cab = ART['cabbage']
    for x, y in ((1, 2), (11, 0), (21, 2)):                # the precious cargo
        put(im, cab, x, y)
    d.rectangle((3, 13, 32, 22), fill=n)                   # cart box
    for x in range(8, 32, 6):
        d.line((x, 14, x, 22), fill=N)
    d.rectangle((2, 12, 33, 13), fill=t)
    d.line((33, 16, 37, 13), fill=N)                       # handle
    for cx in (10, 26):                                    # wheels
        d.ellipse((cx - 6, 18, cx + 6, 29), fill=N)
        d.ellipse((cx - 4, 20, cx + 4, 27), fill=t)
        d.line((cx - 4, 23, cx + 4, 24), fill=N)
        d.line((cx, 20, cx, 27), fill=N)
        d.rectangle((cx - 1, 23, cx + 1, 24), fill=N)
    return outline(im, P['k'])


ART['cart'] = cart()


def teapot():
    im = new(31, 24)
    d = ImageDraw.Draw(im)
    e, E, l, L, a = (P[c] for c in 'eElLa')
    d.arc((1, 9, 12, 20), 80, 280, fill=E, width=2)        # handle
    d.polygon([(22, 14), (28, 7), (30, 8), (30, 10), (25, 18)], fill=e)   # spout
    d.ellipse((7, 7, 24, 23), fill=e)                      # body
    d.ellipse((10, 4, 21, 10), fill=E)                     # lid
    d.rectangle((14, 2, 17, 4), fill=a)
    px = im.load()
    for x in range(7, 25):                                 # gold band
        if px[x, 15] == e:
            px[x, 15] = a
    dots(im, [(10, 11), (11, 10), (12, 9), (10, 12), (11, 11)], L)
    d.rectangle((11, 22, 20, 23), fill=E)
    shade_under(im, e, E, 2)
    return outline(im, P['k'])


ART['teapot'] = teapot()


def koi_fish(im, a0, body, spot):
    """One koi, curled along a circle in a 28 x 28 box, its head at angle a0."""
    pts = []
    for i in range(60):
        t = i / 59
        a = a0 - t * math.pi * .92
        pts.append((14 + 8 * math.cos(a), 14 + 8 * math.sin(a), 3.4 * (1 - t) ** .7 + .7))
    for x, y, r in reversed(pts):
        disc(im, x, y, r, body)
    tx, ty, _ = pts[-1]                                     # tail fin
    disc(im, tx + (tx - 14) * .25, ty + (ty - 14) * .25, 1.6, body)
    hx, hy, _ = pts[4]
    disc(im, hx, hy, 1.3, spot)


def koi():
    """Tui and La: a white and a black koi circling each other."""
    im = new(28, 28)
    koi_fish(im, 0, P['w'], P['D'])
    koi_fish(im, math.pi, P['D'], P['w'])
    return outline(im, P['B'])


ART['koi'] = koi()


def moon():
    im = new(24, 24)
    d = ImageDraw.Draw(im)
    w, W, g = P['w'], P['W'], P['g']
    d.ellipse((0, 0, 23, 23), fill=w)
    px = im.load()
    for y in range(24):
        for x in range(24):
            if px[x, y][3] and (x - 8) ** 2 + (y - 8) ** 2 > 13.5 ** 2:
                px[x, y] = W
    for box in ((5, 5, 9, 9), (13, 11, 18, 16), (7, 15, 10, 18), (15, 4, 17, 6)):
        d.ellipse(box, fill=W)
        dots(im, [(box[0] + 1, box[3])], g)
    return outline(im, col('#9fb4d8'))


ART['moon'] = moon()


def comet():
    im = new(44, 26)
    hx, hy, tx, ty = 36, 19, 2, 3
    for i in range(200, -1, -1):
        t = i / 200
        c = P['Y'] if t < .12 else P['y'] if t < .32 else P['o'] if t < .62 else P['r']
        disc(im, hx + (tx - hx) * t, hy + (ty - hy) * t, 5.2 * (1 - t) + .5, c)
    disc(im, hx, hy, 3.6, P['w'])
    return outline(im, P['R'])


ART['comet'] = comet()


def dragon(main, dark, belly):
    im = new(52, 46)
    d = ImageDraw.Draw(im)
    path = spline([(37, 13), (27, 11), (17, 17), (21, 27), (32, 30), (31, 38), (19, 41), (7, 37)], 26)
    n = len(path)
    for i in range(n - 1, -1, -1):                         # tail first, so the neck ends up on top
        x, y = path[i]
        t = i / (n - 1)
        r = 4.3 * (1 - t * .78)
        if i % 9 == 4 and 0 < i < n - 1:                   # back fins
            (x0, y0), (x1, y1) = path[i - 1], path[i + 1]
            nx, ny = -(y1 - y0), (x1 - x0)
            ln = math.hypot(nx, ny) or 1
            nx, ny = nx / ln, ny / ln
            if ny > 0:
                nx, ny = -nx, -ny
            disc(im, x + nx * (r + .8), y + ny * (r + .8), 1.3, P['y'])
        disc(im, x, y, r, main)
        disc(im, x, y + r * .55, r * .42, belly)
    d.line((36, 8, 32, 3), fill=P['a'])                    # horns
    d.line((39, 7, 37, 1), fill=P['a'])
    d.ellipse((33, 7, 45, 18), fill=main)                  # head
    d.rectangle((43, 10, 49, 16), fill=main)               # snout
    d.line((41, 16, 49, 16), fill=dark)
    dots(im, [(48, 11)], P['D'])
    d.rectangle((40, 10, 42, 11), fill=P['Y'])             # eye
    dots(im, [(42, 11), (42, 10)], P['D'])
    dots(im, [(50, 14), (51, 16), (51, 18), (50, 20)], P['a'])   # whisker
    dots(im, [(33, 9), (32, 11), (33, 13), (32, 15)], P['y'])    # mane
    return outline(im, P['k'])


ART['ran'] = dragon(P['r'], P['R'], P['y'])
ART['shaw'] = flip(dragon(P['b'], P['B'], P['c']))


# ── portraits ───────────────────────────────────────────────────

def bust(skin, robe, trim, hair=None, hair_box=None, face_box=(9, 7, 22, 24)):
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    d.ellipse((1, 24, 30, 44), fill=robe)                  # shoulders
    d.polygon([(10, 24), (21, 24), (16, 31), (15, 31)], fill=trim)
    d.rectangle((13, 21, 18, 25), fill=P['s'] if skin == P['T'] else P['N'])
    if hair:
        d.ellipse(hair_box or (7, 3, 24, 20), fill=hair)
    d.ellipse(face_box, fill=skin)
    d.rectangle((8, 13, 8, 16), fill=skin)                 # ears
    d.rectangle((23, 13, 23, 16), fill=skin)
    return im, d


def iroh():
    g, G, D = P['g'], P['G'], P['D']
    im, d = bust(P['T'], P['e'], P['t'], hair=g, hair_box=(7, 4, 24, 22), face_box=(9, 6, 22, 24))
    d.rectangle((14, 1, 17, 4), fill=g)                    # topknot
    d.line((14, 4, 17, 4), fill=P['a'])
    d.polygon([(9, 16), (11, 20), (20, 20), (22, 16), (22, 23), (17, 30), (14, 30), (9, 23)], fill=g)   # beard
    dots(im, [(10, 14), (11, 13), (12, 13), (13, 14), (18, 14), (19, 13), (20, 13), (21, 14)], D)       # smiling eyes
    d.line((10, 11, 13, 11), fill=G)
    d.line((18, 11, 21, 11), fill=G)
    dots(im, [(15, 15), (16, 15), (15, 16), (16, 16)], P['s'])
    dots(im, [(13, 18), (14, 19), (15, 19), (16, 19), (17, 19), (18, 18)], D)
    dots(im, [(11, 16), (20, 16)], P['m'])
    return outline(im, P['k'])


def zuko():
    d_, D = P['d'], P['D']
    im, d = bust(P['T'], P['r'], P['a'], hair=d_, hair_box=(7, 3, 24, 17))
    for x in (9, 12, 15, 18):                              # shaggy fringe
        d.polygon([(x, 7), (x + 4, 7), (x + 2, 11)], fill=d_)
    d.ellipse((17, 10, 23, 17), fill=P['R'])               # the scar
    d.rectangle((23, 12, 23, 16), fill=P['R'])
    dots(im, [(18, 12), (19, 11), (21, 16), (22, 15)], P['r'])
    dots(im, [(19, 14), (20, 14)], D)
    dots(im, [(11, 14), (12, 14)], D)
    dots(im, [(12, 14)], P['a'])
    dots(im, [(10, 12), (11, 12), (12, 13), (13, 13)], d_)
    dots(im, [(15, 16), (16, 16)], P['s'])
    dots(im, [(14, 20), (15, 19), (16, 19), (17, 20)], D)
    return outline(im, P['k'])


def sokka():
    d_, D = P['d'], P['D']
    im, d = bust(P['S'], P['b'], P['w'], hair=P['N'], hair_box=(8, 5, 23, 18))
    d.ellipse((10, 3, 21, 10), fill=d_)                    # hair on top, shaved sides
    d.polygon([(14, 4), (15, 0), (19, 0), (20, 2), (18, 5)], fill=d_)   # wolf tail
    d.ellipse((9, 8, 22, 24), fill=P['S'])
    dots(im, [(11, 14), (20, 14)], D)
    dots(im, [(12, 14), (19, 14)], P['b'])
    dots(im, [(10, 12), (11, 11), (12, 11), (13, 11), (18, 12), (19, 12), (20, 12), (21, 12)], d_)
    dots(im, [(15, 16), (16, 16)], P['N'])
    dots(im, [(14, 20), (15, 20), (16, 20), (17, 19), (18, 19)], D)
    d.polygon([(25, 23), (29, 11), (31, 12), (28, 24)], fill=P['c'])    # boomerang over the shoulder
    d.polygon([(29, 11), (24, 6), (23, 8), (28, 13)], fill=P['c'])
    dots(im, [(13, 26), (15, 27), (16, 27), (18, 26)], P['w'])
    return outline(im, P['k'])


def daili():
    E, D = P['E'], P['D']
    im, d = bust(P['T'], E, P['e'])
    d.rectangle((9, 12, 22, 17), fill=P['s'])              # face shadowed by the hat
    dots(im, [(11, 16), (12, 16), (19, 16), (20, 16)], D)
    d.polygon([(1, 13), (15, 3), (16, 3), (30, 13), (28, 15), (3, 15)], fill=E)
    d.line((3, 14, 28, 14), fill=P['e'])
    d.rectangle((15, 7, 16, 9), fill=P['a'])
    dots(im, [(8, 16), (8, 17), (8, 18), (23, 16), (23, 17), (23, 18)], P['d'])
    dots(im, [(15, 18), (16, 18)], P['s'])
    d.line((13, 21, 18, 21), fill=D)
    return outline(im, P['k'])


def longfeng():
    D = P['D']
    im, d = bust(P['T'], P['E'], P['a'], hair=D, hair_box=(8, 3, 23, 15), face_box=(9, 6, 22, 24))
    d.rectangle((14, 1, 17, 3), fill=D)
    dots(im, [(11, 14), (12, 14), (19, 14), (20, 14)], D)
    dots(im, [(10, 11), (11, 11), (12, 12), (13, 12), (21, 11), (20, 11), (19, 12), (18, 12)], D)
    dots(im, [(15, 16), (16, 16)], P['s'])
    d.line((13, 18, 18, 18), fill=D)                       # long thin moustache
    dots(im, [(12, 19), (11, 20), (11, 21), (11, 22), (19, 19), (20, 20), (20, 21), (20, 22)], D)
    dots(im, [(15, 22), (16, 22), (15, 23), (16, 23), (15, 24), (16, 24)], D)
    dots(im, [(14, 20), (15, 20), (16, 20), (17, 20)], P['s'])
    for i, y in enumerate(range(19, 31, 2)):               # braid over the shoulder
        dots(im, [(24 + i % 2, y), (24 + i % 2, y + 1)], D)
    d.line((8, 27, 12, 31), fill=P['a'])
    d.line((23, 27, 19, 31), fill=P['a'])
    return outline(im, P['k'])


def ozai():
    D, a = P['D'], P['a']
    im, d = bust(P['T'], P['R'], a, hair=D, hair_box=(6, 3, 25, 19))
    d.rectangle((6, 11, 9, 31), fill=D)                    # long hair
    d.rectangle((22, 11, 25, 31), fill=D)
    d.ellipse((9, 7, 22, 24), fill=P['T'])
    d.polygon([(13, 5), (14, 1), (15, 3), (16, 0), (17, 3), (18, 1), (18, 5)], fill=a)   # flame crown
    d.polygon([(0, 27), (5, 21), (10, 26)], fill=P['r'])   # shoulder armour
    d.polygon([(31, 27), (26, 21), (21, 26)], fill=P['r'])
    d.line((0, 27, 5, 21), fill=a)
    d.line((31, 27, 26, 21), fill=a)
    dots(im, [(11, 14), (20, 14)], D)
    dots(im, [(12, 14), (19, 14)], a)
    dots(im, [(10, 11), (11, 11), (12, 12), (13, 13), (21, 11), (20, 11), (19, 12), (18, 13)], D)
    dots(im, [(15, 16), (16, 16)], P['s'])
    dots(im, [(13, 21), (14, 20), (15, 20), (16, 20), (17, 20), (18, 21)], D)
    d.polygon([(14, 22), (17, 22), (16, 28), (15, 28)], fill=D)   # pointed beard
    return outline(im, P['k'])


for name, fn in (('iroh', iroh), ('zuko', zuko), ('sokka', sokka), ('daili', daili), ('longfeng', longfeng), ('ozai', ozai)):
    ART[name] = fn()


# ── scene backdrops (176 x 96, shown inside the scene boxes) ────

SW, SH = 176, 96


def stage_flight():
    im = new(SW, SH)
    vgrad(im, 0, SH, [col(c) for c in ('#2f7fc9', '#4f9bdc', '#7fbfea', '#b5dff3', '#e8f1e2')])
    ridge(im, 82, 9, col('#9dbfd8'), 3, top=col('#c4dcea'))
    d = ImageDraw.Draw(im)                                  # a far-off air temple
    for x, h in ((118, 12), (122, 18), (126, 10)):
        d.rectangle((x, 70 - h, x + 1, 74), fill=col('#c4dcea'))
        dots(im, [(x, 69 - h), (x + 1, 69 - h)], col('#7fa6c4'))
    ridge(im, 91, 6, col('#7499ba'), 5, top=col('#9dbfd8'))
    return im


def stage_desert():
    im = new(SW, SH)
    vgrad(im, 0, 72, [col(c) for c in ('#f6c44e', '#f8ae42', '#f7953c', '#f17c3a')])
    disc(im, 146, 16, 12.5, col('#fbd77a'))
    disc(im, 146, 16, 10.5, col('#fff2b8'))
    d = ImageDraw.Draw(im)                                  # the buried library's spire
    hz = col('#c9743c')
    d.rectangle((40, 38, 42, 64), fill=hz)
    d.polygon([(37, 40), (41, 28), (45, 40)], fill=hz)
    d.rectangle((38, 46, 44, 47), fill=hz)
    ridge(im, 62, 5, col('#e3a654'), 11, top=col('#f4c478'))
    ridge(im, 73, 6, col('#cf8e42'), 12, top=col('#e8b060'))
    ridge(im, 86, 5, col('#b87634'), 13, top=col('#d89a4c'))
    rnd = random.Random(4)
    for _ in range(40):
        dots(im, [(rnd.randrange(SW), rnd.randrange(80, SH))], col('#a2652a'))
    return im


def stage_cave():
    im = new(SW, SH, col('#241710'))
    d = ImageDraw.Draw(im)
    rnd = random.Random(9)
    d.rectangle((0, 6, SW, 72), fill=col('#4a3222'))
    for _ in range(170):                                    # rough rock
        x, y = rnd.randrange(SW), rnd.randrange(6, 72)
        w, h = rnd.randrange(3, 9), rnd.randrange(2, 5)
        d.rectangle((x, y, x + w, y + h), fill=col(rnd.choice(('#553a28', '#3f2a1c', '#46301f'))))
    px = im.load()
    for y in range(0, 60):                                  # torchlight
        for x in range(40, 136):
            dist = math.hypot(x - 88, (y - 10) * 1.4)
            if dist < 44 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 44:
                px[x, y] = col('#7a5232') if px[x, y] != col('#3f2a1c') else col('#5c3f28')
    for cx in (30, 88, 146):                                # three tunnels
        d.ellipse((cx - 16, 26, cx + 16, 62), fill=col('#6a4a32'))
        d.rectangle((cx - 16, 44, cx + 16, 72), fill=col('#6a4a32'))
        d.ellipse((cx - 13, 29, cx + 13, 61), fill=col('#0b0705'))
        d.rectangle((cx - 13, 45, cx + 13, 72), fill=col('#0b0705'))
    for _ in range(26):                                     # stalactites
        x, h = rnd.randrange(SW), rnd.randrange(4, 15)
        d.polygon([(x - 3, 0), (x + 3, 0), (x, h)], fill=col('#1c110b'))
    d.rectangle((0, 72, SW, SH), fill=col('#5c3f2a'))
    ridge(im, 74, 2, col('#5c3f2a'), 21, top=col('#7a5638'))
    for _ in range(60):
        x, y = rnd.randrange(SW), rnd.randrange(78, SH)
        dots(im, [(x, y), (x + 1, y)], col(rnd.choice(('#46301f', '#7a5638'))))
    return im


def stage_water():
    im = new(SW, SH)
    vgrad(im, 0, 44, [col(c) for c in ('#070b24', '#0d1740', '#152a66', '#1f3f8c')])
    rnd = random.Random(5)
    for _ in range(70):
        dots(im, [(rnd.randrange(SW), rnd.randrange(0, 34))], col(rnd.choice(('#ffffff', '#9fb4d8', '#5f78b0'))))
    px = im.load()
    for x in range(SW):                                     # aurora
        y0 = 9 + 4 * math.sin(x * .05) + 2 * math.sin(x * .13)
        for k in range(7):
            y = int(y0 + k)
            if (BAYER[y % 4][x % 4] + .5) / 16 > .35 + k * .09:
                px[x, y] = col('#3fd6a0') if k < 3 else col('#2f9fb0')
    d = ImageDraw.Draw(im)
    ice, shade, deep = col('#e8f6fb'), col('#a9d2ea'), col('#6fa6cf')
    d.rectangle((0, 37, SW, 44), fill=shade)                # the great wall of ice
    d.rectangle((0, 37, SW, 38), fill=ice)
    for x in range(0, SW, 8):
        d.rectangle((x, 35, x + 3, 37), fill=ice)
    for cx, wd, h in ((88, 34, 22), (88, 22, 30), (88, 10, 37), (40, 12, 16), (136, 12, 16), (16, 8, 11), (160, 8, 11)):
        d.rectangle((cx - wd // 2, 37 - h, cx + wd // 2, 37), fill=shade)
        d.rectangle((cx - wd // 2, 37 - h, cx + wd // 2, 38 - h), fill=ice)
        d.rectangle((cx - wd // 2, 37 - h, cx - wd // 2 + 1, 37), fill=ice)
    d.ellipse((84, 20, 92, 28), fill=deep)                  # the tribe's emblem
    d.arc((85, 21, 91, 27), 200, 20, fill=ice)
    d.rectangle((85, 39, 91, 44), fill=deep)
    vgrad(im, 44, SH, [col(c) for c in ('#24486e', '#1b3657', '#142845', '#0e1c33')])
    for side in (0, 1):                                     # ice shelves down into the pond
        for i, (wd, y) in enumerate(((44, 50), (34, 60), (24, 72), (14, 84))):
            x0, x1 = (0, wd) if side == 0 else (SW - wd, SW)
            d.rectangle((x0, y, x1, SH), fill=col(('#3a6a94', '#2f5a82', '#264a6e', '#1e3c5c')[i]))
            d.line((x0, y, x1, y), fill=col('#6fa6cf'))
    return im


def stage_map():
    sea, sea2 = col('#6f95a6'), col('#86aab8')
    land_c, forest, sand = col('#c9b97e'), col('#8fa35c'), col('#e6cf8c')
    fire, ice, coast = col('#b0604a'), col('#eef6f8'), col('#5b4630')
    im = new(SW, SH, sea)
    rnd = random.Random(7)
    for _ in range(240):
        x, y = rnd.randrange(SW - 2), rnd.randrange(SH)
        dots(im, [(x, y), (x + 1, y)], sea2)
    land = new(SW, SH)
    for i, (cx, cy, rx, ry) in enumerate(((125, 48, 44, 32), (94, 54, 20, 17), (108, 74, 24, 12), (150, 22, 22, 11), (160, 72, 12, 13))):
        blob(land, cx, cy, rx, ry, land_c, i + 1)           # the Earth Kingdom
    for i in range(16):
        blob(land, rnd.randrange(100, 170), rnd.randrange(22, 86), rnd.randrange(3, 7), rnd.randrange(2, 5), forest, 30 + i, only=land_c)
    blob(land, 116, 67, 17, 9, sand, 40, only=land_c)       # Si Wong Desert
    blob(land, 116, 67, 17, 9, sand, 40, only=forest)
    blob(land, 20, 48, 13, 20, fire, 6)                     # Fire Nation crescent
    blob(land, 28, 45, 7, 10, CLEAR, 8)
    blob(land, 37, 63, 6, 5, fire, 7)
    for cx, cy in ((43, 40), (49, 47), (55, 53)):
        blob(land, cx, cy, 3, 2, fire, cx)
    blob(land, 34, 27, 3, 2, fire, 52)                      # Ember Island, in the northern outer islands
    blob(land, 56, 24, 5, 4, land_c, 50)                    # air temple islands
    blob(land, 166, 90, 5, 3, land_c, 51)
    blob(land, 88, 4, 36, 9, ice, 9)                        # the poles
    blob(land, 82, 95, 30, 7, ice, 10)
    px = land.load()                                        # coastlines
    edge = [(x, y) for y in range(SH) for x in range(SW) if px[x, y][3]
            and any(0 <= x + dx < SW and 0 <= y + dy < SH and px[x + dx, y + dy][3] == 0 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    dots(land, edge, coast)
    im.alpha_composite(land)
    d = ImageDraw.Draw(im)

    def peak(x, y, h, body, cap):
        d.polygon([(x - h, y), (x, y - h), (x + h, y)], fill=body)
        d.line((x, y - h, x + h, y), fill=coast)
        dots(im, [(x, y - h), (x - 1, y - h + 1), (x, y - h + 1)], cap)

    for x, y, h in ((86, 42, 5), (93, 39, 6), (101, 42, 5), (97, 50, 4), (89, 51, 4), (128, 58, 4), (150, 62, 5)):
        peak(x, y, h, col('#8a7355'), ice)
    peak(18, 44, 5, col('#7a3a30'), col('#f08a2c'))         # a volcano
    d.ellipse((127, 20, 151, 36), outline=coast)            # the walls of Ba Sing Se
    d.ellipse((134, 24, 144, 32), outline=coast)
    d.ellipse((146, 40, 152, 43), fill=sea)                 # Lake Laogai
    for _ in range(26):
        dots(im, [(rnd.randrange(102, 131), rnd.randrange(61, 74))], col('#c9a85c'))
    d.line((12, 78, 12, 90), fill=coast)                    # compass
    d.line((6, 84, 18, 84), fill=coast)
    d.polygon([(12, 76), (10, 80), (14, 80)], fill=col('#b0604a'))
    px = im.load()                                          # aged parchment edges
    for y in range(SH):
        for x in range(SW):
            m = min(x, y, SW - 1 - x, SH - 1 - y)
            if m < 5 and (BAYER[y % 4][x % 4] + .5) / 16 > m / 5:
                r, g, b, a = px[x, y]
                px[x, y] = (int(r * .72), int(g * .68), int(b * .6), a)
    return im


for name, fn in (('stage-flight', stage_flight), ('stage-desert', stage_desert), ('stage-cave', stage_cave),
                 ('stage-water', stage_water), ('stage-map', stage_map)):
    ART[name] = fn()


# ── full-page backdrops (192 x 108) ─────────────────────────────

BW, BH = 192, 108


def bg_tea():
    im = new(BW, BH)
    vgrad(im, 0, 84, [col(c) for c in ('#7a4326', '#6a381f', '#5a2f1a')])
    d = ImageDraw.Draw(im)
    wood, dark = col('#3f2012'), col('#2c160c')
    d.ellipse((66, 14, 126, 74), fill=wood)                 # round garden window
    d.ellipse((70, 18, 122, 70), fill=col('#bfe3c8'))
    win = new(BW, BH)
    ridge(win, 52, 6, col('#6fae5a'), 2)
    ridge(win, 60, 5, col('#3f7d3e'), 3)
    px, wp = im.load(), win.load()
    for y in range(18, 71):
        for x in range(70, 123):
            if px[x, y] == col('#bfe3c8') and wp[x, y][3]:
                px[x, y] = wp[x, y]
    d.line((96, 18, 96, 70), fill=wood)
    d.line((70, 44, 122, 44), fill=wood)
    for x in (0, 60, 130, 188):                             # pillars and beam
        d.rectangle((x, 0, x + 3, 84), fill=wood)
    d.rectangle((0, 0, BW, 3), fill=wood)
    rnd = random.Random(3)
    for x0 in (8, 138):                                     # shelves of teapots and jars
        for y in (30, 50, 70):
            d.rectangle((x0, y, x0 + 46, y + 1), fill=wood)
            for x in range(x0 + 3, x0 + 44, 8):
                c = col(rnd.choice(('#4e9c45', '#c9362c', '#e2b23f', '#8fd3ee', '#f7f1e1')))
                h = rnd.randrange(4, 8)
                d.rectangle((x, y - h, x + 4, y - 1), fill=c)
                dots(im, [(x + 1, y - h - 1), (x + 2, y - h - 1), (x + 3, y - h - 1)], dark)
    for x in (34, 157):                                     # lanterns
        d.line((x, 3, x, 9), fill=dark)
        d.ellipse((x - 5, 9, x + 5, 21), fill=col('#d2412c'))
        d.ellipse((x - 2, 11, x + 2, 19), fill=col('#f6cf4f'))
        d.rectangle((x - 3, 8, x + 3, 9), fill=col('#e2b23f'))
        d.rectangle((x - 3, 21, x + 3, 22), fill=col('#e2b23f'))
    d.rectangle((0, 84, BW, BH), fill=col('#8a5a34'))       # floorboards
    for y in range(84, BH, 6):
        d.line((0, y, BW, y), fill=col('#6b4426'))
        for x in range((y * 7) % 31, BW, 31):
            d.line((x, y, x, y + 6), fill=col('#6b4426'))
    return im


def bg_dragon():
    im = new(BW, BH)
    vgrad(im, 0, BH, [col(c) for c in ('#2a1a4a', '#6a2a5a', '#c84a3a', '#f08a2c', '#f6cf4f', '#f6cf4f')])
    disc(im, 96, 70, 24, col('#fff0a6'))
    d = ImageDraw.Draw(im)
    rock, dark, step = col('#4a2238'), col('#2c1426'), col('#6a3a4a')
    for cx in (34, 158):                                    # the two masters' mountains
        d.polygon([(cx - 26, BH), (cx - 8, 22), (cx + 8, 22), (cx + 26, BH)], fill=rock)
        d.ellipse((cx - 6, 28, cx + 6, 42), fill=dark)
        d.line((cx - 8, 22, cx - 26, BH), fill=step)
    d.line((40, 42, 82, 44), fill=rock)                     # bridges to the platform
    d.line((152, 42, 110, 44), fill=rock)
    d.polygon([(82, 44), (110, 44), (138, BH), (54, BH)], fill=step)    # the great staircase
    d.rectangle((74, 42, 118, 44), fill=rock)
    for i, y in enumerate(range(47, BH, 3)):
        half = 14 + (y - 44) * 28 / (BH - 44)
        d.line((96 - half, y, 96 + half, y), fill=rock if i % 2 else dark)
    ridge(im, 101, 4, col('#1a1420'), 6)
    return im


def bg_ozai():
    im = new(BW, BH)
    vgrad(im, 0, BH, [col(c) for c in ('#2a0508', '#5c0c0c', '#a21c10', '#e0521a', '#f6a03a')])
    for i in range(300, -1, -1):                            # the comet
        t = i / 300
        c = P['Y'] if t < .1 else P['y'] if t < .3 else P['o'] if t < .6 else col('#c9362c')
        disc(im, 150 - 140 * t, 30 - 20 * t, 4.4 * (1 - t) + .4, c)
    disc(im, 150, 30, 3, P['w'])
    d = ImageDraw.Draw(im)
    dark, lit = col('#1c0a0c'), col('#4a1612')
    for x, y in ((40, 46), (120, 58)):                      # airships
        d.ellipse((x, y, x + 22, y + 7), fill=dark)
        d.rectangle((x + 7, y + 7, x + 15, y + 9), fill=dark)
        d.polygon([(x, y + 3), (x - 4, y), (x - 4, y + 7)], fill=dark)
    rnd = random.Random(8)
    for x in (10, 34, 62, 92, 126, 152, 180):               # the rock pillars
        wd, top = rnd.randrange(9, 17), rnd.randrange(52, 84)
        d.rectangle((x - wd // 2, top, x + wd // 2, BH), fill=dark)
        d.rectangle((x - wd // 2 - 1, top, x + wd // 2 + 1, top + 2), fill=dark)
        d.line((x + wd // 2, top + 3, x + wd // 2, BH), fill=lit)
    d.rectangle((0, 100, BW, BH), fill=col('#12060a'))
    return im


def bg_default():
    """Dawn over an air temple: the backdrop behind every screen without its own.

    White round towers with spiral bands and blue upturned roofs, perched on the
    ledges of one steep rock spire, with misty stone pillars standing behind it.
    """
    W, H = 288, 162
    im = new(W, H)
    vgrad(im, 0, H, [col(c) for c in ('#1b2a5c', '#3a4f8f', '#7a6fa8', '#d9897a', '#f6c98a', '#f9e3b0')])
    disc(im, 222, 100, 16, col('#fff3c4'))
    d = ImageDraw.Draw(im)
    px = im.load()
    for cx, cy, wd, c in ((58, 30, 44, '#5a69a8'), (196, 20, 52, '#4a5c9c'), (246, 46, 40, '#9a86b4'),
                          (92, 58, 34, '#b08fae'), (22, 66, 30, '#b08fae'), (266, 76, 34, '#e8a98c')):
        d.rectangle((cx - wd // 2, cy, cx + wd // 2, cy + 2), fill=col(c))     # long flat clouds
        d.rectangle((cx - wd // 3, cy - 2, cx + wd // 4, cy - 1), fill=col(c))
        d.rectangle((cx - wd // 4, cy + 3, cx + wd // 3, cy + 4), fill=col(c))

    def pillar(cx, top, wd, c, edge):                       # a tall, lumpy pillar of rock with a sunlit edge
        blob(im, cx, top + wd * .55, wd / 2, wd * .6, c, cx, rough=.24)
        blob(im, cx - wd * .32, top + wd * 1.25, wd * .42, wd * .7, c, cx + 1, rough=.2)
        d.polygon([(cx - wd // 2, top + wd // 2), (cx + wd // 2, top + wd // 2), (cx + wd // 2 + 6, H), (cx - wd // 2 - 9, H)], fill=c)
        for y in range(top, 118):
            xs = [x for x in range(max(0, cx - wd), min(W, cx + wd + 8)) if px[x, y] == c]
            if xs:
                px[xs[-1], y] = edge
        rnd = random.Random(cx)
        for _ in range(wd // 2):                            # a few ledges
            x, y = cx + rnd.randrange(-wd // 3, wd // 3), top + rnd.randrange(wd // 2, wd * 2)
            for k in range(rnd.randrange(2, 5)):
                if 0 <= x + k < W and y < H and px[x + k, y] == c:
                    px[x + k, y] = edge

    def mist(y0, y1, c, thick):                             # a band of cloud, densest in the middle
        mid, half = (y0 + y1) / 2, (y1 - y0) / 2
        for y in range(y0, y1):
            for x in range(W):
                if (BAYER[y % 4][x % 4] + .5) / 16 > 1 - thick * (1 - abs(y - mid) / half):
                    px[x, y] = c

    for cx, top, wd in ((48, 86, 14), (252, 82, 14), (104, 100, 12)):          # the furthest pillars, lost in haze
        pillar(cx, top, wd, col('#b3a6cc'), col('#c9bedd'))
    mist(104, 126, col('#d9c6d6'), .8)
    for cx, top, wd in ((26, 72, 26), (66, 94, 18), (236, 64, 30), (270, 90, 22)):
        pillar(cx, top, wd, col('#8f86b8'), col('#b3a6cc'))

    # the temple's own spire of rock, lit by the low sun on the right
    lit, mid, shade, crack = col('#d8b48c'), col('#b48f7c'), col('#7d6a8c'), col('#5f5078')
    left = [(138, 52), (134, 58), (128, 66), (124, 76), (118, 84), (114, 96), (108, 104), (104, 116), (98, 128), (94, 144), (86, H)]
    right = [(154, 58), (160, 64), (164, 74), (170, 82), (176, 90), (180, 102), (188, 112), (192, 126), (200, 138), (208, H)]
    d.polygon([(140, 50), (150, 50)] + right + left[::-1], fill=lit)
    d.polygon([(140, 50)] + left + [(128, H), (134, 124), (139, 92), (144, 66)], fill=shade)
    d.polygon([(144, 66), (139, 92), (134, 124), (128, H), (150, H), (150, 120), (147, 90)], fill=mid)
    rnd = random.Random(44)
    for _ in range(70):                                     # ledges and cracks in the rock
        x, y = rnd.randrange(92, 204), rnd.randrange(58, H)
        if px[x, y] in (lit, mid, shade):
            c = {lit: mid, mid: crack, shade: crack}[px[x, y]]
            for k in range(rnd.randrange(3, 8)):
                if x + k < W and px[x + k, y] in (lit, mid, shade):
                    px[x + k, y] = c
    for x, y in ((112, 110), (126, 88), (166, 80), (184, 116), (150, 100), (120, 130), (176, 132), (140, 140)):
        blob(im, x, y, 4, 2, col('#5f8a5a'), x)             # scrub clinging to the ledges
    path = [(146, 72), (160, 80), (148, 90), (166, 100), (152, 110), (176, 120), (154, 132), (182, 144), (160, 156)]
    d.line(path, fill=col('#ecd9ae'))                       # the path winding down

    wall, wall_shade, band = col('#f2eee2'), col('#c4c2d8'), col('#93a7c4')
    roof, roof_dark, roof_hi = col('#3f8fb8'), col('#2a6a94'), col('#8fd0e6')

    def tower(cx, base, hw, ht, wd, spire):
        """A round white tower with spiral bands, a blue roof with upturned eaves and a long thin spire."""
        top = base - ht
        d.rectangle((cx - hw - 1, base, cx + hw + 1, base + 1), fill=col('#ecd9ae'))    # its ledge
        d.rectangle((cx - hw, top, cx + hw, base), fill=wall)
        d.rectangle((cx - hw, top, cx - hw + hw // 2, base), fill=wall_shade)
        for y in range(base - 3, top + 2, -5):                                         # the bands spiral upwards
            d.line((cx - hw, y + 1, cx + hw, y - 1), fill=band)
        rows = [0, 1, 2, 3, 4, 6, wd] if wd >= 8 else [0, 1, 2, wd - 2, wd]
        peak = top - len(rows)
        d.line((cx, peak - spire, cx, peak), fill=roof_hi)
        for i, half in enumerate(rows):
            d.line((cx - half, peak + i, cx + half, peak + i), fill=roof_dark if i == len(rows) - 1 else roof)
            dots(im, [(cx + half, peak + i)], roof_hi)
        eave = peak + len(rows) - 1
        dots(im, [(cx - wd - 1, eave - 1), (cx + wd + 1, eave - 1)], roof)             # upturned corners
        dots(im, [(cx - wd - 1, eave - 2), (cx + wd + 1, eave - 2)], roof_dark)
        dots(im, [(cx, base - 2), (cx, base - 1)], crack)                              # a doorway

    for x0, y0, x1, y1 in ((135, 62, 142, 68), (129, 70, 136, 75), (125, 78, 131, 82)):  # halls stepping down the slope
        d.rectangle((x0, y0, x1, y1), fill=wall)
        d.line((x0, y0, x1, y0), fill=roof)
        dots(im, [((x0 + x1) // 2, y1), ((x0 + x1) // 2, y1 - 1)], crack)
    d.rectangle((127, 101, 139, 103), fill=col('#ecd9ae'))                             # the airball court
    tower(184, 124, 3, 14, 5, 7)
    tower(192, 134, 3, 11, 5, 6)
    tower(172, 98, 3, 13, 5, 7)
    tower(110, 118, 3, 13, 5, 7)
    tower(121, 96, 3, 14, 5, 8)
    tower(157, 68, 3, 15, 5, 7)
    tower(145, 60, 5, 30, 9, 13)                            # the great tower at the top
    d.rectangle((139, 30, 151, 33), fill=wall)              # ...with a gallery under its roof
    dots(im, [(141, 32), (144, 32), (147, 32), (150, 32)], crack)

    ridge(im, 134, 10, col('#5d5a8c'), 32, top=col('#7f79ab'))
    mist(124, 138, col('#c9b6cf'), .75)
    ridge(im, 148, 8, col('#3d3b66'), 33, top=col('#55528a'))
    dark = col('#1c1830')
    for pts, tx in (([(0, H), (0, 118), (16, 114), (38, 122), (56, 140), (66, H)], 18),
                    ([(W, H), (W, 124), (W - 22, 120), (W - 44, 130), (W - 58, 148), (W - 62, H)], W - 26)):
        d.polygon(pts, fill=dark)                                           # cliffs in the foreground
        d.line((tx, 96, tx + 2, 118), fill=dark, width=2)                   # ...each with a windswept pine
        for dx, dy, wd in ((-9, 92, 14), (-3, 86, 12), (2, 98, 12)):
            d.rectangle((tx + dx, dy, tx + dx + wd, dy + 3), fill=col('#24304a'))
            d.rectangle((tx + dx + 2, dy - 2, tx + dx + wd - 3, dy - 1), fill=col('#24304a'))
    put(im, grid([                                          # Appa on his way home, riders and all
        '....................ob............',
        '...................NNNN...tt......',
        '..............wwwwwNNNNwwwttww....',
        '...........wwwnnnnnnnnnnnnnnnnww..',
        '.........wwwwwwwwwwwwwwwwwwnnnnnw.',
        'nnn....wwwwwwwwwwwwwwwwwwwwwwnnnww',
        'wnnnnwwwwwwwwwwwwwwwwwwwwwwwwwnwww',
        'wwwnnnwwwwwwwwwwwwwwwwwwwwwDwwwwDD',
        '.wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwDD',
        '...wwwwwwwwwwwwwwwwwwwwwwwwwwwwww.',
        '........wwWWWWWWWWWWWWWWWWwwGGGG..',
        '.........WWWWWWWWWWWWWWWWW........',
        '.........WWWgg.WWWgg.WWWgg........',
        '.........WWWg..WWWg..WWWg.........',
        '.........ttt...ttt...ttt..........',
    ]), 84, 34)   # up beside the great tower, where he stays in view however the window is shaped
    return im


ART['bg-default'] = bg_default()

for name, fn in (('bg-tea', bg_tea), ('bg-dragon', bg_dragon), ('bg-ozai', bg_ozai)):
    ART[name] = fn()


# ── card faces (60 x 50) ────────────────────────────────────────

CW, CH = 60, 50


def scene(cols):
    im = new(CW, CH)
    vgrad(im, 0, CH, [col(c) for c in cols])
    return im, ImageDraw.Draw(im)


def card_iceberg():
    im, d = scene(('#0d1740', '#1f3f8c', '#3f8fd6'))
    rnd = random.Random(1)
    for _ in range(18):
        dots(im, [(rnd.randrange(CW), rnd.randrange(22))], P['w'])
    d.rectangle((0, 37, CW, CH), fill=col('#16305a'))
    d.polygon([(15, 38), (22, 14), (31, 5), (41, 15), (46, 38)], fill=P['C'])
    d.polygon([(31, 5), (41, 15), (46, 38), (34, 38)], fill=P['c'])
    d.polygon([(20, 38), (26, 45), (40, 45), (44, 38)], fill=col('#3f6f9c'))
    disc(im, 31, 25, 7.5, col('#bfeaf7'))
    disc(im, 31, 25, 5.5, P['Y'])
    d.rectangle((30, 23, 32, 28), fill=P['o'])              # the boy
    dots(im, [(31, 22), (30, 22), (32, 22)], P['T'])
    dots(im, [(31, 21)], P['c'])
    for x in (4, 12, 50, 55):
        d.line((x, 41, x + 3, 41), fill=P['c'])
    return im


def card_nowar():
    im, d = scene(('#8fd3ee', '#c8eb9c', '#c8eb9c'))
    wall, line = col('#b9a47a'), col('#8a7a5a')
    d.rectangle((0, 14, CW, CH), fill=wall)
    for x in range(0, CW, 8):
        d.rectangle((x, 10, x + 4, 14), fill=wall)
    for y in range(18, CH, 5):
        d.line((0, y, CW, y), fill=line)
        for x in range((y % 2) * 5, CW, 10):
            d.line((x, y, x, y + 5), fill=line)
    put(im, ART['el-earth'].resize((32, 32), Image.NEAREST), 14, 15)
    return im


def card_yipyip():
    im, d = scene(('#2f7fc9', '#7fbfea', '#e8f1e2'))
    put(im, ART['cloud'], -8, 34)
    put(im, ART['cloud'], 36, 2)
    put(im, ART['appa'], -4, 5)
    return im


def card_cabbages():
    im, d = scene(('#f6cf4f', '#ef8a2b', '#c9362c'))
    for i in range(12):                                     # impact burst
        a = i * math.pi / 6
        d.line((30, 28, 30 + 60 * math.cos(a), 28 + 60 * math.sin(a)), fill=P['Y'])
    put(im, ART['cart'].rotate(-18, expand=True, resample=Image.NEAREST), 10, 16)
    for x, y in ((2, 3), (22, -2), (42, 6), (-3, 26), (46, 30)):
        put(im, ART['cabbage'], x, y)
    return im


def card_rough():
    im, d = scene(('#070b24', '#152a66', '#1f3f8c'))
    rnd = random.Random(2)
    for _ in range(20):
        dots(im, [(rnd.randrange(CW), rnd.randrange(30))], P['w'])
    put(im, ART['moon'], 5, 3)
    d.rectangle((0, 40, CW, CH), fill=col('#0d1740'))
    for y, x0, x1 in ((41, 10, 26), (43, 13, 23), (45, 15, 21)):
        d.line((x0, y, x1, y), fill=P['W'])
    d.ellipse((38, 12, 54, 28), fill=P['r'])                # the war balloon
    d.ellipse((42, 15, 47, 20), fill=P['o'])
    d.line((40, 27, 43, 33), fill=P['D'])
    d.line((52, 27, 49, 33), fill=P['D'])
    d.rectangle((43, 33, 49, 36), fill=P['n'])
    return im


def card_cactus():
    im = new(CW, CH)
    px = im.load()
    rings = [P[c] for c in 'mypclo']
    for y in range(CH):
        for x in range(CW):
            px[x, y] = rings[int(math.hypot(x - 30, y - 26) / 5 + math.atan2(y - 26, x - 30) * 1.2) % len(rings)]
    put(im, ART['mushroom'], 28, 22)
    put(im, ART['cactus'], 2, 20)
    return im


def card_tunnel():
    im = new(CW, CH, col('#0b0705'))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 4, 54, 70), fill=col('#1c120c'))
    d.ellipse((14, 12, 46, 70), fill=col('#050403'))
    for x, y in ((2, 26), (40, 28), (13, 8), (30, 0)):
        disc(im, x + 8, y + 9, 11, col('#12301c'))
    for x, y in ((2, 26), (40, 28), (13, 8), (30, 0)):
        put(im, ART['crystal'], x, y)
    return im


def card_tea():
    im, d = scene(('#7a4326', '#5a2f1a', '#5a2f1a'))
    d.rectangle((0, 40, CW, CH), fill=P['n'])
    d.line((0, 40, CW, 40), fill=P['t'])
    put(im, ART['teapot'], 6, 17)
    put(im, ART['pin-tea'].crop((0, 4, 20, 14)), 38, 31)
    for i, (x, y) in enumerate(((39, 9), (38, 6), (40, 3), (44, 26), (43, 23), (45, 20), (48, 25), (49, 22))):
        dots(im, [(x, y), (x, y + 1)], P['w'])
    return im


def card_moon():
    im = new(CW, CH, col('#2e6934'))
    disc(im, 30, 25, 23, col('#16305a'))
    disc(im, 30, 25, 21, col('#235a9c'))
    d = ImageDraw.Draw(im)
    d.arc((14, 9, 46, 41), 20, 120, fill=P['b'])
    d.arc((11, 6, 49, 44), 200, 300, fill=P['b'])
    put(im, ART['koi'], 15, 10)
    rnd = random.Random(6)
    for _ in range(30):
        x, y = rnd.randrange(CW), rnd.randrange(CH)
        if math.hypot(x - 30, y - 25) > 24:
            dots(im, [(x, y)], P['l'])
    return im


def card_dragon():
    im = new(CW, CH, col('#2a1a4a'))
    px = im.load()
    rainbow = [P[c] for c in 'royelbp']
    for y in range(CH):
        for x in range(CW):
            r = math.hypot(x - 30, (y - 50) * 1.1)
            if 20 < r < 48:
                px[x, y] = rainbow[int((r - 20) / 4) % 7]
    put(im, ART['ran'], -20, 0)
    put(im, ART['shaw'], 26, 0)
    return im


def card_avatar():
    im = new(CW, CH, col('#0d1740'))
    px = im.load()
    for y in range(CH):
        for x in range(CW):
            dist = math.hypot(x - 30, y - 25)
            if dist < 26 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 26:
                px[x, y] = P['c'] if dist > 12 else P['C']
    put(im, ART['logo'], 19, 15)
    put(im, ART['el-water'], 1, 1)
    put(im, ART['el-earth'], 43, 1)
    put(im, ART['el-fire'], 1, 33)
    put(im, ART['el-air'], 43, 33)
    return im


def card_energy():
    im = new(CW, CH, col('#070b24'))
    d = ImageDraw.Draw(im)
    for x0, core, glow in ((19, P['C'], P['b']), (36, P['Y'], P['o'])):   # the two beams
        d.rectangle((x0 - 2, 0, x0 + 6, 30), fill=glow)
        d.rectangle((x0, 0, x0 + 4, 30), fill=core)
    D = P['D']
    d.rectangle((0, 44, CW, CH), fill=col('#2a1a2e'))
    d.rectangle((19, 30, 24, 44), fill=D)                   # Aang, standing
    disc(im, 21.5, 28, 3, D)
    d.line((24, 33, 35, 31), fill=D, width=2)               # arm to his forehead
    d.polygon([(33, 44), (35, 34), (41, 34), (44, 44)], fill=D)   # Ozai, kneeling
    disc(im, 38, 31, 3, D)
    dots(im, [(21, 27), (22, 27)], P['C'])
    dots(im, [(38, 30), (39, 30)], P['Y'])
    return im


for name, fn in (('iceberg', card_iceberg), ('nowar', card_nowar), ('yipyip', card_yipyip), ('cabbages', card_cabbages),
                 ('rough', card_rough), ('cactus', card_cactus), ('tunnel', card_tunnel), ('tea', card_tea),
                 ('moon', card_moon), ('dragon', card_dragon), ('avatar', card_avatar), ('energy', card_energy)):
    ART['card-' + name] = fn()


# ── the secrets: the swamp, the Melon Lord, Koh ─────────────────

def melon():
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    n, R, e, E, D = (P[c] for c in 'nReED')
    d.rectangle((15, 19, 16, 31), fill=n)                  # a post...
    d.polygon([(5, 31), (9, 23), (22, 23), (26, 31)], fill=R)   # ...a ragged red robe...
    for x in (9, 14, 20):
        d.polygon([(x, 31), (x + 2, 27), (x + 4, 31)], fill=CLEAR)
    d.line((2, 24, 29, 24), fill=n, width=2)
    dots(im, [(1, 23), (1, 26), (2, 27), (30, 23), (30, 26), (29, 27)], P['y'])
    d.ellipse((7, 1, 24, 20), fill=e)                      # ...and a melon for a head
    px = im.load()
    for x in (10, 13, 18, 21):
        for y in range(1, 21):
            if px[x, y] == e:
                px[x, y] = E
    dots(im, [(11, 4), (12, 3), (11, 5)], P['L'])
    d.polygon([(10, 8), (14, 9), (12, 12)], fill=D)        # carved eyes and a jagged grin
    d.polygon([(21, 8), (17, 9), (19, 12)], fill=D)
    d.polygon([(10, 14), (12, 16), (14, 14), (16, 16), (18, 14), (20, 16), (21, 14), (20, 18), (11, 18)], fill=D)
    return outline(im, P['k'])


def noface():
    """What is left of you when Koh wins: no face at all."""
    im, d = bust(P['T'], P['o'], P['y'])
    d.rectangle((14, 7, 17, 11), fill=P['b'])              # the arrow is all he left
    d.polygon([(12, 11), (19, 11), (16, 15), (15, 15)], fill=P['b'])
    return outline(im, P['k'])


KOH_FACES = [grid(rows, mirror=True, edge=None) for rows in (
    [   # the white mask
        '...wwww', '.wwwwww', '.wwwGww', 'wwwwwww', 'wwGGGww', 'wwGDDGw', 'wwwGGww', 'wwwwwww',
        'wwwwwwW', 'wwwwwwW', 'wwwwwww', 'wwwwwrr', '.wwwwrr', '.wwwwww', '..wwwww', '....www',
    ],
    [   # an old man
        '...TTTT', '.TTTTTT', '.TTTTTT', 'TTsssTT', 'TTgggTT', 'TTTDDTT', 'TTTTTTT', 'TTTTTTs',
        'TTTTTss', 'TTggggg', 'TTgggTT', 'TTTTTDD', '.TTTTTT', '.TTgggg', '..ggggg', '....ggg',
    ],
    [   # a woman
        '...DDDD', '.DDDDDD', '.DDTTTT', 'DDTTTTT', 'DDTDDDT', 'DDTTDDT', 'DDTTTTT', 'DDTTTTs',
        'DDTTTTs', 'DTTmTTT', 'DTTTTTT', 'DTTTTrr', '.DTTTrr', '.DTTTTT', '..DTTTT', '....TTT',
    ],
    [   # a blue-faced baboon
        '...nnnn', '.nnnnnn', '.nnnnnn', 'nnnnnnn', 'nnDDDnn', 'nnyyDnr', 'nbbbbrr', 'bbcbbrr',
        'bbcbbrr', 'bbcbbrr', 'bbbbbrr', '.bbbwww', '.nnDDDD', '..nnnnn', '...nnnn', '....nnn',
    ],
)]


def koh(face):
    """A very long centipede with somebody else's face."""
    im = new(84, 64)
    d = ImageDraw.Draw(im)
    body, band, leg = col('#2b2028'), col('#4a3440'), col('#8a6a52')
    path = spline([(42, 26), (42, 36), (31, 43), (19, 41), (12, 50), (22, 58), (40, 59), (58, 57), (70, 50), (73, 40), (66, 33)], 22)
    n = len(path)
    for i in range(n - 1, -1, -1):
        x, y = path[i]
        r = 5.2 * (1 - i / (n - 1) * .45)
        if i % 5 == 2 and 0 < i < n - 1:                   # legs, lots of them
            (x0, y0), (x1, y1) = path[i - 1], path[i + 1]
            nx, ny = -(y1 - y0), (x1 - x0)
            ln = math.hypot(nx, ny) or 1
            nx, ny = nx / ln, ny / ln
            for side in (1, -1):
                d.line((x + side * nx * r, y + side * ny * r, x + side * nx * (r + 4), y + side * ny * (r + 4) + 1), fill=leg)
        disc(im, x, y, r, band if i % 10 < 5 else body)
    for deg in (150, 180, 210, 330, 0, 30):                # a few more around the head
        a = math.radians(deg)
        d.line((41.5 + 11 * math.cos(a), 15.5 + 14 * math.sin(a), 41.5 + 16 * math.cos(a), 15.5 + 18 * math.sin(a)), fill=leg)
    d.ellipse((30, 1, 53, 30), fill=body)
    put(im, face, 35, 6)
    return outline(im, col('#7a5638'))


ART['melon'] = melon()
ART['noface'] = noface()
for i, face in enumerate(KOH_FACES):
    ART[f'koh-{i + 1}'] = koh(face)


def stage_swamp():
    im = new(SW, SH)
    vgrad(im, 0, SH, [col(c) for c in ('#16291f', '#24452f', '#3b6a43', '#5a8a55')])
    d = ImageDraw.Draw(im)
    rnd = random.Random(14)
    for _ in range(14):                                     # trees further back
        x, wd = rnd.randrange(SW), rnd.randrange(3, 8)
        d.rectangle((x, 0, x + wd, 72), fill=col('#2a4a33'))
    px = im.load()
    for y in range(38, 60):                                 # fog
        for x in range(SW):
            if (BAYER[y % 4][x % 4] + .5) / 16 > .35 + abs(y - 49) * .06:
                px[x, y] = col('#8fb59a')
    trunk, bark = col('#3b2a1c'), col('#55402a')
    d.polygon([(42, 0), (86, 0), (80, 40), (94, 76), (34, 76), (48, 40)], fill=trunk)    # the great banyan-grove tree
    for x0, x1 in ((30, 22), (40, 14), (90, 104), (98, 118), (60, 56), (72, 78)):
        d.line((x0, 44, x1, 78), fill=trunk, width=3)       # roots reaching into the water
    for x in range(50, 80, 5):
        d.line((x, 0, x + rnd.randrange(-3, 4), 70), fill=bark)
    for _ in range(26):                                     # hanging vines
        x, ln = rnd.randrange(SW), rnd.randrange(10, 46)
        d.line((x, 0, x, ln), fill=col('#1d3a24'))
        dots(im, [(x - 1, ln - 2), (x + 1, ln - 5), (x - 1, ln - 9)], col('#4e9c45'))
    d.rectangle((0, 76, SW, SH), fill=col('#1f3d33'))       # murky water
    for _ in range(30):
        x, y = rnd.randrange(SW - 6), rnd.randrange(78, SH)
        d.line((x, y, x + rnd.randrange(3, 7), y), fill=col('#2f5a48'))
    for x, y in ((18, 84), (132, 80), (150, 90), (104, 88)):
        d.ellipse((x, y, x + 7, y + 3), fill=col('#4e9c45'))
    for _ in range(24):                                     # fireflies
        dots(im, [(rnd.randrange(SW), rnd.randrange(10, 76))], col('#f6f08a'))
    return im


def stage_koh():
    im = new(SW, SH, col('#0b1512'))
    px = im.load()
    for y in range(SH):                                     # a sickly glow from somewhere behind him
        for x in range(SW):
            dist = math.hypot((x - 88) * .75, y - 46)
            if dist < 58 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 58:
                px[x, y] = col('#2f6a5c') if dist < 26 else col('#1b4640')
    d = ImageDraw.Draw(im)
    root, dark = col('#241a14'), col('#120c0a')
    rnd = random.Random(12)
    for _ in range(22):                                     # roots hanging down
        x, ln, wd = rnd.randrange(SW), rnd.randrange(12, 44), rnd.randrange(2, 5)
        d.polygon([(x - wd, 0), (x + wd, 0), (x + rnd.randrange(-6, 7), ln)], fill=root)
    ridge(im, 86, 5, root, 41, top=col('#3a2a20'))
    d.polygon([(0, 0), (28, 0), (18, 30), (32, 60), (14, SH), (0, SH)], fill=dark)       # the hollow tree's walls
    d.polygon([(SW, 0), (SW - 28, 0), (SW - 18, 34), (SW - 34, 58), (SW - 12, SH), (SW, SH)], fill=dark)
    for _ in range(30):                                     # drifting spirit lights
        dots(im, [(rnd.randrange(24, SW - 24), rnd.randrange(8, 84))], col('#7ff0d0'))
    return im


ART['stage-swamp'] = stage_swamp()
ART['stage-koh'] = stage_koh()


def card_swamp():
    im, d = scene(('#16291f', '#3b6a43', '#5a8a55'))
    trunk = col('#3b2a1c')
    d.polygon([(8, 0), (26, 0), (23, 22), (30, 40), (4, 40), (11, 22)], fill=trunk)
    for x0, x1 in ((6, 0), (28, 36), (17, 20)):
        d.line((x0, 26, x1, 42), fill=trunk, width=2)
    rnd = random.Random(15)
    px = im.load()
    for y in range(20, 30):
        for x in range(CW):
            if (BAYER[y % 4][x % 4] + .5) / 16 > .45 + abs(y - 25) * .1:
                px[x, y] = col('#8fb59a')
    for _ in range(10):
        x, ln = rnd.randrange(CW), rnd.randrange(5, 20)
        d.line((x, 0, x, ln), fill=col('#1d3a24'))
    d.rectangle((0, 40, CW, CH), fill=col('#1f3d33'))
    put(im, grid(MINI_APPA).rotate(-12, expand=True, resample=Image.NEAREST), 34, 30)   # one stuck sky bison
    for _ in range(12):
        dots(im, [(rnd.randrange(CW), rnd.randrange(4, 40))], col('#f6f08a'))
    return im


def card_melon():
    im, d = scene(('#8fd3ee', '#c8eb9c', '#f6c98a'))
    d.rectangle((0, 40, CW, CH), fill=P['t'])
    d.ellipse((2, 34, 16, 46), fill=P['S'])                 # boulders
    d.ellipse((44, 32, 58, 46), fill=P['S'])
    put(im, ART['melon'], 13, 8)
    put(im, ART['el-fire'], -2, 20)
    put(im, ART['el-fire'], 46, 18)
    return im


def card_koh():
    im = new(CW, CH, col('#0b1512'))
    px = im.load()
    for y in range(CH):
        for x in range(CW):
            dist = math.hypot(x - 30, y - 16)
            if dist < 28 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 28:
                px[x, y] = col('#1b4640')
    put(im, ART['koh-1'], -13, -3)
    return im


ART['card-swamp'] = card_swamp()
ART['card-melon'] = card_melon()
ART['card-koh'] = card_koh()


# ── more secrets: the labyrinth under the cave, and being reborn ─

def badgermole():
    im = new(56, 46)
    d = ImageDraw.Draw(im)
    n, N, w = P['n'], P['N'], P['w']
    d.ellipse((7, 3, 15, 11), fill=N)                      # ears
    d.ellipse((40, 3, 48, 11), fill=N)
    d.ellipse((4, 6, 51, 52), fill=n)                      # a mountain of fur
    d.ellipse((16, 13, 39, 40), fill=P['S'])               # face
    d.polygon([(25, 8), (30, 8), (31, 30), (24, 30)], fill=w)   # the badger stripe
    d.ellipse((21, 27, 34, 39), fill=P['t'])               # snout
    d.ellipse((25, 28, 30, 32), fill=P['m'])
    d.line((27, 33, 27, 36), fill=N)
    dots(im, [(18, 21), (19, 21), (20, 22), (35, 22), (36, 21), (37, 21)], P['g'])   # blind eyes
    for x in (5, 10, 15, 36, 41, 46):                      # digging claws
        d.polygon([(x, 45), (x + 2, 37), (x + 4, 45)], fill=w)
    shade_under(im, n, N, 2)
    return outline(im, P['k'])


def roku():
    w, D = P['w'], P['D']
    im, d = bust(P['T'], P['r'], P['a'], hair=w, hair_box=(7, 3, 24, 20))
    d.rectangle((6, 11, 9, 30), fill=w)                    # long white hair
    d.rectangle((22, 11, 25, 30), fill=w)
    d.ellipse((9, 7, 22, 24), fill=P['T'])
    d.rectangle((14, 1, 17, 5), fill=w)                    # topknot with its gold headpiece
    d.polygon([(13, 3), (15, 0), (16, 0), (18, 3), (17, 4), (14, 4)], fill=P['a'])
    d.polygon([(11, 19), (20, 19), (21, 23), (17, 31), (14, 31), (10, 23)], fill=w)   # beard
    d.line((12, 18, 19, 18), fill=w)
    dots(im, [(11, 14), (12, 14), (19, 14), (20, 14)], D)
    d.line((10, 12, 13, 12), fill=P['g'])
    d.line((18, 12, 21, 12), fill=P['g'])
    dots(im, [(15, 16), (16, 16)], P['s'])
    d.line((14, 21, 17, 21), fill=P['G'])
    return outline(im, P['k'])


def stage_cave_dark():
    """The same cave with the torch out: only the outlines of the three tunnels."""
    im = new(SW, SH, col('#030605'))
    d = ImageDraw.Draw(im)
    rim = col('#12201a')
    for cx in (30, 88, 146):
        d.ellipse((cx - 16, 26, cx + 16, 62), fill=rim)
        d.rectangle((cx - 16, 44, cx + 16, 72), fill=rim)
        d.ellipse((cx - 13, 29, cx + 13, 61), fill=col('#000000'))
        d.rectangle((cx - 13, 45, cx + 13, 72), fill=col('#000000'))
    d.line((0, 73, SW, 73), fill=rim)
    rnd = random.Random(19)
    for _ in range(40):
        dots(im, [(rnd.randrange(SW), rnd.randrange(76, SH))], rim)
    return im


def card_lovers():
    im = new(CW, CH, col('#050a0c'))
    d = ImageDraw.Draw(im)
    frames = [(0, 0, 59, 49), (9, 7, 50, 42), (16, 13, 43, 36), (21, 17, 38, 32)]   # a tunnel, felt in depth
    for i, box in enumerate(frames):
        d.rectangle(box, outline=col(('#9fd6dc', '#6fa6ae', '#4a7880', '#f2c45a')[i]))
    for (a, b) in zip(frames, frames[1:]):
        for ca, cb in (((a[0], a[1]), (b[0], b[1])), ((a[2], a[1]), (b[2], b[1])), ((a[0], a[3]), (b[0], b[3])), ((a[2], a[3]), (b[2], b[3]))):
            d.line((ca, cb), fill=col('#4a7880'))
    d.rectangle((22, 18, 37, 31), fill=col('#3a2a1c'))     # the tomb at the end
    for x, y in ((27, 20), (28, 20), (31, 20), (32, 20), (26, 21), (33, 21)):
        dots(im, [(x, y)], P['m'])
    d.polygon([(26, 21), (33, 21), (30, 24), (29, 24)], fill=P['m'])
    disc(im, 26.5, 27, 2, P['a'])                          # Oma and Shu
    disc(im, 32.5, 27, 2, P['a'])
    d.rectangle((24, 29, 35, 31), fill=P['a'])
    for x, y in ((4, 20), (12, 30), (54, 16), (47, 28), (3, 40), (55, 38)):   # crystals
        dots(im, [(x, y), (x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)], P['l'])
        dots(im, [(x, y)], P['L'])
    return im


def card_cycle():
    im, d = scene(('#0d1740', '#1f3f8c', '#0d1740'))
    rnd = random.Random(21)
    for _ in range(16):
        dots(im, [(rnd.randrange(CW), rnd.randrange(18))], P['c'])
    d.line((0, 43, CW, 43), fill=P['B'])
    for i, (x, sz) in enumerate(((12, 1.0), (27, .8), (38, .62), (47, .48), (54, .36))):   # the lives before this one
        c = (P['C'], P['c'], P['c'], P['b'], P['b'])[i]
        h, base = 26 * sz, 42
        d.polygon([(x - 6 * sz, base), (x - 3 * sz, base - h + 4 * sz), (x + 3 * sz, base - h + 4 * sz), (x + 6 * sz, base)], fill=c)
        disc(im, x, base - h, 3.2 * sz + .6, c)
    dots(im, [(12, 15), (12, 16), (11, 17), (13, 17), (12, 17), (12, 18)], P['b'])   # the nearest one has an arrow
    return im


ART['badgermole'] = badgermole()
ART['roku'] = roku()
ART['stage-cave-dark'] = stage_cave_dark()
ART['card-lovers'] = card_lovers()
ART['card-cycle'] = card_cycle()


# ── Wan Shi Tong, for a long streak of right answers ────────────

def owl():
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    body, feather, w, D = col('#2c2f4a'), col('#454a72'), P['w'], P['D']
    d.ellipse((2, 20, 29, 44), fill=body)                  # hunched shoulders
    d.ellipse((6, 3, 25, 26), fill=body)                   # head
    for x, y in ((6, 26), (10, 28), (20, 28), (24, 26), (13, 29), (17, 29), (4, 24), (26, 24)):
        dots(im, [(x, y), (x + 1, y), (x, y + 1)], feather)
    d.ellipse((8, 6, 16, 18), fill=w)                      # the pale, heart-shaped face
    d.ellipse((15, 6, 23, 18), fill=w)
    d.polygon([(9, 15), (22, 15), (16, 23), (15, 23)], fill=w)
    d.polygon([(14, 5), (17, 5), (16, 9), (15, 9)], fill=body)
    d.ellipse((10, 9, 13, 13), fill=D)                     # eyes
    d.ellipse((18, 9, 21, 13), fill=D)
    dots(im, [(11, 10), (19, 10)], P['g'])
    d.polygon([(15, 14), (16, 14), (16, 18), (15, 18)], fill=P['a'])   # beak
    dots(im, [(10, 16), (21, 16), (12, 19), (19, 19)], P['W'])
    return outline(im, col('#5a5f8c'))   # a pale edge, so he shows up against a dark screen


def card_owl():
    im, d = scene(('#3b2a1c', '#5b3920', '#3b2a1c'))
    rnd = random.Random(23)
    for y in (9, 21, 33, 45):                               # shelf after shelf of scrolls
        d.line((0, y, CW, y), fill=P['N'])
        for x in range(1, CW, 4):
            c = P[rnd.choice('trwayeb')]
            d.rectangle((x, y - rnd.randrange(4, 8), x + 2, y - 1), fill=c)
    disc(im, 30, 26, 19, col('#241710'))
    put(im, ART['owl'], 13, 8)
    return im


ART['owl'] = owl()
ART['card-owl'] = card_owl()


# ── the lovers' tomb, and the dragon masters at full size ───────

STONE = [col(c) for c in ('#120d0a', '#2a2018', '#4a3a2a', '#6e5a40', '#96805a', '#c4aa78')]   # darkest to brightest
STELE = [col(c) for c in ('#2f4a30', '#55784a', '#c9d8a0')]
FLAME = [col(c) for c in ('#ef8a2b', '#fff0a6')]


def tomb(W, H, people=True):
    """The tomb of Oma and Shu: two seated statues leaning into a kiss inside an
    arched alcove, a carved tablet between them, lit from below by torches."""
    im = new(W, H, STONE[0])
    d = ImageDraw.Draw(im)
    course = max(3, H // 9)                                 # the brick wall around the alcove
    for i, y in enumerate(range(0, H, course)):
        d.line((0, y, W, y), fill=STONE[1])
        for x in range((i % 2) * course, W, course * 2):
            d.line((x, y, x, y + course), fill=STONE[1])
    x0, x1, top = round(W * .1), round(W * .9) - 1, round(H * .04)
    rise = (x1 - x0) * .42
    d.ellipse((x0, top, x1, top + rise * 2), fill=STONE[2])                 # the arch and its rim
    d.rectangle((x0, top + rise, x1, H), fill=STONE[2])
    d.ellipse((x0 + 2, top + 2, x1 - 2, top + rise * 2), fill=STONE[0])
    d.rectangle((x0 + 2, top + rise, x1 - 2, H), fill=STONE[0])

    hw = W // 2
    half = new(hw, H)                                       # the left-hand statue; the other is its mirror image
    h = ImageDraw.Draw(half)
    X, Y = lambda f: f * hw, lambda f: f * H
    cx, cy, r = X(.60), Y(.27), X(.40)                      # the fan-shaped headdress, with its ribs
    h.pieslice((cx - r, cy - r, cx + r, cy + r), 150, 300, fill=STONE[2])
    for deg in range(160, 300, 20):
        a = math.radians(deg)
        h.line((cx, cy, cx + r * math.cos(a), cy + r * math.sin(a)), fill=STONE[3])
    h.ellipse((X(.10), Y(.70), X(1.04), Y(.98)), fill=STONE[3])             # crossed legs
    h.polygon([(X(.26), Y(.80)), (X(.32), Y(.48)), (X(.50), Y(.41)), (X(.76), Y(.43)), (X(.86), Y(.58)), (X(.88), Y(.80))], fill=STONE[3])
    h.line((X(.36), Y(.52), X(.40), Y(.76)), fill=STONE[2])                 # folds in the robe
    h.line((X(.50), Y(.50), X(.52), Y(.74)), fill=STONE[2])
    h.line((X(.64), Y(.50), X(.94), Y(.70)), fill=STONE[4], width=max(1, round(X(.10))))   # the arm reaching across
    h.polygon([(X(.58), Y(.34)), (X(.76), Y(.36)), (X(.78), Y(.45)), (X(.56), Y(.45))], fill=STONE[3])   # neck
    h.ellipse((X(.48), Y(.15), X(.86), Y(.38)), fill=STONE[4])              # head
    h.polygon([(X(.80), Y(.18)), (X(.90), Y(.21)), (X(.93), Y(.26)), (X(1.0), Y(.29)),               # the face in profile:
               (X(.94), Y(.31)), (X(1.0), Y(.33)), (X(.93), Y(.36)), (X(.84), Y(.39)), (X(.74), Y(.38))], fill=STONE[4])   # brow, nose, lips
    h.ellipse((X(.44), Y(.12), X(.80), Y(.27)), fill=STONE[2])              # hair, swept up...
    h.ellipse((X(.50), Y(.05), X(.70), Y(.17)), fill=STONE[2])              # ...into a knot
    h.line((X(.80), Y(.26), X(.87), Y(.26)), fill=STONE[1])                 # closed eye
    px = half.load()
    for y in range(H):                                      # lit from below: darker at the very top, brighter low down
        for x in range(hw):
            if px[x, y][3] and px[x, y] in STONE[2:5]:
                i = STONE.index(px[x, y])
                if y < H * .12:
                    px[x, y] = STONE[i - 1]
                elif y > H * .66:
                    px[x, y] = STONE[i + 1]
    im.alpha_composite(half, (0, 0))
    im.alpha_composite(half.transpose(Image.FLIP_LEFT_RIGHT), (W - hw, 0))

    sx0, sx1 = round(W * .455), round(W * .545)             # the tablet between them
    d.rectangle((sx0, Y(.50), sx1, Y(.88)), fill=STELE[0])
    d.rectangle((sx0, Y(.50), sx1, Y(.50)), fill=STELE[1])
    d.line((sx0, Y(.50), sx0, Y(.88)), fill=STELE[1])
    for y in range(round(Y(.56)), round(Y(.84)), 3):
        dots(im, [((sx0 + sx1) // 2, y), ((sx0 + sx1) // 2 + (y // 3) % 2, y + 1)], STELE[2])
    d.rectangle((0, Y(.92), W, H), fill=STONE[2])           # floor
    d.line((0, Y(.92), W, Y(.92)), fill=STONE[4])
    for x in (round(W * .40), round(W * .60)):              # torches
        d.line((x, Y(.84), x, Y(.92)), fill=STONE[1])
        dots(im, [(x, round(Y(.82)))], FLAME[1])
        dots(im, [(x, round(Y(.82)) - 1), (x - 1, round(Y(.82))), (x + 1, round(Y(.82)))], FLAME[0])
    if people:                                              # the two who found it
        ax, fy = W // 2 - 3, round(Y(.92)) - 1
        dots(im, [(ax, fy), (ax, fy - 1)], P['o'])
        dots(im, [(ax, fy - 2)], P['T'])
        dots(im, [(ax + 5, fy), (ax + 5, fy - 1)], P['b'])
        dots(im, [(ax + 5, fy - 2)], P['n'])
    return im


def epic_dragon(main, dark, belly, wing, rib):
    """A dragon master risen to full height, facing right: wings, horns, whiskers, teeth."""
    W, H = 112, 132
    im = new(W, H)
    d = ImageDraw.Draw(im)
    fin, k = col('#eef2f8'), P['k']
    d.polygon([(46, 38), (26, 8), (4, 2), (12, 20), (2, 30), (18, 34), (8, 50), (30, 46), (44, 50)], fill=wing)   # the wing
    for tip in ((26, 8), (4, 2), (2, 30), (8, 50)):
        d.line((46, 40, tip[0], tip[1]), fill=rib)
    path = spline([(84, 30), (70, 24), (54, 26), (40, 36), (34, 52), (42, 68), (58, 78), (70, 92), (66, 108), (50, 118), (30, 120), (14, 112), (4, 102)], 22)
    n = len(path)
    for i in range(n - 1, -1, -1):                          # tail first, so the neck lies on top
        x, y = path[i]
        t = i / (n - 1)
        r = 7.6 * (1 - t ** 1.5 * .84)
        (x0, y0), (x1, y1) = path[max(0, i - 1)], path[min(n - 1, i + 1)]
        nx, ny = -(y1 - y0), (x1 - x0)
        ln = math.hypot(nx, ny) or 1
        nx, ny = nx / ln, ny / ln
        if i % 5 == 2:                                      # white spines all the way down the back
            for j in range(3):
                disc(im, x + nx * (r + j), y + ny * (r + j), 1.6 - j * .5, fin)
        disc(im, x, y, r, main)
    for i in range(n - 1, 6, -1):                           # the pale belly, in plates, on the other side
        x, y = path[i]
        r = 7.6 * (1 - (i / (n - 1)) ** 1.5 * .84)
        (x0, y0), (x1, y1) = path[i - 1], path[min(n - 1, i + 1)]
        nx, ny = -(y1 - y0), (x1 - x0)
        ln = math.hypot(nx, ny) or 1
        disc(im, x - nx / ln * r * .55, y - ny / ln * r * .55, r * .45, dark if i % 4 == 0 else belly)
    for (sx, sy), (ex, ey) in (((60, 78), (82, 70)), ((66, 100), (86, 104))):     # legs reaching forward, with claws
        d.line((sx, sy, (sx + ex) // 2, ey + 7), fill=dark, width=6)
        d.line(((sx + ex) // 2, ey + 7, ex, ey), fill=main, width=4)
        for cy in (-2, 0, 2):                               # three claws
            d.line((ex, ey + cy, ex + 4, ey + cy + 1), fill=fin)
    d.line((80, 22, 60, 8), fill=k, width=2)                # long swept-back horns
    d.line((84, 20, 66, 2), fill=k, width=2)
    for x, y in ((70, 20), (66, 22), (62, 24), (72, 30), (68, 32)):                # mane
        d.line((x, y, x - 5, y - 3), fill=belly)
    d.ellipse((74, 18, 96, 38), fill=main)                  # head
    d.polygon([(92, 22), (108, 25), (109, 31), (92, 33)], fill=main)              # snout
    d.polygon([(86, 34), (106, 33), (108, 36), (88, 38)], fill=col('#5a1018'))    # open mouth
    d.polygon([(84, 37), (104, 40), (100, 45), (84, 43)], fill=main)              # lower jaw
    dots(im, [(x, 33) for x in range(92, 108, 3)] + [(x, 38) for x in range(90, 104, 3)], fin)   # teeth
    dots(im, [(93, 34), (93, 35), (101, 37), (101, 36)], fin)                     # fangs
    d.line((78, 22, 90, 24), fill=dark)                     # brow
    d.rectangle((84, 25, 86, 27), fill=P['y'])
    dots(im, [(86, 26)], P['D'])
    dots(im, [(106, 26)], P['D'])
    d.line((106, 24, 110, 12), fill=k)                      # whiskers
    d.line((110, 12, 106, 6), fill=k)
    d.line((104, 30, 111, 40), fill=k)
    for x, y in ((90, 45), (92, 47), (88, 46), (90, 49)):   # beard
        dots(im, [(x, y)], belly)
    return outline(im, k)


ART['card-lovers'] = tomb(CW, CH)
ART['tomb'] = tomb(32, 22, people=False)                    # also copied into the game as the labyrinth's tomb wall
ART['shaw-epic'] = epic_dragon(col('#3f6fd0'), col('#27408f'), col('#9fc0f0'), col('#2a3f8a'), col('#4f74c8'))
ART['ran-epic'] = flip(epic_dragon(col('#c9402c'), col('#8c1f24'), col('#f0a070'), col('#8a2a22'), col('#d05a3a')))


# ── three more secrets: a bad play, a forced vacation, a fishing trip ──

def azula():
    D, a = P['D'], P['a']
    im, d = bust(P['T'], P['R'], a, hair=D, hair_box=(7, 3, 24, 18))
    d.rectangle((14, 1, 17, 4), fill=D)                    # topknot with the flame headpiece
    d.polygon([(13, 4), (14, 1), (15, 3), (16, 0), (17, 3), (18, 1), (18, 4)], fill=a)
    d.rectangle((8, 10, 9, 22), fill=D)                    # the two loose bangs
    d.rectangle((22, 10, 23, 22), fill=D)
    dots(im, [(11, 14), (20, 14)], D)
    dots(im, [(12, 14), (19, 14)], a)
    dots(im, [(10, 12), (11, 12), (12, 12), (13, 13), (21, 12), (20, 12), (19, 12), (18, 13)], D)
    dots(im, [(15, 16), (16, 16)], P['s'])
    dots(im, [(14, 20), (15, 20), (16, 20), (17, 19), (18, 18)], P['r'])   # the smirk
    return outline(im, P['k'])


def katara():
    N, D = P['N'], P['D']
    im, d = bust(P['S'], P['b'], P['w'], hair=N, hair_box=(7, 3, 24, 21))
    d.ellipse((9, 8, 22, 24), fill=P['S'])
    d.polygon([(9, 12), (12, 7), (19, 7), (22, 12), (19, 9), (12, 9)], fill=N)   # hair swept back from a middle parting
    dots(im, [(15, 8), (16, 8)], P['S'])
    for x, bead in ((9, 10), (22, 21)):                    # hair loopies, each with a blue bead
        dots(im, [(x, 12), (x, 13), (x, 14), (x, 15), (bead, 16)], N)
        dots(im, [(bead, 12), (bead, 13)], P['c'])
    dots(im, [(11, 15), (20, 15)], D)
    dots(im, [(12, 15), (19, 15)], P['b'])
    dots(im, [(11, 13), (12, 13), (19, 13), (20, 13)], N)
    dots(im, [(15, 17), (16, 17)], N)
    dots(im, [(14, 20), (15, 21), (16, 21), (17, 20)], D)
    d.line((12, 25, 19, 25), fill=P['B'])                  # her mother's necklace
    dots(im, [(15, 26), (16, 26)], P['c'])
    return outline(im, P['k'])


def loli():
    """Lo and Li, identical down to the last wrinkle."""
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    g, D = P['g'], P['D']
    for x in (0, 16):
        d.ellipse((x - 2, 24, x + 17, 42), fill=P['R'])    # shoulders
        d.polygon([(x + 5, 24), (x + 10, 24), (x + 8, 29), (x + 7, 29)], fill=P['a'])
        d.ellipse((x + 2, 6, x + 13, 18), fill=g)          # grey hair, pulled up into a bun
        d.ellipse((x + 5, 1, x + 10, 7), fill=g)
        d.line((x + 5, 6, x + 10, 6), fill=P['r'])
        d.ellipse((x + 3, 9, x + 12, 25), fill=P['T'])
        dots(im, [(x + 5, 15), (x + 6, 15), (x + 9, 15), (x + 10, 15)], D)
        dots(im, [(x + 4, 13), (x + 5, 13), (x + 10, 13), (x + 11, 13)], g)
        dots(im, [(x + 4, 18), (x + 11, 18), (x + 5, 21), (x + 10, 21)], P['s'])
        dots(im, [(x + 7, 17), (x + 8, 17), (x + 7, 18)], P['s'])
        d.line((x + 6, 21, x + 9, 21), fill=D)
    return outline(im, P['k'])


def actress_aang():
    """The Avatar as the Ember Island Players cast him: a woman in a bald cap."""
    D = P['D']
    im, d = bust(P['T'], P['o'], P['y'])
    d.rectangle((14, 7, 17, 11), fill=P['b'])
    d.polygon([(12, 11), (19, 11), (16, 15), (15, 15)], fill=P['b'])
    dots(im, [(9, 11), (10, 10), (11, 10), (20, 10), (21, 10), (22, 11)], P['s'])   # the edge of the cap
    dots(im, [(8, 17), (8, 18), (8, 19), (23, 17), (23, 18), (23, 19)], P['N'])     # and the hair it fails to hide
    dots(im, [(11, 14), (12, 14), (10, 13), (13, 13)], D)                           # lashes
    dots(im, [(19, 14), (20, 14), (21, 14), (18, 13), (22, 13)], D)                 # a wink
    disc(im, 11, 18, 1.6, P['m'])                                                   # far too much blush
    disc(im, 20, 18, 1.6, P['m'])
    dots(im, [(14, 20), (15, 20), (16, 20), (17, 20), (15, 21), (16, 21)], P['r'])
    return outline(im, P['k'])


def actor_toph():
    """Toph as the Ember Island Players cast her: a really buff guy."""
    D = P['D']
    im, d = bust(P['T'], P['e'], P['L'], hair=D, hair_box=(6, 2, 25, 17), face_box=(8, 7, 23, 22))
    d.polygon([(2, 31), (9, 22), (22, 22), (29, 31)], fill=P['e'])        # a neck like a tree trunk
    d.polygon([(11, 24), (20, 24), (16, 30), (15, 30)], fill=P['L'])
    d.rectangle((10, 19, 21, 25), fill=P['s'])
    d.rectangle((8, 13, 23, 22), fill=P['T'])                             # square jaw
    d.rectangle((10, 22, 21, 23), fill=P['T'])
    d.ellipse((11, 0, 20, 6), fill=D)                                     # her bun, his head
    d.rectangle((6, 8, 25, 9), fill=P['l'])                               # and her headband
    dots(im, [(6, 10), (6, 11), (25, 10), (25, 11)], P['L'])
    d.line((10, 12, 13, 12), fill=D)
    d.line((18, 12, 21, 12), fill=D)
    dots(im, [(11, 14), (12, 14), (19, 14), (20, 14)], D)
    dots(im, [(15, 16), (16, 16), (15, 17), (16, 17)], P['s'])
    d.rectangle((12, 19, 19, 20), fill=P['w'])                            # a grin with all its teeth
    d.line((12, 21, 19, 21), fill=D)
    dots(im, [(9, 20), (10, 22), (21, 22), (22, 20), (11, 23), (20, 23)], P['G'])   # stubble
    return outline(im, P['k'])


ART['fish'] = grid([
    '..........BB.......',
    'B......bbbbbbb.....',
    'BB...bbcccccccbb...',
    'BBB.bcccccccccwDb..',
    '.BBbccccccccccccbb.',
    'BBB.bccccccccccbb..',
    'BB...bbwwwwwwwb....',
    'B......bbbbbb......',
    '..........B........',
])

ART['spear'] = grid([
    '..w..',
    '.www.',
    '.wgw.',
    'wwgww',
    '.wgw.',
    '..n..',
    '.ana.',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..n..',
    '..N..',
    '..N..',
])

ART['pin-ember'] = grid([
    '....ee....ee......',
    '..eeeee.eeeee.....',
    '.ee..eeeee..ee....',
    '.e...eene....e.yy.',
    '....ee.n.e....yyyy',
    '....e..n......yyyy',
    '.......n.......yy.',
    '......nn..........',
    '......n.....ccc...',
    '..tttnntt.cccccc..',
    'ttTTTTTTTtttcccccc',
], edge='N')

# kuai ball players, seen across the net (so the left foot of each is on your right)
KUAI_GIRL = [
    '.....NNNN.....',
    '.NN.NNNNNN.NN.',
    'NNN.NTTTTN.NNN',
    'NN..TDTTDT..NN',
    '.N..TTTTTT..N.',
    '.....TssT.....',
    '......TT......',
    '...TTmmmmTT...',
    '..TT.mmmm.TT..',
    '..T..TTTT..T..',
    '..T..TTTT..T..',
    '..T..mmmm..T..',
    '.....mmmm.....',
    '.....TT.TT....',
    '.....TT.TT....',
    '.....TT.TT....',
    '.....TT.TT....',
    '....TTT.TTT...',
]
KUAI_KID = [
    '.....dddd.....',
    '....dddddd....',
    '....dTTTTd....',
    '....TDTTDT....',
    '....TTTTTT....',
    '.....TssT.....',
    '......TT......',
    '...TTTTTTTT...',
    '..TT.TTTT.TT..',
    '..T..TTTT..T..',
    '..T..TTTT..T..',
    '..T..rrrr..T..',
    '.....rrrr.....',
    '.....rr.rr....',
    '.....TT.TT....',
    '.....TT.TT....',
    '.....TT.TT....',
    '....TTT.TTT...',
]
ART['kuai-1'] = grid(KUAI_GIRL)
ART['kuai-2'] = grid(KUAI_KID)
ART['kuai-3'] = recolor(grid(KUAI_KID), {P['r']: P['a'], P['d']: P['N'], P['T']: P['s'], P['s']: P['S']})


def ball():
    im = new(11, 11)
    disc(im, 5, 5, 5.2, P['w'])
    d = ImageDraw.Draw(im)
    d.arc((-4, -1, 6, 11), 300, 60, fill=P['r'])
    d.arc((4, -1, 14, 11), 120, 240, fill=P['r'])
    dots(im, [(3, 9), (4, 10), (5, 10), (6, 10), (7, 9)], P['W'])
    return outline(im, P['k'])


def canoe():
    """Sokka and Katara out fishing: he has the spear, she has other ideas."""
    im = new(48, 28)
    d = ImageDraw.Draw(im)
    n, N, b, B, w, S = (P[c] for c in 'nNbBwS')
    d.line((36, 21, 44, 1), fill=P['t'])                   # the spear, raised and ready
    dots(im, [(44, 1), (45, 0), (44, 0), (45, 1), (43, 2)], w)
    for x, hair in ((13, 'braid'), (32, 'tail')):
        d.rectangle((x - 3, 12, x + 3, 21), fill=b)        # parka with a fur collar
        d.rectangle((x - 3, 12, x + 3, 13), fill=w)
        d.line((x - 3, 18, x + 3, 18), fill=B)
        disc(im, x, 8, 3.2, S)
        d.rectangle((x - 3, 4, x + 3, 6), fill=N)
        dots(im, [(x - 3, 7), (x + 3, 7)], N)
        dots(im, [(x + 1, 8)], P['D'])
        if hair == 'braid':
            dots(im, [(x - 4, 7), (x - 4, 8), (x - 5, 9), (x - 5, 10), (x - 5, 11)], N)
        else:
            dots(im, [(x - 2, 3), (x - 3, 2), (x - 3, 3)], N)
            d.line((x + 3, 15, x + 5, 19), fill=b)         # his arm on the spear
    d.polygon([(0, 17), (3, 17), (7, 21), (40, 21), (44, 17), (47, 17), (42, 27), (5, 27)], fill=n)   # hide canoe
    d.line((6, 23, 41, 23), fill=N)
    d.line((1, 18, 46, 18), fill=P['t'])
    for x in range(10, 40, 7):
        d.line((x, 21, x, 26), fill=N)
    return outline(im, P['k'])


for name, fn in (('azula', azula), ('katara', katara), ('loli', loli), ('actress-aang', actress_aang), ('actor-toph', actor_toph),
                 ('ball', ball), ('canoe', canoe)):
    ART[name] = fn()
ART['actor-zuko'] = flip(ART['zuko'])                       # the scar is on the wrong side


def stage_play():
    """The Ember Island Theater, set for the first scene: the icy South Pole seas.
    The game shows this in a low, wide box and crops the top and bottom to fit,
    so everything that matters sits in the middle rows."""
    im = new(SW, SH, col('#150c12'))
    d = ImageDraw.Draw(im)
    vgrad(im, 14, 64, [col(c) for c in ('#1f3f8c', '#3f7fb8', '#9fd0e6')], x0=20, x1=SW - 20)   # painted backdrop
    d.polygon([(120, 56), (128, 36), (135, 28), (144, 38), (150, 56)], fill=P['C'])            # a prop iceberg
    d.polygon([(135, 28), (144, 38), (150, 56), (139, 56)], fill=P['c'])
    for row, y in enumerate((50, 55, 60)):                                                     # rows of wooden waves
        for x in range(14 + row * 5, SW - 14, 12):
            d.ellipse((x, y, x + 12, y + 12), fill=col(('#2f6a9c', '#27588a', '#1f4878')[row]))
            d.arc((x, y, x + 12, y + 12), 200, 340, fill=P['C'])
    d.rectangle((0, 65, SW, SH), fill=col('#6a4326'))                                          # the boards
    d.line((0, 65, SW, 65), fill=col('#96683c'))
    for y in range(70, SH, 6):
        d.line((0, y, SW, y), fill=col('#4f2f1a'))
    for i, x in enumerate(range(6, SW, 22)):
        d.line((x + (i % 2) * 9, 66, x + (i % 2) * 9, SH), fill=col('#4f2f1a'))
    r, R, dark = P['r'], P['R'], col('#5a1218')
    for x in range(0, 24):                                                                     # curtains, drawn back
        c = (r, r, R, dark, R)[x % 5]
        d.line((x, 0, x, 68 - (x // 6)), fill=c)
        d.line((SW - 1 - x, 0, SW - 1 - x, 68 - (x // 6)), fill=c)
    d.rectangle((0, 0, SW, 20), fill=R)
    for x in range(-2, SW, 14):
        d.ellipse((x, 13, x + 14, 27), fill=r)
        d.arc((x, 13, x + 14, 27), 20, 160, fill=P['a'])
    d.rectangle((0, 0, SW, 16), fill=dark)
    for x in range(32, SW - 28, 16):                                                           # footlights
        d.rectangle((x, 76, x + 4, 78), fill=P['a'])
        dots(im, [(x + 1, 75), (x + 2, 74), (x + 3, 75), (x + 2, 75)], P['Y'])
    return im


def stage_beach():
    """A kuai ball court on Ember Island: a ring in the sand with a net across it."""
    im = new(SW, SH)
    vgrad(im, 0, 22, [col(c) for c in ('#4fa8e0', '#8fd3ee', '#d6f1fa')])
    d = ImageDraw.Draw(im)
    d.polygon([(110, 22), (128, 9), (133, 9), (150, 22)], fill=col('#7a8a9a'))                 # a volcano out at sea
    dots(im, [(129, 8), (131, 7), (132, 5), (130, 4)], P['W'])
    vgrad(im, 22, 34, [col(c) for c in ('#2f7fc9', '#3f9fd6', '#7fd0e6')])
    rnd = random.Random(31)
    for _ in range(26):
        x, y = rnd.randrange(SW - 6), rnd.randrange(23, 33)
        d.line((x, y, x + rnd.randrange(3, 8), y), fill=P['C'])
    d.line((0, 34, SW, 34), fill=P['w'])                                                       # surf
    vgrad(im, 35, SH, [col(c) for c in ('#f1d9a0', '#e8c986', '#d9b470')])
    for _ in range(90):
        dots(im, [(rnd.randrange(SW), rnd.randrange(36, SH))], col(rnd.choice(('#c9a260', '#f7e6b8'))))
    d.ellipse((10, 38, SW - 11, 118), outline=P['w'])                                          # the ring
    for x in (9, SW - 12):                                                                     # net posts
        d.rectangle((x, 52, x + 2, 72), fill=P['N'])
    for y in range(56, 66):                                                                    # the net
        for x in range(12, SW - 12):
            if y in (56, 65) or (x + y) % 3 == 0:
                im.putpixel((x, y), P['w'] if y in (56, 65) else P['W'])
    for x0, lean in ((2, 1), (SW - 4, -1)):                                                    # palms at the edges
        for y in range(8, 40):
            dots(im, [(x0 + lean * (40 - y) // 6, y), (x0 + lean * (40 - y) // 6 + 1, y)], P['N'])
        tx = x0 + lean * 5
        for a in range(0, 360, 45):
            ex, ey = tx + 10 * math.cos(math.radians(a)), 8 + 5 * math.sin(math.radians(a)) + 3
            d.line((tx, 8, ex, ey), fill=P['E'], width=2)
            d.line((tx, 7, ex, ey - 1), fill=P['e'])
    return im


def stage_fish():
    """The South Pole seas: a strip of sky, and a lot of very cold water."""
    im = new(SW, SH)
    vgrad(im, 0, 30, [col(c) for c in ('#9fd0e6', '#c9e6f2', '#eef6f8')])
    d = ImageDraw.Draw(im)
    ice, shade = col('#eef6f8'), col('#a9d2ea')
    for pts in ([(0, 30), (6, 12), (14, 6), (22, 14), (30, 30)], [(104, 30), (116, 10), (126, 3), (138, 12), (150, 30)],
                [(60, 30), (66, 20), (72, 17), (80, 30)], [(160, 30), (168, 16), (SW, 12), (SW, 30)]):   # icebergs
        d.polygon(pts, fill=ice)
        mid = pts[len(pts) // 2]
        d.polygon([mid] + pts[len(pts) // 2 + 1:] + [(mid[0] + 2, 30)], fill=shade)
    vgrad(im, 30, SH, [col(c) for c in ('#3f8fd6', '#2f6fb8', '#235a9c', '#16305a', '#0d1740')])
    d.line((0, 30, SW, 30), fill=P['C'])
    rnd = random.Random(33)
    for _ in range(34):                                                                        # light in the water
        x, y = rnd.randrange(SW - 8), rnd.randrange(33, 70)
        d.line((x, y, x + rnd.randrange(3, 9), y), fill=col('#5fa8e0') if y < 50 else col('#2f6fb8'))
    for x, w_ in ((38, 14), (86, 9), (146, 12)):                                               # loose floes
        d.rectangle((x, 28, x + w_, 31), fill=ice)
        d.line((x, 32, x + w_, 32), fill=shade)
    return im


ART['stage-play'] = stage_play()
ART['stage-beach'] = stage_beach()
ART['stage-fish'] = stage_fish()


def card_players():
    im = new(CW, CH, col('#150c12'))
    d = ImageDraw.Draw(im)
    d.polygon([(30, 0), (8, 44), (52, 44)], fill=col('#4a3a2a'))                               # a spotlight
    d.polygon([(30, 0), (16, 44), (44, 44)], fill=col('#8a7448'))
    d.rectangle((0, 42, CW, CH), fill=col('#6a4326'))
    d.line((0, 42, CW, 42), fill=col('#96683c'))
    for x in range(0, 11):
        c = (P['r'], P['r'], P['R'], col('#5a1218'), P['R'])[x % 5]
        d.line((x, 0, x, 45), fill=c)
        d.line((CW - 1 - x, 0, CW - 1 - x, 45), fill=c)
    d.rectangle((0, 0, CW, 4), fill=P['R'])
    for x in range(-2, CW, 10):
        d.ellipse((x, 0, x + 10, 8), fill=P['r'])
    put(im, ART['actress-aang'], 13, 10)
    return im


def card_beach():
    im, d = scene(('#4fa8e0', '#8fd3ee', '#d6f1fa'))
    vgrad(im, 18, 26, [col(c) for c in ('#2f7fc9', '#7fd0e6')])
    vgrad(im, 26, CH, [col(c) for c in ('#f1d9a0', '#d9b470')])
    d.line((0, 26, CW, 26), fill=P['w'])
    for x in (3, CW - 5):
        d.rectangle((x, 24, x + 1, 44), fill=P['N'])
    for y in range(28, 38):
        for x in range(5, CW - 5):
            if y in (28, 37) or (x + y) % 3 == 0:
                im.putpixel((x, y), P['w'] if y in (28, 37) else P['W'])
    for x in (8, 22, 36, 48):                                                                  # the net, on fire
        put(im, ART['el-fire'].crop((2, 0, 14, 16)), x, 22)
    for i in range(14, -1, -1):                                                                # and the ball that did it
        t = i / 14
        disc(im, 30 + 22 * t, 12 - 10 * t, 4.5 * (1 - t) + .6, P['Y'] if t < .25 else P['o'] if t < .6 else P['r'])
    put(im, ART['ball'], 23, 6)
    return im


def card_fish():
    im, d = scene(('#9fd0e6', '#c9e6f2', '#eef6f8'))
    d.polygon([(0, 30), (4, 14), (10, 9), (16, 30)], fill=col('#eef6f8'))
    d.polygon([(10, 9), (16, 30), (11, 30)], fill=col('#a9d2ea'))
    vgrad(im, 30, CH, [col(c) for c in ('#3f8fd6', '#235a9c', '#16305a')])
    d.line((0, 30, CW, 30), fill=P['C'])
    put(im, ART['canoe'], 1, 18)
    disc(im, 45, 12, 10.5, P['b'])                                                             # one fish, in a ball of water
    disc(im, 45, 12, 9.5, P['c'])
    disc(im, 42, 9, 5, P['C'], only=P['c'])
    put(im, ART['fish'].resize((16, 9), Image.NEAREST), 37, 8)
    dots(im, [(52, 24), (54, 27), (51, 28)], P['C'])                                           # dripping
    return im


ART['card-players'] = card_players()
ART['card-beach'] = card_beach()
ART['card-fish'] = card_fish()


# ── the Spirit Oasis, broken and mended: Zhao and Yue ───────────

def koi_alone(white):
    """Tui (white) or La (black) on its own. La keeps its place in the 28 x 28
    box, so it can stand in for the pair once Tui is gone; Tui is cropped."""
    im = new(28, 28)
    if white:
        koi_fish(im, 0, P['w'], P['D'])
        im = im.crop(im.getbbox())
    else:
        koi_fish(im, math.pi, P['D'], P['w'])
    return outline(im, P['B'])


def zhao():
    D, a = P['D'], P['a']
    im, d = bust(P['T'], col('#3a2a2e'), P['R'], hair=D, hair_box=(9, 3, 22, 11), face_box=(10, 6, 21, 24))
    d.rectangle((14, 1, 17, 4), fill=D)                    # topknot
    d.rectangle((14, 0, 17, 0), fill=a)                    # and its crown piece
    d.polygon([(9, 10), (10, 10), (11, 16), (12, 21), (9, 23), (6, 20), (7, 14)], fill=D)     # those sideburns,
    d.polygon([(22, 10), (21, 10), (20, 16), (19, 21), (22, 23), (25, 20), (24, 14)], fill=D) # flaring out to a point
    dots(im, [(7, 20), (8, 21), (24, 20), (23, 21)], P['d'])
    dots(im, [(11, 12), (12, 12), (13, 12), (14, 13), (20, 12), (19, 12), (18, 12), (17, 13)], D)   # heavy brows
    dots(im, [(12, 14), (13, 14), (18, 14), (19, 14)], D)
    dots(im, [(15, 16), (16, 16)], P['s'])
    dots(im, [(13, 20), (14, 20), (15, 20), (16, 20), (17, 19), (18, 18)], D)                       # the smirk
    for side in (1, -1):                                   # admiral's shoulder plates
        x0 = 0 if side == 1 else 31
        d.polygon([(x0, 28), (x0 + side * 6, 22), (x0 + side * 11, 27)], fill=P['R'])
        d.line((x0, 28, x0 + side * 6, 22), fill=a)
    return outline(im, P['k'])


def yue():
    w, D = P['w'], P['D']
    im, d = bust(P['S'], col('#5d6fc4'), w, hair=w, hair_box=(6, 4, 25, 22))
    d.rectangle((6, 13, 9, 31), fill=w)                    # long white hair, down past the shoulders
    d.rectangle((22, 13, 25, 31), fill=w)
    d.ellipse((9, 8, 22, 24), fill=P['S'])
    d.polygon([(9, 12), (12, 7), (19, 7), (22, 12), (19, 9), (12, 9)], fill=w)
    d.ellipse((12, 0, 19, 6), fill=w)                      # the knot on top, with its blue band
    d.line((12, 5, 19, 5), fill=P['b'])
    for x, bead in ((9, 10), (22, 21)):                    # hair loopies
        dots(im, [(x, 12), (x, 13), (x, 14), (x, 15), (bead, 16)], w)
        dots(im, [(bead, 12), (bead, 13)], P['c'])
    dots(im, [(11, 15), (20, 15)], D)
    dots(im, [(12, 15), (19, 15)], P['b'])
    dots(im, [(11, 13), (12, 13), (19, 13), (20, 13)], P['W'])
    dots(im, [(15, 17), (16, 17)], P['N'])
    dots(im, [(14, 20), (15, 21), (16, 21), (17, 20)], D)
    return outline(im, P['k'])


def red_moon():
    return recolor(ART['moon'], {P['w']: col('#ef6a5a'), P['W']: P['r'], P['g']: P['R'], col('#9fb4d8'): col('#5a1218')})


def card_zhao():
    im, d = scene(('#1c0406', '#4a0e12', '#8c1f24'))
    rnd = random.Random(11)
    for _ in range(16):
        dots(im, [(rnd.randrange(CW), rnd.randrange(26))], col('#ef6a5a'))
    put(im, red_moon(), 33, 2)
    d.rectangle((0, 38, CW, CH), fill=col('#3a0a0e'))                                          # the oasis, red
    d.ellipse((6, 39, 54, 52), fill=col('#5a1218'))
    d.arc((10, 41, 50, 51), 190, 350, fill=P['R'])
    D = P['D']
    d.polygon([(10, 44), (12, 27), (22, 27), (24, 44)], fill=D)                                # Zhao, from behind the light
    disc(im, 17, 22, 4.5, D)
    d.rectangle((15, 15, 18, 18), fill=D)                                                      # topknot
    d.polygon([(6, 30), (12, 24), (14, 28)], fill=D)                                           # shoulder plates
    d.polygon([(28, 30), (22, 24), (20, 28)], fill=D)
    d.line((22, 29, 27, 18), fill=D, width=2)                                                  # the arm, holding up the sack
    sack, tie = col('#8a7448'), col('#4a3a2a')
    d.ellipse((22, 7, 33, 19), fill=sack)
    d.polygon([(25, 8), (27, 3), (29, 3), (30, 8)], fill=sack)                                 # gathered at the neck
    d.line((25, 7, 30, 7), fill=tie)
    put(im, ART['tui'].resize((9, 9), Image.NEAREST), 29, 0)                                   # a white tail, sticking out
    return im


def card_yue():
    im, d = scene(('#070b24', '#152a66', '#2a4f94'))
    rnd = random.Random(12)
    for _ in range(18):
        dots(im, [(rnd.randrange(CW), rnd.randrange(30))], P['w'])
    px = im.load()
    for y in range(CH):                                                                        # moonlight, dithered
        for x in range(CW):
            dist = math.hypot(x - 15, y - 13)
            if dist < 18 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 18 + .15:
                px[x, y] = P['c']
    put(im, ART['moon'], 2, 0)
    d.rectangle((0, 43, CW, CH), fill=col('#16305a'))                                          # the pond, lit up
    d.line((0, 43, CW, 43), fill=P['C'])
    for y in range(44, CH, 2):
        d.line((24, y, 50, y), fill=col('#3f6fb0'))
    glow = col('#bfe6f5')
    d.polygon([(37, 18), (28, 44), (46, 44)], fill=glow)                                       # Yue, rising out of the light
    d.polygon([(37, 21), (31, 44), (43, 44)], fill=P['w'])
    d.rectangle((32, 13, 34, 30), fill=P['w'])                                                 # her long white hair
    d.rectangle((40, 13, 42, 30), fill=P['w'])
    disc(im, 37, 14, 4, P['w'])
    disc(im, 37, 15, 3, P['S'])
    d.rectangle((35, 8, 39, 10), fill=P['w'])                                                  # the knot on top
    d.line((35, 10, 39, 10), fill=P['b'])
    dots(im, [(36, 15), (38, 15)], P['D'])
    put(im, ART['koi'].resize((12, 12), Image.NEAREST), 6, 36)
    return im


# ── Lake Laogai: the room where Joo Dees are made ──────────────

def joodee():
    D = P['D']
    im, d = bust(P['T'], P['e'], P['l'], hair=D, hair_box=(7, 3, 24, 18))
    d.ellipse((11, 0, 20, 7), fill=D)                      # hair up in a bun, with a green band
    d.line((11, 5, 20, 5), fill=P['l'])
    d.ellipse((9, 8, 22, 24), fill=P['T'])
    d.polygon([(9, 12), (12, 7), (19, 7), (22, 12), (19, 9), (12, 9)], fill=D)
    dots(im, [(11, 15), (12, 14), (13, 15), (18, 15), (19, 14), (20, 15)], D)   # eyes shut, smiling
    dots(im, [(15, 17), (16, 17)], P['s'])
    d.line((12, 19, 19, 19), fill=D)                       # and the smile, as wide as it goes
    d.line((13, 20, 18, 20), fill=P['w'])
    dots(im, [(11, 18), (20, 18), (12, 20), (19, 20)], D)
    d.line((14, 21, 17, 21), fill=D)
    dots(im, [(10, 18), (21, 18)], P['m'])
    return outline(im, P['k'])


LANTERN = [
    '..k..',
    '.kAk.',
    'oyyyo',
    'oyYyo',
    'oyYyo',
    'oyyyo',
    '.oOo.',
    '..k..',
]

# the ring track the lantern runs on, in backdrop pixels (the game moves the lantern along the same ellipse)
RING = (88, 52, 44, 12)


def stage_laogai():
    im = new(SW, SH, col('#141c18'))
    d = ImageDraw.Draw(im)
    stone, seam = col('#26332c'), col('#1a241f')
    d.rectangle((0, 0, SW, 60), fill=stone)                 # the back wall, in blocks
    for y in range(0, 60, 8):
        d.line((0, y, SW, y), fill=seam)
        for x in range((y // 8 % 2) * 10, SW, 20):
            d.line((x, y, x, y + 8), fill=seam)
    vgrad(im, 60, SH, [col(c) for c in ('#2e3b33', '#222c26', '#161d19')])   # the floor
    px = im.load()
    for y in range(SH):                                     # one pool of light in the middle
        for x in range(SW):
            dist = math.hypot((x - 88) / 1.6, y - 50)
            if dist < 40 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 40 + .25:
                px[x, y] = col('#3d5244') if y < 60 else col('#465c4c')
    for x0 in (22, 140):                                    # Dai Li banners
        d.rectangle((x0, 6, x0 + 13, 40), fill=P['E'])
        d.polygon([(x0, 40), (x0 + 6, 46), (x0 + 13, 40)], fill=P['E'])
        d.rectangle((x0 + 2, 8, x0 + 11, 38), fill=P['e'])
        d.ellipse((x0 + 3, 16, x0 + 10, 23), fill=P['a'])
        d.ellipse((x0 + 5, 18, x0 + 8, 21), fill=P['E'])
    cx, cy, rx, ry = RING                                   # the ring track, on three posts
    for x in (cx - rx + 4, cx, cx + rx - 4):
        d.line((x, cy + 3, x, 70), fill=col('#3a3f44'))
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=col('#8a9096'))
    d.ellipse((cx - rx + 1, cy - ry + 1, cx + rx - 1, cy + ry - 1), outline=col('#4a5056'))
    return im


def card_laogai():
    im, d = scene(('#0e1a14', '#1e3326', '#2e4a38'))
    face = ART['joodee'].resize((22, 22), Image.NEAREST)
    for i, (x, y) in enumerate(((-3, -2), (17, -2), (37, -2), (7, 14), (27, 14), (47, 14), (-3, 30), (17, 30), (37, 30))):
        put(im, face, x, y)
    put(im, ART['lantern'], 54, 2)
    return im


ART['joodee'] = joodee()
ART['lantern'] = grid(LANTERN)
ART['stage-laogai'] = stage_laogai()
ART['card-laogai'] = card_laogai()

# ── Appa's dream: the Eastern Air Temple, the day they met ─────

def young_aang():
    """Aang as a small boy, before his arrows, one arm held out."""
    im = new(22, 34)
    d = ImageDraw.Draw(im)
    T, D = P['T'], P['D']
    d.ellipse((3, 0, 14, 11), fill=T)                      # head
    dots(im, [(6, 5), (11, 5), (6, 6), (11, 6)], D)
    dots(im, [(7, 8), (8, 9), (9, 9), (10, 8)], D)
    dots(im, [(5, 7), (12, 7)], P['m'])
    d.rectangle((4, 12, 13, 24), fill=P['y'])              # yellow shirt
    d.polygon([(4, 12), (8, 12), (6, 24), (4, 24)], fill=P['o'])   # orange sash over one shoulder
    d.rectangle((13, 14, 20, 16), fill=P['y'])             # the arm, held out
    d.rectangle((19, 14, 21, 16), fill=T)
    d.rectangle((5, 24, 12, 30), fill=P['o'])              # trousers and shoes
    d.rectangle((5, 31, 7, 33), fill=P['N'])
    d.rectangle((10, 31, 12, 33), fill=P['N'])
    return outline(im, P['k'])


APPLE = [
    '..e.',
    '.re.',
    'rYrr',
    'rrrR',
    '.RR.',
]


def sepia(im):
    """Old photo colours, the way the show draws a memory."""
    out = im.copy()
    px = out.load()
    ramp = [col(c) for c in ('#2a1d12', '#5a4128', '#8c6a44', '#bf9b6a', '#e8d2a6', '#fbf1d8')]
    for y in range(out.size[1]):
        for x in range(out.size[0]):
            r, g, b, a = px[x, y]
            lum = (r * .3 + g * .59 + b * .11) / 255
            px[x, y] = ramp[min(5, int(lum * 6))][:3] + (a,)
    return out


def stage_dream():
    im = new(SW, SH)
    vgrad(im, 0, 70, [col(c) for c in ('#7fbfea', '#b5dff3', '#e8f1e2')])
    put(im, ART['cloud'], 6, 10)
    put(im, ART['cloud'], 120, 22)
    ridge(im, 60, 10, col('#9fb0c0'), 31)
    d = ImageDraw.Draw(im)
    for x, top, w in ((126, 14, 7), (140, 6, 9), (156, 18, 7)):          # the temple's spires on their peaks
        d.polygon([(x - 14, 70), (x, top + 18), (x + 14, 70)], fill=col('#c9c0b0'))
        d.rectangle((x - w // 2, top + 6, x + w // 2, top + 22), fill=col('#efe6d0'))
        d.polygon([(x - w // 2 - 2, top + 7), (x, top), (x + w // 2 + 2, top + 7)], fill=col('#3f8fd6'))
        d.rectangle((x - 1, top + 12, x + 1, top + 15), fill=col('#5a4128'))
    vgrad(im, 70, SH, [col(c) for c in ('#d8cdb4', '#bfb196', '#a8987a')])   # the stone terrace
    d.line((0, 70, SW, 70), fill=col('#efe6d0'))
    for x in range(0, SW, 22):
        d.line((x, 71, x - 8, SH), fill=col('#a8987a'))
    return im


def card_friend():
    im, d = scene(('#4f7f9c', '#7f9fb0', '#9fb0b8'))
    ridge(im, 30, 6, col('#5f6f7c'), 4)
    d.rectangle((0, 38, CW, CH), fill=col('#8a7f6a'))
    put(im, ART['appa'].resize((34, 22), Image.NEAREST), 1, 18)        # a calf, sniffing
    put(im, ART['young-aang'], 36, 10)
    im = sepia(im)
    put(im, ART['apple'], 54, 9)                                        # the one thing in the memory with its colour
    return im


ART['young-aang'] = young_aang()
ART['apple'] = grid(APPLE)
ART['stage-dream'] = sepia(stage_dream())
ART['card-friend'] = card_friend()

# ── the Serpent's Pass: the other way into Ba Sing Se ──────────

SERPENT = (col('#2f9f8f'), col('#1d6b60'), col('#d6e8a8'), col('#b8324a'))   # body, shadow, belly, fins


def serpent():
    """Rearing up out of the water, facing right."""
    body, dark, belly, fin = SERPENT
    im = new(50, 76)
    d = ImageDraw.Draw(im)
    path = spline([(21, 75), (31, 61), (15, 45), (25, 30), (29, 20)], 30)
    n = len(path)
    for i, (x, y) in enumerate(path):                      # from the water up, so the neck ends on top
        t = i / (n - 1)
        r = 7 - 2.6 * t
        if i % 11 == 5:                                    # fins down its back
            d.polygon([(x - r + 1, y - 2), (x - r - 5, y - 1), (x - r + 1, y + 3)], fill=fin)
        disc(im, x, y, r, body)
        disc(im, x + r * .5, y, r * .42, belly)
        if i % 3 == 0:
            dots(im, [(int(x - r * .3), int(y))], dark)    # scales
    d.ellipse((21, 8, 39, 23), fill=body)                  # head
    d.polygon([(36, 13), (48, 15), (47, 19), (36, 22)], fill=body)   # snout
    d.polygon([(37, 18), (48, 18), (40, 22)], fill=P['m'])           # and an open mouth
    d.line((37, 18, 48, 18), fill=dark)
    dots(im, [(42, 18), (45, 18)], P['w'])                 # teeth
    d.polygon([(22, 12), (14, 3), (27, 8)], fill=fin)      # the crest
    d.polygon([(27, 8), (25, 0), (33, 7)], fill=fin)
    d.polygon([(23, 18), (15, 22), (24, 21)], fill=fin)
    d.rectangle((31, 12, 33, 14), fill=P['Y'])             # eye
    dots(im, [(33, 13)], P['D'])
    return outline(im, P['k'])


def unagi():
    """The Unagi of Kyoshi Island: an eel the size of a ship, with whiskers to hang on to."""
    body, dark, belly = col('#4f6e5a'), col('#2f4a3a'), col('#c9d6a8')
    im = new(56, 76)
    d = ImageDraw.Draw(im)
    path = spline([(20, 75), (28, 60), (18, 44), (24, 30), (27, 22)], 30)
    n = len(path)
    for i, (x, y) in enumerate(path):
        t = i / (n - 1)
        r = 7.5 - 2 * t
        if i % 9 == 4:                                     # a ragged fin along its back
            d.polygon([(x - r + 1, y - 3), (x - r - 4, y), (x - r + 1, y + 3)], fill=dark)
        disc(im, x, y, r, body)
        disc(im, x + r * .5, y, r * .4, belly)
    d.ellipse((17, 10, 37, 26), fill=body)                 # a broad, flat head
    d.polygon([(34, 14), (46, 17), (46, 22), (34, 24)], fill=body)
    d.line((35, 21, 46, 21), fill=dark)                    # mouth
    d.rectangle((28, 14, 30, 16), fill=P['Y'])             # eye
    dots(im, [(30, 15)], P['D'])
    for (x0, y0), pts in (((44, 18), [(48, 14), (52, 12), (55, 15)]), ((44, 22), [(49, 26), (52, 31), (55, 30)])):
        d.line([(x0, y0)] + pts, fill=col('#a8b890'))      # its whiskers
    return outline(im, P['k'])


WALKER = [
    '..TT..',
    '..TT..',
    '.nnnNN',
    'nnnnNN',
    '.nnnNN',
    '.nnn..',
    '.nnn..',
    '.n.n..',
    '.N.N..',
]


def stage_serpent():
    im = new(SW, SH)
    vgrad(im, 0, 40, [col(c) for c in ('#5f8fc0', '#8fb8dc', '#c8dcea')])
    ridge(im, 30, 8, col('#7f93a8'), 12)                  # far mountains
    vgrad(im, 38, 54, [col(c) for c in ('#4f86b8', '#3f76a8')])   # the far lake
    d = ImageDraw.Draw(im)
    rock, rock_hi, rock_lo = col('#8a7f6a'), col('#b5a888'), col('#5f5646')
    d.polygon([(132, 96), (140, 30), (152, 12), (166, 6), (176, 4), (176, 96)], fill=rock_lo)   # the mountainside
    d.polygon([(140, 30), (152, 12), (166, 6), (160, 40), (150, 60)], fill=rock)
    vgrad(im, 58, SH, [col(c) for c in ('#2f6aa0', '#24578a', '#1a4470', '#123358')], 0, 140)  # the near lake
    for x0 in range(4, 136, 18):                           # ripples
        d.line((x0, 70 + x0 % 7, x0 + 7, 70 + x0 % 7), fill=col('#5f9fd0'))
        d.line((x0 + 9, 84 + x0 % 5, x0 + 15, 84 + x0 % 5), fill=col('#4f8fc0'))
    d.rectangle((0, 52, 146, 58), fill=rock)               # the pass itself: a sliver of rock between them
    d.line((0, 52, 146, 52), fill=rock_hi)
    d.line((0, 58, 146, 58), fill=rock_lo)
    for x in range(6, 140, 11):
        dots(im, [(x, 55), (x + 4, 56)], rock_lo)
    d.rectangle((9, 38, 10, 52), fill=P['N'])              # and the sign at the start of it
    d.rectangle((3, 36, 17, 43), fill=P['n'])
    d.line((5, 39, 15, 39), fill=P['N'])
    d.line((5, 41, 12, 41), fill=P['N'])
    return im


def card_serpent():
    im, d = scene(('#8fb8dc', '#c8dcea', '#c8dcea'))
    vgrad(im, 30, CH, [col(c) for c in ('#2f6aa0', '#1a4470')])
    d.rectangle((0, 33, CW, 36), fill=col('#8a7f6a'))
    d.line((0, 33, CW, 33), fill=col('#b5a888'))
    put(im, ART['serpent'].resize((38, 58), Image.NEAREST), 12, -4)
    for x in (4, 50, 55):
        put(im, ART['walker'], x, 24)
    return im


ART['serpent'] = serpent()
ART['unagi'] = unagi()
ART['walker'] = grid(WALKER)
ART['stage-serpent'] = stage_serpent()
ART['card-serpent'] = card_serpent()

# ── Zuko, practising his speech for the gang ───────────────────

BADGERFROG = [                                              # a frog, with a badger's stripe down its head
    '.ee.....ee.',
    'eYDe...eYDe',
    'eeeDDwDDeee',
    'eeeeDwDeeee',
    'lllllllllll',
    '.lE.....El.',
]


def card_zuko():
    """The Western Air Temple hangs upside down under its cliff; Zuko rehearses on the grass above."""
    im, d = scene(('#7fbfea', '#b5dff3', '#e8f1e2'))
    d.rectangle((0, 30, CW, CH), fill=col('#6e6a68'))                                        # the cliff, and the drop below it
    d.rectangle((0, 28, CW, 31), fill=P['e'])
    for x, top, w in ((40, 32, 6), (50, 32, 8)):                                              # spires, hanging down
        d.rectangle((x - w // 2, top, x + w // 2, top + 9), fill=col('#efe6d0'))
        d.polygon([(x - w // 2 - 1, top + 9), (x, top + 16), (x + w // 2 + 1, top + 9)], fill=col('#c9362c'))
    put(im, ART['zuko'], 0, 14)
    put(im, ART['badgerfrog'], 28, 20)
    return im


ART['badgerfrog'] = grid(BADGERFROG)
ART['card-zuko'] = card_zuko()

# ── the secret dance party, in a cave ───────────────────────────

DANCER = [                                                  # a Fire Nation schoolkid, in uniform
    '.....DDDD.....',
    '....DDDDDD....',
    '....DTTTTD....',
    '....TDTTDT....',
    '....TTTTTT....',
    '.....TssT.....',
    '......TT......',
    '...rrrrrrrr...',
    '..rr.rRRr.rr..',
    '..T..rRRr..T..',
    '.....rrrr.....',
    '.....DDDD.....',
    '.....DD.DD....',
    '.....DD.DD....',
    '.....DD.DD....',
    '....NNN.NNN...',
]
DANCER_GIRL = [
    '.....DDDD.....',
    '...DDDDDDDD...',
    '...DDTTTTDD...',
    '...DTDTTDTD...',
    '...DTTTTTTD...',
    '...D.TssT.D...',
    '...D..TT..D...',
    '...rrrrrrrr...',
    '..rr.rRRr.rr..',
    '..T..rRRr..T..',
    '.....rrrr.....',
    '....rrrrrr....',
    '...rrrrrrrr...',
    '.....TT.TT....',
    '.....TT.TT....',
    '....NNN.NNN...',
]
AANG_DANCER = [                                             # Kuzon, from the colonies, headband on
    '.....TTTT.....',
    '....TTTTTT....',
    '....RRRRRR....',
    '....TDTTDT....',
    '....TTTTTT....',
    '.....TssT.....',
    '......TT......',
    '...rrrrrrrr...',
    '..rr.raar.rr..',
    '..T..raar..T..',
    '.....rrrr.....',
    '.....DDDD.....',
    '.....DD.DD....',
    '.....DD.DD....',
    '.....DD.DD....',
    '....NNN.NNN...',
]
KATARA_DANCER = [
    '.....NNNN.....',
    '...NNNNNNNN...',
    '..NNNSSSSNNN..',
    '..cNSDSSDSNc..',
    '..NNSSSSSSNN..',
    '..N..SNNS..N..',
    '..N...SS...N..',
    '...rrrrrrrr...',
    '..rr.RrrR.rr..',
    '..S..rrrr..S..',
    '.....RRRR.....',
    '....rrrrrr....',
    '...rrrrrrrr...',
    '.....SS.SS....',
    '.....SS.SS....',
    '....NNN.NNN...',
]


def teacher():
    D = P['D']
    im, d = bust(P['T'], P['R'], P['a'], hair=D, hair_box=(9, 4, 22, 12))
    d.rectangle((14, 1, 17, 5), fill=D)                    # topknot
    dots(im, [(11, 14), (12, 14), (19, 14), (20, 14)], D)  # stern little eyes
    dots(im, [(10, 12), (11, 12), (12, 12), (19, 12), (20, 12), (21, 12)], P['G'])
    dots(im, [(15, 16), (16, 16)], P['s'])
    d.line((12, 19, 14, 18), fill=D)                       # a thin, disapproving moustache
    d.line((17, 18, 19, 19), fill=D)
    d.line((14, 21, 17, 21), fill=D)
    return outline(im, P['k'])


def stage_dance():
    im = new(SW, SH, col('#1c120c'))
    d = ImageDraw.Draw(im)
    d.ellipse((-30, -40, SW + 30, 88), fill=col('#2e2016'))   # the cave
    d.ellipse((10, -20, SW - 10, 80), fill=col('#3a2a1c'))
    vgrad(im, 70, SH, [col(c) for c in ('#4a3826', '#3a2a1c', '#2a1e14')])   # the dance floor
    d.rectangle((52, 34, 124, 52), fill=col('#6e5a40'))      # the stage Toph raised
    d.rectangle((52, 34, 124, 35), fill=col('#96805a'))
    d.rectangle((52, 52, 124, 54), fill=col('#4a3a2a'))
    for x in (66, 84, 102):                                   # the band, the Flamey-O's
        d.rectangle((x, 22, x + 5, 33), fill=col('#1a1420'))
        disc(im, x + 2.5, 19, 3, col('#1a1420'))
        d.line((x + 5, 26, x + 9, 24), fill=P['a'])
    px = im.load()
    for cx, cy in ((14, 40), (32, 30), (144, 30), (162, 40), (24, 58), (152, 58)):   # candles along the walls
        for y in range(cy - 7, cy + 4):
            for x in range(cx - 7, cx + 8):
                dist = math.hypot(x - cx, (y - cy) * 1.3)
                if 0 <= x < SW and dist < 7 and (BAYER[y % 4][x % 4] + .5) / 16 > dist / 7 + .2:
                    px[x, y] = col('#7a5a30')
        d.rectangle((cx - 1, cy, cx + 1, cy + 4), fill=P['w'])
        dots(im, [(cx, cy - 1), (cx, cy - 2)], P['y'])
        dots(im, [(cx, cy - 1)], P['Y'])
    return im


def card_dance():
    im = new(CW, CH, col('#2e2016'))
    d = ImageDraw.Draw(im)
    for r, c in ((26, '#4a3826'), (18, '#6e5030'), (10, '#8a6a3a')):     # candlelight in the middle
        disc(im, 30, 30, r, col(c))
    put(im, ART['aang-dancer'].resize((24, 30), Image.NEAREST), 7, 16)
    put(im, flip(ART['katara-dancer']).resize((24, 30), Image.NEAREST), 29, 16)
    for x, y in ((4, 6), (50, 4), (28, 2)):                  # music notes
        d.rectangle((x + 2, y, x + 3, y + 6), fill=P['y'])
        d.rectangle((x, y + 5, x + 2, y + 7), fill=P['y'])
        d.rectangle((x + 3, y, x + 5, y + 1), fill=P['y'])
    return im


ART['dancer-1'] = grid(DANCER)
ART['dancer-2'] = grid(DANCER_GIRL)
ART['dancer-3'] = recolor(grid(DANCER), {P['D']: P['N'], P['r']: P['o'], P['R']: P['O'], P['T']: P['s'], P['s']: P['S']})
ART['dancer-4'] = recolor(grid(DANCER_GIRL), {P['D']: P['d'], P['r']: P['R'], P['R']: P['r'], P['T']: P['s'], P['s']: P['S']})
ART['aang-dancer'] = grid(AANG_DANCER)
ART['katara-dancer'] = grid(KATARA_DANCER)
ART['teacher'] = teacher()
ART['stage-dance'] = stage_dance()
ART['card-dance'] = card_dance()

# ── the banyan-grove tree, seen from far enough away ───────────

def card_banyan():
    im, d = scene(('#7fbfea', '#b5dff3', '#d6e8c0'))
    vgrad(im, 30, CH, [col(c) for c in ('#5a8a55', '#3b6a43', '#24452f')])   # the swamp, out to the horizon
    for x0 in range(-4, CW, 9):                                              # its roots, glowing, all one tree
        d.line((30, 31, x0, CH), fill=col('#86efac'))
    d.polygon([(26, 31), (34, 31), (33, 18), (27, 18)], fill=col('#3b2a1c'))  # trunk
    d.ellipse((4, 8, 56, 22), fill=col('#3b6a43'))                           # one wide canopy
    d.ellipse((8, 6, 52, 18), fill=col('#4e9c45'))
    d.ellipse((16, 5, 44, 13), fill=col('#93cf56'))
    rnd = random.Random(15)
    for x in range(7, 54, 3):                                                # roots hanging from the branches
        d.line((x, 18, x, 18 + rnd.randrange(4, 12)), fill=col('#3b2a1c'))
    return im


ART['card-banyan'] = card_banyan()

# ── Wan Shi Tong's book of creatures: four loose pages ─────────

PAPER, PAPER_DARK = col('#f1e4c4'), col('#c9b088')
INK, INK_MID = col('#3a2a1c'), col('#7a5a3a')

PAGE = [                                                    # a loose page, one corner folded
    'WWWWWWWWg.',
    'WwwwwwwWgg',
    'WwDDDDwwwW',
    'WwwwwwwwwW',
    'WwDDDDDDwW',
    'WwwwwwwwwW',
    'WwDDDDDwwW',
    'WwwwwwwwwW',
    'WwDDDDDDwW',
    'WwwwwwwwwW',
    'WWWWWWWWWW',
]


def ink(img, light=True):
    """A sprite redrawn as an ink sketch: dark lines, mid shading, and paper for the light parts."""
    out = img.copy()
    px = out.load()
    for y in range(out.size[1]):
        for x in range(out.size[0]):
            r, g, b, a = px[x, y]
            if not a:
                continue
            lum = (r * .3 + g * .59 + b * .11) / 255
            px[x, y] = INK if lum < .38 else INK_MID if lum < .68 else (PAPER if light else CLEAR)
    return out


def paper(w=CW, h=CH):
    """A page of field notes: paper, a darker edge, and a few lines of handwriting."""
    im = new(w, h, PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=PAPER_DARK)
    rnd = random.Random(w * 7 + h)
    for y in range(h - 9, h - 2, 3):                       # notes along the bottom
        x = 3
        while x < w - 6:
            ln = rnd.randrange(2, 7)
            d.line((x, y, min(w - 4, x + ln), y), fill=INK_MID)
            x += ln + 2
    return im, d


def paisho_table():
    """An old man in the shade of an awning, at a Pai Sho table, waiting for a game."""
    im = new(46, 40)
    d = ImageDraw.Draw(im)
    for x in (3, 42):                                       # the awning and its poles
        d.rectangle((x, 6, x, 34), fill=P['N'])
    for i in range(8):
        d.rectangle((1 + i * 6, 2, 6 + i * 6, 7), fill=P['r'] if i % 2 else P['w'])
    d.ellipse((15, 8, 30, 22), fill=P['T'])                 # the old man
    d.ellipse((16, 6, 29, 10), fill=P['g'])                 # what is left of his hair
    d.polygon([(17, 18), (28, 18), (26, 26), (19, 26)], fill=P['g'])   # and a long beard
    dots(im, [(19, 14), (20, 14), (25, 14), (26, 14)], P['D'])
    dots(im, [(18, 12), (19, 12), (26, 12), (27, 12)], P['g'])
    dots(im, [(22, 16), (23, 16)], P['s'])
    d.polygon([(11, 22), (34, 22), (37, 34), (8, 34)], fill=P['n'])   # robe
    d.rectangle((6, 28, 40, 31), fill=P['N'])               # the table
    d.rectangle((10, 32, 12, 38), fill=P['N'])
    d.rectangle((34, 32, 36, 38), fill=P['N'])
    d.ellipse((13, 25, 33, 30), fill=P['t'])                # and the board on it
    d.line((23, 25, 23, 30), fill=P['n'])
    d.line((13, 27, 33, 27), fill=P['n'])
    dots(im, [(17, 28), (28, 26), (21, 26), (26, 29)], P['w'])
    return outline(im, P['k'])


def paisho_lotus():
    """The board from above, the tiles laid out as a lotus flower."""
    im = new(32, 32)
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, 31, 31), fill=P['t'])
    d.ellipse((2, 2, 29, 29), outline=P['n'])
    for i in range(0, 32, 4):                               # the grid
        d.line((i, 0, i, 31), fill=P['T'])
        d.line((0, i, 31, i), fill=P['T'])
    d.ellipse((0, 0, 31, 31), outline=P['N'])
    for k in range(8):                                      # eight petals of tiles around the white lotus in the middle
        a = k * math.pi / 4
        for r in (6, 10):
            disc(im, 15.5 + r * math.cos(a), 15.5 + r * math.sin(a), 1.6, P['m'] if r == 10 else P['w'])
    disc(im, 15.5, 15.5, 2.6, P['w'])
    disc(im, 15.5, 15.5, 1.2, P['y'])
    out = im.copy()                                         # keep it round
    px, src = out.load(), im.load()
    for y in range(32):
        for x in range(32):
            if (x - 15.5) ** 2 + (y - 15.5) ** 2 > 16.2 ** 2:
                px[x, y] = CLEAR
    return outline(out, P['k'])


HAWK = [                                                    # a messenger hawk, with the message strapped to its back
    '..DD.........',
    '.DDDD....DD..',
    'DDDDDDDDDDDD.',
    '.DDDrDDDDDDDY',
    '..DDDDwwDD...',
    '....DD.......',
]

RAVEN_EAGLE = [                                             # brown, with a white crest and red streaks on its head
    '......wwrw......',
    '.....wwwrrwY....',
    'NN..nwwwwwwYY...',
    'NNNnnnwwwr......',
    '.NNnnnnnn.......',
    '..NNnnnnnnn.....',
    '...NNNnnnnnn....',
    '....NN..nnnnn...',
    '.......Y..YN....',
]


def isle():
    im = new(24, 14)
    d = ImageDraw.Draw(im)
    d.ellipse((0, 7, 23, 13), fill=P['t'])
    d.ellipse((3, 5, 20, 11), fill=P['e'])
    for x, h in ((7, 1), (14, 0)):                          # two trees
        d.rectangle((x, h + 3, x + 1, 8), fill=P['N'])
        d.ellipse((x - 3, h, x + 4, h + 4), fill=P['E'])
    return outline(im, P['B'])


def lion_turtle():
    """The same island, with an enormous head lifted out of the sea in front of it."""
    im = new(36, 22)
    put(im, isle(), 0, 7)
    d = ImageDraw.Draw(im)
    mane, face = col('#6e5a40'), col('#c4aa78')
    d.ellipse((21, 3, 35, 17), fill=mane)                   # a shaggy mane
    for a in range(0, 360, 40):
        x, y = 28 + 7.5 * math.cos(math.radians(a)), 10 + 7.5 * math.sin(math.radians(a))
        d.polygon([(x, y), (28 + 9.5 * math.cos(math.radians(a + 20)), 10 + 9.5 * math.sin(math.radians(a + 20))), (28 + 6 * math.cos(math.radians(a + 30)), 10 + 6 * math.sin(math.radians(a + 30)))], fill=mane)
    d.ellipse((24, 6, 33, 15), fill=face)                   # the face
    d.polygon([(26, 13), (31, 13), (28, 19)], fill=mane)    # its beard
    dots(im, [(26, 9), (31, 9)], P['D'])
    d.rectangle((28, 10, 29, 12), fill=col('#8a7355'))      # a broad nose
    d.line((24, 1, 26, 5), fill=P['W'])                     # and horns
    d.line((33, 1, 31, 5), fill=P['W'])
    return outline(im, P['B'])


def notes_book():
    im = new(CW, CH, col('#5b3920'))
    d = ImageDraw.Draw(im)
    d.rectangle((2, 4, 57, 47), fill=col('#3b2a1c'))        # the cover, open
    for x0 in (4, 31):                                      # two blank pages
        d.rectangle((x0, 6, x0 + 24, 45), fill=PAPER)
        d.line((x0, 6, x0, 45), fill=PAPER_DARK)
    d.line((30, 5, 30, 46), fill=col('#2a1d12'))
    return im


# Where each page's sketch goes in the open book: two on each side. Each sketch
# is also drawn on a layer of its own, the size of the card, so the game can lay
# the ones found so far over the empty book.
NOTES_SPOTS = {'eagle': (14, 10), 'lotus': (6, 28), 'unagi': (34, 10), 'dragons': (42, 28)}

def notes_sketch(name):
    im = new(CW, CH)
    put(im, ART['card-page-' + name].resize((12, 10), Image.NEAREST), *NOTES_SPOTS[name])
    return im


def card_notes():
    im = ART['notes-book'].copy()
    for name in NOTES_SPOTS:
        put(im, ART['notes-page-' + name], 0, 0)
    return im


def page_lotus():
    im, d = paper()
    d.ellipse((17, 5, 43, 31), outline=INK)                 # the tile
    d.ellipse((19, 7, 41, 29), outline=INK_MID)
    for k in range(8):                                      # its lotus
        a = k * math.pi / 4
        d.line((30, 18, 30 + 9 * math.cos(a), 18 + 9 * math.sin(a)), fill=INK)
        disc(im, 30 + 7 * math.cos(a), 18 + 7 * math.sin(a), 1.8, INK_MID)
    disc(im, 30, 18, 2.5, PAPER)
    d.ellipse((27, 15, 33, 21), outline=INK)
    return im


def page_dragons():
    im, d = paper()
    put(im, ink(ART['ran']).resize((30, 27), Image.NEAREST), -2, 3)
    put(im, ink(ART['shaw']).resize((30, 27), Image.NEAREST), 32, 3)
    return im


def page_eagle():
    im, d = paper()
    put(im, ink(ART['raven-eagle']).resize((40, 22), Image.NEAREST), 10, 8)
    return im


def page_unagi():
    im, d = paper()
    put(im, ink(ART['unagi']).resize((26, 36), Image.NEAREST), 17, 0)
    d.line((4, 33, 56, 33), fill=INK_MID)                   # the waterline
    for x in (8, 46, 52):
        d.line((x, 35, x + 3, 35), fill=INK_MID)
    return im


ART['page'] = grid(PAGE)
ART['paisho-table'] = paisho_table()
ART['paisho-lotus'] = paisho_lotus()
ART['hawk'] = grid(HAWK)
ART['raven-eagle'] = grid(RAVEN_EAGLE)
ART['isle'] = isle()
ART['lion-turtle'] = lion_turtle()
for name, fn in (('lotus', page_lotus), ('dragons', page_dragons), ('eagle', page_eagle), ('unagi', page_unagi)):
    ART['card-page-' + name] = fn()
ART['notes-book'] = notes_book()
for name in NOTES_SPOTS:
    ART['notes-page-' + name] = notes_sketch(name)
ART['card-notes'] = card_notes()

ART['tui'] = koi_alone(True)
ART['koi-la'] = koi_alone(False)
ART['zhao'] = zhao()
ART['yue'] = yue()
ART['card-zhao'] = card_zhao()
ART['card-yue'] = card_yue()


# ── write everything out ────────────────────────────────────────

def main():
    os.makedirs(OUT, exist_ok=True)
    for name, img in ART.items():
        img.save(os.path.join(OUT, name + '.png'))
    print(f'wrote {len(ART)} images to {OUT}')
    if len(sys.argv) > 1:                                   # overview sheet for checking the art
        scale, gap, width = 4, 8, 1500
        x = y = gap
        row_h = 0
        placed = []
        for name, img in ART.items():
            big = img.resize((img.size[0] * scale, img.size[1] * scale), Image.NEAREST)
            if x + big.size[0] + gap > width:
                x, y, row_h = gap, y + row_h + gap, 0
            placed.append((big, x, y))
            x += big.size[0] + gap
            row_h = max(row_h, big.size[1])
        sheet = Image.new('RGBA', (width, y + row_h + gap), col('#4a5568'))
        for big, bx, by in placed:
            sheet.alpha_composite(big, (bx, by))
        sheet.save(sys.argv[1])
        print('sheet:', sys.argv[1])


if __name__ == '__main__':
    main()
