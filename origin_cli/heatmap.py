"""热力图：矩阵着色、白线分格、格内数值、分类刻度、右侧色标（学自 热力图/1–3）。

色标规则：同一张图里多幅热图共用色标下限（全局最小值向下取到 0.01），上限取各自最大值（保留 3 位小数）；
色标 6 个等距刻度，保留 3 位小数；格内数值保留 4 位小数、白字。
"""
import math

import numpy as np

from . import layout, style

DARK = '#1A1A1A'


def _numeric(labels):
    """标签全是等距数值时返回数值列表，否则 None（按分类处理）。"""
    try:
        vals = [float(v) for v in labels]
    except (TypeError, ValueError):
        return None
    if len(vals) > 2:
        d = vals[1] - vals[0]
        if d == 0 or any(abs((b - a) - d) > abs(d) * 1e-6 for a, b in zip(vals, vals[1:])):
            return None
    return vals


def _fmt(v, dec):
    return f'{v:.{dec}f}'


def z_ranges(panels, st):
    """各幅的色标范围 (lo, hi)。z.min：数值 / shared（默认，共用下限）/ own；z.max：数值 / own（默认）/ shared。"""
    dec = st['colorbar']['decimals']
    mins = [float(np.nanmin(np.asarray(p['values'], float))) for p in panels]
    maxs = [float(np.nanmax(np.asarray(p['values'], float))) for p in panels]
    lo_step, hi_step = 10 ** -(dec - 1), 10 ** -dec
    out = []
    for p, mn, mx in zip(panels, mins, maxs):
        z = p.get('z') or {}
        dz = z.get('decimals', dec)
        lo = z.get('min', 'shared')
        hi = z.get('max', 'own')
        lo = lo if isinstance(lo, (int, float)) else layout.floor_to(min(mins) if lo == 'shared' else mn, lo_step)
        hi = hi if isinstance(hi, (int, float)) else round(max(maxs) if hi == 'shared' else mx, dz)
        if hi <= lo:
            hi = lo + hi_step
        out.append((lo, hi))
    return out


def _luminance(c):
    lin = [v / 255 for v in style.hex2rgb(c)]
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in lin]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def cell_ink(colors, t):
    """格内文字默认白字（参考图风格）；只有白字几乎看不清的浅色格（与白色对比度 < 1.8）改用深色字。"""
    bg = colors[min(max(round(t * (len(colors) - 1)), 0), len(colors) - 1)]
    return '#FFFFFF' if 1.05 / (_luminance(bg) + 0.05) >= 1.8 else DARK


def colormap(L, lo, hi, colors):
    n = len(colors)
    L.lt_exec(f'layer.cmap.zmin={lo}; layer.cmap.zmax={hi}; layer.cmap.numMajorLevels={n}; '
              'layer.cmap.numMinorLevels=0; layer.cmap.SetLevels(1);')
    L.lt_exec(' '.join(f'layer.cmap.color{i}=color({c});' for i, c in enumerate(colors, 1))
              + f' layer.cmap.colorBelow=color({colors[0]}); layer.cmap.colorAbove=color({colors[-1]});'
              ' layer.cmap.updateScale();')


def heatmap_panels(fig, items):
    """items：[(图层, 面板, 框)]，返回 {面板序号: 报告}。"""
    st = fig.st['heatmap']
    ranges = z_ranges([p for _, p, _ in items], st)
    reports = {}
    for (L, p, frame), (lo, hi) in zip(items, ranges):
        reports[L.index()] = draw(fig, L, p, frame, lo, hi)
    return reports


def draw(fig, L, p, frame, lo, hi):
    op, st = fig.op, fig.st['heatmap']
    k = L.index()
    vals = np.asarray(p['values'], float)
    nr, nc = vals.shape
    xs = _numeric(p['cols'])
    xs = xs if xs and nc > 1 else [float(j + 1) for j in range(nc)]
    dx = xs[1] - xs[0] if nc > 1 else 1.0
    cat_x = _numeric(p['cols']) is None
    ms = op.new_sheet('m', lname=f'heatmap {k + 1}')
    ms.from_np(np.flipud(vals))                     # 第一行显示在最上
    ms.xymap = (xs[0], xs[-1], 1.0, float(nr))
    L.add_mplot(ms, 0, type=105)
    L.rescale()                                     # 不 rescale 时色阶属性还没初始化
    L.lt_exec('label -r SPECTRUM1; label -r legend;')
    colors = style.heatmap_colors(p.get('palette', st['palette']), st['levels'])
    colormap(L, lo, hi, colors)
    xa = {'from': xs[0] - dx / 2, 'to': xs[-1] + dx / 2, 'step': dx, 'first': xs[0],
          'decimals': p['x'].get('decimals', layout.decimals(dx))}
    ya = {'from': 0.5, 'to': nr + 0.5, 'step': 1, 'first': 1, 'decimals': 0}
    sub = {'x': {'title': None if cat_x else p['x'].get('title')}, 'y': {'title': p['y'].get('title')}}
    fig.axes(L, xa, ya, sub, ticks=st['ticks'])
    L.lt_exec('layer.y.showLabels=0; layer.x.label.rotate=0;' + (' layer.x.showLabels=0;' if cat_x else ''))
    size = fig.st['font']['size']
    # 行标签（从上到下）在框左侧右对齐；分类横轴的列标签在框下方
    items = []
    tick = fig.st['axis']['tick_length'] * layout.PT
    for r, label in enumerate(p['rows']):
        nm = fig.text(L, label, size)
        items.append((nm, frame[0] - tick - 0.08, frame[1] + (r + 0.5) / nr * frame[3], 'rc'))
    if cat_x:
        for j, label in enumerate(p['cols']):
            nm = fig.text(L, label, size)
            items.append((nm, frame[0] + (j + 0.5) / nc * frame[2], frame[1] + frame[3] + tick + 0.06, 'ct'))
    fig.at_page(L, items)
    if cat_x and p['x'].get('title'):
        nm = fig.text(L, p['x']['title'], size)
        fig.at_page(L, [(nm, frame[0] + frame[2] / 2, frame[1] + frame[3] + tick + 0.42, 'ct')])
        bx = fig.box(L, nm)
        fig.xtitle_bottom[k] = bx[1] + bx[3]
    # 白线分格
    y0, y1 = 0.5, nr + 0.5
    for j in range(nc - 1):
        x = xs[j] + dx / 2
        fig.segment(L, x, y0, x, y1, st['grid'], st['grid_width'])
    for r in range(1, nr):
        fig.segment(L, xa['from'], r + 0.5, xa['to'], r + 0.5, st['grid'], st['grid_width'])
    # 格内数值
    cells = p.get('cells') or {}
    dec, color = cells.get('decimals', st['cell_decimals']), cells.get('color', st['cell_color'])
    if cells.get('show', True):
        for r in range(nr):
            for j in range(nc):
                v = vals[r, j]
                if v != v:
                    continue
                c = color if color != 'auto' else cell_ink(colors, (v - lo) / (hi - lo))
                nm = fig.text(L, _fmt(v, dec), cells.get('size', st['cell_size']), c)
                fig.at_data(L, nm, xs[j], nr - r)
    colorbar(fig, p, frame, lo, hi, colors)
    return {'z': [lo, hi], 'x': [xa['from'], xa['to']], 'y': [y0, y1]}


def colorbar(fig, p, frame, lo, hi, colors):
    """色标单独占一个图层：竖向渐变矩阵，右侧刻度与刻度值，标目竖排在热图与色标之间。"""
    op, cb = fig.op, fig.st['heatmap']['colorbar']
    cbar = p.get('colorbar') or {}
    if cbar.get('show', True) is False:
        return
    left = frame[0] + frame[2] + cbar.get('gap', cb['gap'])
    width = cbar.get('width', cb['width'])
    B = fig.new_layer((left, frame[1], width, frame[3]))
    ms = op.new_sheet('m', lname=f'colorbar {B.index()}')
    ms.from_np(np.repeat(np.linspace(lo, hi, 129)[:, None], 2, axis=1))
    ms.xymap = (0.0, 1.0, lo, hi)
    B.add_mplot(ms, 0, type=220)       # 图像图：PDF 里是一整张位图，不会出现小矩形之间的接缝
    B.rescale()
    B.lt_exec('label -r SPECTRUM1; label -r legend;')
    colormap(B, lo, hi, colors)
    n = cbar.get('ticks', cb['ticks'])
    dec = cbar.get('decimals', cb['decimals'])
    size = cbar.get('size', cb['size'])
    # 步长略小于等分，避免浮点误差丢掉顶端刻度
    xa = {'from': 0, 'to': 1, 'step': 1, 'first': 0, 'decimals': 0}
    ya = {'from': lo, 'to': hi, 'step': (hi - lo) / (n - 1) * (1 - 1e-6), 'first': lo, 'decimals': dec}
    fig.axes(B, xa, ya, {'x': {}, 'y': {}}, size=size, ticks='none')
    f = fig.font
    B.lt_exec(f'layer.x.showLabels=0; layer.y.ticks=0; layer.y2.ticks=2; layer.y.showLabels=2; '
              f'layer.y2.label.font={f}; layer.y2.label.pt={size}; layer.y2.label.numFormat=1; '
              f'layer.y2.label.decPlaces={dec};')
    title = cbar.get('title')
    if title:
        # 标目竖排在热图与色标之间（参考图的位置）
        nm = fig.text(B, title, size, rotate=90)
        fig.at_page(B, [(nm, (frame[0] + frame[2] + left) / 2, frame[1] + frame[3] / 2, 'cc')])
