"""读回 .opju 里图的结构与格式：页面、图层框、坐标轴、每条曲线的样式、图例与文字对象（学习已有图、验收用）。"""
from . import style

# 格式树里的颜色：0–23 为 Origin 调色板序号（0 起），-4 无，-9 自动，≥0x1000000 为 RGB
_PALETTE = ['#000000', '#FF0000', '#00FF00', '#0000FF', '#00FFFF', '#FF00FF', '#FFFF00', '#808000', '#000080',
            '#800080', '#800000', '#008000', '#008080', '#0000A0', '#FF8000', '#8000FF', '#FF0080', '#FFFFFF',
            '#C0C0C0', '#808080', '#FFFF80', '#80FFFF', '#FF80FF', '#404040']
_UNITS_CM = {2: 2.54, 3: 1.0, 4: 0.1, 6: 2.54 / 72}


def color(v):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return None
    if v >= 0x1000000:
        return '#{:02X}{:02X}{:02X}'.format(v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)
    if 0 <= v < len(_PALETTE):
        return _PALETTE[v]
    return {-4: 'none', -9: 'auto'}.get(v, f'special({v})')


def _inv(table, v):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return v
    return next((k for k, n in table.items() if n == v), v)


def _f(v):
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return v


def inspect_project(s, graph=None) -> dict:
    op = s.op
    graphs = [g for g in op.graph_list() if not graph or graph in (g.name, g.lname)]
    out = []
    for g in graphs:
        res = g.get_float('resx') or 600
        page = {'name': g.name, 'size_cm': [round(g.get_float('width') / res * 2.54, 3),
                                            round(g.get_float('height') / res * 2.54, 3)], 'layers': []}
        g.lt_exec(f'win -a {g.name};')
        for L in g:
            li = L.index()
            unit = int(L.get_float('unit'))
            dims = [L.get_float(k) for k in ('left', 'top', 'width', 'height')]
            if unit == 1:            # 页面百分比
                frame = [dims[0] * page['size_cm'][0] / 100, dims[1] * page['size_cm'][1] / 100,
                         dims[2] * page['size_cm'][0] / 100, dims[3] * page['size_cm'][1] / 100]
            else:
                frame = [v * _UNITS_CM.get(unit, 1.0) for v in dims]
            lay = {'index': li, 'frame_cm': [round(v, 3) for v in frame], 'axes': {}, 'plots': [], 'objects': []}
            for a in ('x', 'y'):
                lay['axes'][a] = {k: _f(L.get_float(f'{a}.{k}')) for k in ('from', 'to', 'inc', 'ticks')}
                lay['axes'][a]['label_pt'] = _f(L.get_float(f'{a}.label.pt'))
            for k, p in enumerate(L.plot_list()):
                t = s.dump(g.name, li, plot=k)
                lay['plots'].append({
                    'range': p.lt_range(), 'color': color(t.get('Line/Color')),
                    'shape': _inv(style.SHAPES, t.get('Symbol/Shape')), 'interior': _inv(style.INTERIORS, t.get('Symbol/Interior')),
                    'size': _f(t.get('Symbol/Size')), 'edge': color(t.get('Symbol/EdgeColor')),
                    'fill': color(t.get('Symbol/FillColor')), 'dash': _inv(style.DASHES, t.get('Line/Style')),
                    'width': _f(t.get('Line/Width')), 'line_behind_symbol': t.get('Line/LineSymbolOrder') == '2',
                    'bar_fill': color(t.get('Pattern/Fill/FillColor')) if 'Pattern/Fill/FillColor' in t else None})
            for go in L.obj.GetGraphObjects():
                name = go.GetName()
                box = [round(v / res * 2.54, 3) for v in (go.GetLeft(), go.GetTop(), go.GetWidth(), go.GetHeight())]
                off = box[0] > page['size_cm'][0] or box[1] > page['size_cm'][1] or box[0] + box[2] < 0 or box[1] + box[3] < 0
                if name.startswith('_') or not (box[2] or box[3]) or off:
                    continue        # Origin 内部对象、隐藏的占位对象、模板放在页面外的对象
                obj = {'name': name, 'box_cm': box}
                if go.GetText():
                    d = s.dump(g.name, li, obj=name)      # 格式树里的文字是 UTF-8，GetText 会把 η、ω 等转坏
                    obj.update({'text': d.get('Text', ''), 'font_pt': _f(d.get('Font/Size'))})
                lay['objects'].append(obj)
            page['layers'].append(lay)
        out.append(page)
    return {'graphs': out}
