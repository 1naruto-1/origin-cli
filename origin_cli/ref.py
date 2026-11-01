"""参考图工具（学习新风格、复刻时对照用）：measure 找坐标框、统计主色；compare 把参考图与成品并排。"""
from collections import Counter

from PIL import Image, ImageDraw


def _load(path):
    im = Image.open(path)
    dpi = im.info.get('dpi', (None, None))[0]
    im = im.convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert('RGB'), dpi


def _runs(line, min_len):
    """一行像素里连续深色段的 (起, 止)"""
    out, start = [], None
    for i, dark in enumerate(line + [False]):
        if dark and start is None:
            start = i
        elif not dark and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return out


def frames(im) -> list:
    """找坐标框：上下两条横线与左右两条竖线围成的矩形（像素）。
    横线两端可能连着朝外的刻度（框角上的刻度与框线同一行），左右边以贯通上下的竖线为准。"""
    W, H = im.size
    px = im.load()
    dark = [[max(px[x, y]) < 100 for x in range(W)] for y in range(H)]
    hlines = [(y, a, b) for y in range(H) for a, b in _runs(dark[y], W // 6)]
    cols = [[dark[y][x] for y in range(H)] for x in range(W)]
    vlines = [(x, a, b) for x in range(W) for a, b in _runs(cols[x], H // 8)]
    boxes = []
    for i, (y0, a0, b0) in enumerate(hlines):
        for y1, a1, b1 in hlines[i + 1:]:
            lo, hi = max(a0, a1), min(b0, b1)
            if y1 - y0 < H // 10 or hi - lo < W // 6:
                continue
            xs = [x for x, va, vb in vlines if lo - 3 <= x <= hi + 3 and va <= y0 + 3 and vb >= y1 - 3]
            if xs and max(xs) - min(xs) >= W // 6:
                if not any(abs(bx[0] - min(xs)) <= 3 and abs(bx[1] - y0) <= 3 for bx in boxes):
                    boxes.append([min(xs), y0, max(xs), y1])
                break
    return boxes


def colors(im, box=None, n=12) -> list:
    """区域内的主色（去掉近白、近黑与灰色），按出现次数排序。"""
    if box:
        im = im.crop(tuple(box))
    cnt = Counter()
    for r, g, b in im.getdata():
        if min(r, g, b) > 235 or max(r, g, b) < 40 or max(r, g, b) - min(r, g, b) < 18:
            continue
        cnt[(r // 4 * 4, g // 4 * 4, b // 4 * 4)] += 1
    return [{'color': '#%02X%02X%02X' % c, 'pixels': k} for c, k in cnt.most_common(n)]


def measure(path, box=None) -> dict:
    im, dpi = _load(path)
    out = {'size_px': list(im.size), 'dpi': dpi}
    boxes = frames(im)
    out['frames_px'] = boxes
    if dpi:
        out['frames_cm'] = [[round(v / dpi * 2.54, 2) for v in (b[0], b[1], b[2] - b[0], b[3] - b[1])] for b in boxes]
    if box:
        box = [int(v) for v in str(box).split(',')] if isinstance(box, str) else box
        out['box'] = box
        out['colors'] = colors(im, box)
    else:
        out['colors'] = colors(im)
    return out


def compare(a, b, out, height=900) -> dict:
    """左右并排（左参考、右成品）。两张图都带 dpi 时按实际尺寸同比例缩放，字号、线宽可以直接比；
    否则缩放到同样高度。"""
    loaded = [_load(path) for path in (a, b)]
    if all(dpi for _, dpi in loaded):
        cm = [im.height / dpi for im, dpi in loaded]
        per_cm = height / max(cm)
        scale = [per_cm / dpi for _, dpi in loaded]
        mode = 'physical'
    else:
        scale = [height / im.height for im, _ in loaded]
        mode = 'same_height'
    ims = [im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
           for (im, _), k in zip(loaded, scale)]
    height = max(im.height for im in ims)
    W = ims[0].width + ims[1].width + 30
    canvas = Image.new('RGB', (W, height + 30), 'white')
    canvas.paste(ims[0], (0, 30))
    canvas.paste(ims[1], (ims[0].width + 30, 30))
    d = ImageDraw.Draw(canvas)
    d.text((10, 8), 'reference', fill='black')
    d.text((ims[0].width + 40, 8), 'output', fill='black')
    d.line([(ims[0].width + 15, 0), (ims[0].width + 15, height + 30)], fill=(200, 200, 200))
    canvas.save(out)
    return {'out': out, 'size_px': [W, height + 30], 'scale': mode}
