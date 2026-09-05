"""Regenerate scripts/shirts_data.json from the source art in docs/shirts/.

The art is AI-generated on a solid #f1f1ec ground, which reads as a bright slab
on a dark card. Naively keying it out leaves a pale fringe: the 1-2px edge
pixels are a blend of outline and ground, so making them semi-transparent while
keeping their washed-out colour halos every outline. Instead, for each edge
pixel recover the foreground colour F from the neighbouring solid artwork and
take alpha from coverage, |P-B| / |F-B|. Also drops stranded specks - chiefly
the generator's sparkle watermark in the corner of the 500.
"""
import json, base64, io
from collections import deque
from PIL import Image

T_BG   = 100   # ground, plus the soft drop shadow painted on it (outlines sit at ~320)
RINGS  = 3     # edge-blend bands to un-matte outward from the ground

def dist(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

def ground_colour(px, w, h):
    border = [px[x, y] for x in range(w) for y in (0, h-1)] + \
             [px[x, y] for y in range(h) for x in (0, w-1)]
    opaque = [p for p in border if p[3] > 200]
    if not opaque:
        return (241, 241, 236)
    return tuple(sorted(c[i] for c in opaque)[len(opaque)//2] for i in range(3))

def flood_ground(px, w, h, bg):
    """Pixels reachable from the border that are still the flat ground."""
    is_bg = bytearray(w*h)
    q = deque([(x, y) for x in range(w) for y in (0, h-1)] +
              [(x, y) for y in range(h) for x in (0, w-1)])
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or is_bg[y*w+x]:
            continue
        p = px[x, y]
        if p[3] > 0 and dist(p, bg) > T_BG:
            continue
        is_bg[y*w+x] = 1
        q.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
    return is_bg

def neighbours(x, y, w, h, r=2):
    for ny in range(max(0, y-r), min(h, y+r+1)):
        for nx in range(max(0, x-r), min(w, x+r+1)):
            if nx != x or ny != y:
                yield nx, ny

def fill_holes(px, w, h, bg, is_bg):
    """The numerals are punched out of the art as transparency - on the cream
    ground they read as cream numbers, but once the ground goes they turn into
    see-through holes (dark numbers on a dark card). Composite every enclosed
    non-opaque pixel back over the ground colour so the glyphs keep the look
    they had, whatever is behind the shirt."""
    filled = 0
    for y in range(h):
        for x in range(w):
            if is_bg[y*w+x]:
                continue
            r, g, b, a = px[x, y]
            if a == 255:
                continue
            f = a / 255.0
            px[x, y] = (round(r*f + bg[0]*(1-f)),
                        round(g*f + bg[1]*(1-f)),
                        round(b*f + bg[2]*(1-f)), 255)
            filled += 1
    return filled

def unmatte(px, w, h, bg, is_bg):
    """Rebuild the antialiased edge with true colours and coverage alpha."""
    solid = bytearray(1 if not is_bg[i] else 0 for i in range(w*h))
    for _ring in range(RINGS):
        band = [(x, y) for y in range(h) for x in range(w)
                if solid[y*w+x] and any(is_bg[ny*w+nx] or not solid[ny*w+nx]
                                        for nx, ny in neighbours(x, y, w, h, 1))]
        updates = {}
        for x, y in band:
            refs = [px[nx, ny] for nx, ny in neighbours(x, y, w, h, 2)
                    if solid[ny*w+nx] and (nx, ny) not in set()]
            refs = [p for p in refs if dist(p, bg) > 120]      # genuinely artwork
            if not refs:
                continue
            F = tuple(sum(p[i] for p in refs)//len(refs) for i in range(3))
            denom = dist(F, bg)
            if denom < 40:
                continue
            a = min(1.0, dist(px[x, y], bg) / denom)
            if a >= 0.97:
                continue
            updates[(x, y)] = (F[0], F[1], F[2], int(round(px[x, y][3] * a)))
        for (x, y), v in updates.items():
            px[x, y] = v
            if v[3] < 8:
                solid[y*w+x] = 0
    for i in range(w*h):
        if is_bg[i]:
            px[i % w, i // w] = (0, 0, 0, 0)

def components(px, w, h, thresh=8):
    lab = bytearray(w*h)
    out = []
    for sy in range(h):
        for sx in range(w):
            if lab[sy*w+sx] or px[sx, sy][3] <= thresh:
                continue
            blob, q = [], deque([(sx, sy)])
            lab[sy*w+sx] = 1
            while q:
                x, y = q.popleft()
                blob.append((x, y))
                for nx, ny in ((x+1,y), (x-1,y), (x,y+1), (x,y-1)):
                    if 0 <= nx < w and 0 <= ny < h and not lab[ny*w+nx] and px[nx, ny][3] > thresh:
                        lab[ny*w+nx] = 1
                        q.append((nx, ny))
            out.append(blob)
    out.sort(key=len, reverse=True)
    return out

data = {}
for n in (25, 50, 100, 250, 500):
    im = Image.open(f'docs/shirts/{n}.png').convert('RGBA')
    w, h = im.size
    px = im.load()
    bg = ground_colour(px, w, h)
    is_bg = flood_ground(px, w, h, bg)
    holes = fill_holes(px, w, h, bg, is_bg)
    unmatte(px, w, h, bg, is_bg)
    blobs = components(px, w, h)
    for blob in blobs[1:]:
        for x, y in blob:
            px[x, y] = (0, 0, 0, 0)

    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
    data[str(n)] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    print(f'{n}: bg={bg} holes={holes:,} kept={len(blobs[0]):,}px dropped={len(blobs)-1} -> {len(buf.getvalue()):,}b')

json.dump(data, open('scripts/shirts_data.json', 'w'))
print('wrote scripts/shirts_data.json')

# Run from the repo root:  python3 scripts/make_shirts.py
# Reads docs/shirts/{25,50,100,250,500}.png (left untouched) and rewrites
# scripts/shirts_data.json, which build.py inlines into the dashboard.
