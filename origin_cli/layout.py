"""几何计算（单位 cm，纯 Python）：页面排版、自动坐标范围、图例定位与避让。"""
import math

PT = 2.54 / 72          # 1 pt 合多少 cm


def nice_step(span: float, target: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag * 1.0001:
            return m * mag
    return 10 * mag


def decimals(step: float) -> int:
    s = f'{step:.10g}'
    return len(s.split('.')[1]) if '.' in s and 'e' not in s else 0


def first_tick(lo: float, step: float) -> float:
    return round(math.ceil(lo / step - 1e-9) * step, 12)


def floor_to(v: float, step: float) -> float:
    return round(math.floor(v / step + 1e-9) * step, 12)


def ceil_to(v: float, step: float) -> float:
    return round(math.ceil(v / step - 1e-9) * step, 12)


def x_axis(values, step=None, target=7) -> dict:
    """横轴两端留白：数据等距时留半个数据间距（至少四分之一刻度），否则留半个刻度。
    参考图 20–90、间距 10 → 15–95；JSAC Fig.8 15–165、间距 15、刻度 30 → 7.5–172.5。"""
    lo, hi = min(values), max(values)
    step = step or nice_step(hi - lo, target)
    ux = sorted(set(values))
    pad = step / 2
    if len(ux) > 2:
        dx = min(b - a for a, b in zip(ux, ux[1:]))
        if dx > 0 and all(abs((u - lo) / dx - round((u - lo) / dx)) < 1e-6 for u in ux):
            pad = min(step / 2, max(dx / 2, step / 4))
    return {'from': lo - pad, 'to': hi + pad, 'step': step, 'first': first_tick(lo, step)}


def y_axis(lo: float, hi: float, step=None, target=5, baseline=None) -> dict:
    """纵轴：上下各留约 0.35 个刻度间距；柱状图从基线（一般为 0）起。"""
    step = step or nice_step(hi - lo, target)
    pad = 0.35 * step
    lo_axis = baseline if baseline is not None else lo - pad
    return {'from': lo_axis, 'to': hi + pad, 'step': step, 'first': first_tick(lo_axis, step)}


# ---------- 页面排版 ----------

def page_layout(cells: list, rows: list, gap=(0.35, 0.25), width=None, outer=0.1) -> dict:
    """cells：每个面板 {'frame': (w, h), 'margin': (左, 上, 右, 下)}，按 rows（每行面板数）分行，
    每行水平居中。返回页面尺寸与每个面板框的位置 (left, top, w, h)，单位 cm。"""
    if sum(rows) != len(cells):
        raise ValueError(f'layout.rows 的面板数 {sum(rows)} 与 panels 个数 {len(cells)} 不符')
    sizes = [(c['margin'][0] + c['frame'][0] + c['margin'][2], c['margin'][1] + c['frame'][1] + c['margin'][3])
             for c in cells]
    row_items, k = [], 0
    for n in rows:
        row_items.append(list(range(k, k + n)))
        k += n
    row_w = [sum(sizes[i][0] for i in items) + gap[0] * (len(items) - 1) for items in row_items]
    page_w = max(width or 0, max(row_w) + 2 * outer)
    frames, y = [None] * len(cells), outer
    for items, rw in zip(row_items, row_w):
        x = (page_w - rw) / 2
        for i in items:
            m, (fw, fh) = cells[i]['margin'], cells[i]['frame']
            frames[i] = (round(x + m[0], 4), round(y + m[1], 4), fw, fh)
            x += sizes[i][0] + gap[0]
        y += max(sizes[i][1] for i in items) + gap[1]
    return {'page': (round(page_w, 4), round(y - gap[1] + outer, 4)), 'frames': frames}


def fit_width(cells: list, rows: list, gap, width: float, outer=0.1):
    """按页面宽度（如期刊单栏 8.5 cm）等比缩放没有指定 frame 的面板框，使最宽的一行正好铺满；留白不变。"""
    scale, k = None, 0
    for n in rows:
        items = cells[k:k + n]
        k += n
        free = sum(c['frame'][0] for c in items if not c.get('fixed'))
        fixed = 2 * outer + gap[0] * (n - 1) + sum(c['margin'][0] + c['margin'][2] for c in items)             + sum(c['frame'][0] for c in items if c.get('fixed'))
        if free:
            s = (width - fixed) / free
            scale = s if scale is None else min(scale, s)
    if scale is None or scale <= 0:
        return cells
    for c in cells:
        if not c.get('fixed'):
            c['frame'] = [round(c['frame'][0] * scale, 4), round(c['frame'][1] * scale, 4)]
    return cells


# ---------- 图例避让 ----------

def _extent_in_span(shapes, a, b, xr, frame):
    """横向区间 [a, b]（cm）内数据占到的最低、最高处（数据单位），以及该处的符号半径（cm）。
    shapes：('line', xs, ys, r_cm) 折线（点上有半径 r 的符号）或 ('rect', x0, x1, y0, y1) 柱。"""
    W = frame[0]
    X = lambda x: (x - xr[0]) / (xr[1] - xr[0]) * W
    lows, highs = [], []
    for s in shapes:
        if s[0] == 'rect':
            if X(s[2]) >= a and X(s[1]) <= b:
                lows.append((s[3], 0.0))
                highs.append((s[4], 0.0))
            continue
        _, xs, ys, r = s
        pts = sorted(zip((X(x) for x in xs), ys))
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            lo, hi = max(xa, a), min(xb, b)
            if lo > hi or xb == xa:
                continue
            for xc in (lo, hi):
                yc = ya + (yb - ya) * (xc - xa) / (xb - xa)
                lows.append((yc, 0.0))
                highs.append((yc, 0.0))
        for xp, yp in pts:
            if a - r <= xp <= b + r:
                lows.append((yp, r))
                highs.append((yp, r))
    return lows, highs


def _bound(items, yr, H, need, side):
    """为让 items 都离开图例带（距框边 need cm），纵轴另一端需要延到哪里；side 为 bottom/top。"""
    y0, y1 = yr
    if side == 'bottom':
        # (y - y0') / (y1 - y0') * H - r >= need  =>  y0' <= (y H - (need + r) y1) / (H - need - r)
        return min(((y * H - (need + r) * y1) / (H - need - r) for y, r in items), default=y0)
    # (y - y0) / (y1' - y0) * H + r <= H - need  =>  y1' >= y0 + (y - y0) H / (H - need - r)
    return max((y0 + (y - y0) * H / (H - need - r) for y, r in items), default=y1)


def place_legend(frame, xr, yr, shapes, size, pos='auto', margin=0.12, side_gap=0.1, clear=0.08,
                 step=None, fixed=False, floor=None, shift_weight=3.0, max_extend=0.6, auto=('bottom', 'top'),
                 parts=None) -> dict:
    """图例放在框内底部（或顶部）左右居中；与曲线/符号/柱重叠时，先在可接受范围内左右平移，
    再把纵轴往图例一侧延长留出空白。返回 pos、offset（cm，相对框中心）、新的 y 范围、是否仍重叠。

    frame=(W, H) cm；xr、yr 为坐标范围；size=(lw, lh) cm；fixed=True 时不改纵轴范围；
    floor 为纵轴下限不能越过的值（柱状图的基线）。
    pos：auto / bottom / top / top-left / top-right / bottom-left / bottom-right；带 -left/-right 的贴角放、不平移。
    auto 时依次试 auto 列表里的位置，越靠后代价越高。
    parts：图例实际占用的几块矩形 (x, y, w, h)，相对整体左上角（cm）；缺省为整块。
    带大括号的图例只有括号和组名那几行占地方，按块计算不会把空白处也当成占用。"""
    W, H = frame
    lw, lh = size
    parts = parts or [(0.0, 0.0, lw, lh)]
    max_shift = max((W - lw) / 2 - side_gap, 0.0)
    offsets = sorted({round(k * 0.05, 4) for k in range(-int(max_shift / 0.05), int(max_shift / 0.05) + 1)} | {0.0},
                     key=abs)
    best = None
    span = yr[1] - yr[0]
    Y = lambda y: (y - yr[0]) / span * H
    for rank, cand in enumerate(list(auto) if pos == 'auto' else [pos]):
        side, _, align = cand.partition('-')
        if side not in ('bottom', 'top') or align not in ('', 'left', 'right'):
            raise ValueError(f'legend.pos 不认识 {cand!r}（可用 auto / bottom / top / top-left / top-right / bottom-left / bottom-right）')
        for off in ([(-1 if align == 'left' else 1) * max_shift] if align else offsets):
            left0, bounds, intrude = W / 2 + off - lw / 2, [], 0.0
            for px, py, pw, ph in parts:
                lows, highs = _extent_in_span(shapes, left0 + px - clear, left0 + px + pw + clear, xr, frame)
                items = lows if side == 'bottom' else highs
                need = margin + (lh - py if side == 'bottom' else py + ph) + clear       # 这一块离框边的距离
                bounds.append(_bound(items, yr, H, need, side))
                if side == 'bottom':
                    intrude = max([intrude] + [need - (Y(y) - r) for y, r in items])
                else:
                    intrude = max([intrude] + [Y(y) + r - (H - need) for y, r in items])
            if side == 'bottom':
                bound = min(bounds)
                ok_now = bound >= yr[0]
                new = yr if ok_now else (floor_to(bound, step / 2) if step else bound, yr[1])
                if floor is not None and new[0] < floor - 1e-12:
                    new = None
            else:
                bound = max(bounds)
                ok_now = bound <= yr[1]
                new = yr if ok_now else (yr[0], ceil_to(bound, step / 2) if step else bound)
            ext = 0.0 if new is None else ((new[1] - new[0]) - span) / span
            if new is None or (not ok_now and fixed) or ext > max_extend:
                # 放不下：按侵入图例带的深度排序，留在原坐标范围
                cost, new, overlap = 10.0 + max(intrude, 0) / H, yr, True
            else:
                cost, overlap = ext, False
            cost += (0 if align else shift_weight * abs(off) / W) + 0.15 * rank
            item = {'pos': cand, 'offset': off, 'y': tuple(new), 'extended': not overlap and ext > 0,
                    'overlap': overlap, 'cost': cost}
            if best is None or cost < best['cost'] - 1e-9:
                best = item
    best.pop('cost')
    best['fits'] = lw + 2 * side_gap <= W and lh + 2 * margin <= H
    return best


def legend_center(frame, yr, placed, size, margin=0.12):
    """图例中心在框内的位置（cm，原点在框左下）。"""
    W, H = frame
    lh = size[1]
    cy = margin + lh / 2 if placed['pos'].startswith('bottom') else H - margin - lh / 2
    return W / 2 + placed['offset'], cy


def brace_points(x, y_top, y_bot, w, n=4):
    """向右开口的花括号（右侧尖端在中点），页面坐标（y 向下）。返回折线点列。"""
    h = y_bot - y_top
    r = min(w / 2, h / 6)
    mid = (y_top + y_bot) / 2

    def arc(cx, cy, a0, a1):
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
                 cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
    xm = x + r                      # 竖直部分所在的位置
    pts = arc(x, y_top + r, -90, 0)                             # 顶端弯向竖直段
    pts += arc(xm + r, mid - r, 180, 90)                         # 竖直段弯向尖端
    pts += arc(xm + r, mid + r, 270, 180)                        # 尖端弯回竖直段
    pts += arc(x, y_bot - r, 0, 90)                              # 竖直段弯向底端
    return pts
