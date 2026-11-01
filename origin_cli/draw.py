"""在 Origin 里按 spec 画图：页面与图层排版、点线/散点/柱状、坐标轴、断轴、图例、插图、标注、子图标题、导出。"""
import math
from pathlib import Path

from . import layout, style
from .layout import PT

INK = '#000000'
CJK = (('一', '鿿'), ('　', '〿'), ('＀', '￯'))


def _unique(values):
    out = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def _ok(v):
    return isinstance(v, float) and v == v


def _to_frac(v, ax):
    """坐标值在轴上的位置（0–1），对数轴按对数算。"""
    a, b = ax['from'], ax['to']
    if ax.get('log'):
        return (math.log10(max(v, 1e-300)) - math.log10(a)) / (math.log10(b) - math.log10(a))
    return (v - a) / (b - a)


def _from_frac(f, ax):
    a, b = ax['from'], ax['to']
    if ax.get('log'):
        return 10 ** (math.log10(a) + f * (math.log10(b) - math.log10(a)))
    return a + f * (b - a)


class Figure:
    RES = 600   # 页面坐标单位为 1/600 英寸，与导出 dpi 无关

    def __init__(self, session, spec):
        self.s, self.op, self.spec, self.st = session, session.op, spec, spec['style']
        self.font = int(session.num(f'font({self.st["font"]["face"]})'))
        self.n, self.warnings, self.panels, self.xtitle_bottom = 0, [], [], {}
        self.legends, self.insets = {}, []      # 图层序号 -> 图例文字；插图图层

    # ---------- 基础 ----------
    def dots(self, cm):
        return round(cm / 2.54 * self.RES)

    def cm(self, dots):
        return dots / self.RES * 2.54

    def name(self, prefix):
        self.n += 1
        return f'{prefix}{self.n}'

    def rich(self, s) -> str:
        """中文字符改用中文字体（Origin 的 \\f:字体名(…) 转义），其余沿用对象字体。"""
        out, run = [], ''
        for ch in str(s):
            if any(a <= ch <= b for a, b in CJK):
                run += ch
                continue
            if run:
                out.append(f'\\f:{self.st["font"]["cjk"]}({run})')
                run = ''
            out.append(ch)
        if run:
            out.append(f'\\f:{self.st["font"]["cjk"]}({run})')
        return ''.join(out)

    def text(self, L, s, size=None, color=INK, rotate=0):
        nm = self.name('T')
        self.s.set_str('__t$', self.rich(s))
        L.lt_exec(f'label -n {nm} "x"; {nm}.text$ = __t$; {nm}.font = {self.font}; '
                  f'{nm}.fsize = {size or self.st["font"]["size"]}; {nm}.color = color({color}); '
                  f'{nm}.background = 0; {nm}.rotate = {rotate};')
        return nm

    def at_data(self, L, nm, x, y):
        """对象中心放到坐标 (x, y)，随坐标轴移动。"""
        L.lt_exec(f'{nm}.attach = 2; {nm}.x = {x}; {nm}.y = {y};')

    def at_page(self, L, items):
        """items：[(对象名, x cm, y cm, 锚点)]，锚点两个字母：横向 l/c/r、纵向 t/c/b，如 'ct' 为上沿中点。"""
        self.s.lt('doc -uw;')
        for nm, x, y, anchor in items:
            obj = L.label(nm)
            w, h = obj.get_float('width'), obj.get_float('height')
            left = self.dots(x) - {'l': 0, 'c': w / 2, 'r': w}[anchor[0]]
            top = self.dots(y) - {'t': 0, 'c': h / 2, 'b': h}[anchor[1]]
            obj.set_int('left', round(left))
            obj.set_int('top', round(top))

    def box(self, L, nm):
        """对象在页面上的位置 (left, top, width, height)，cm。"""
        obj = L.label(nm)
        return tuple(self.cm(obj.get_float(k)) for k in ('left', 'top', 'width', 'height'))

    def segment(self, L, x1, y1, x2, y2, color=INK, width=0.75, dash=0, arrow=False, head=(4, 6)):
        """数据坐标的线段；arrow 为 True（终点带箭头）或 'both'（两端都带），head 为箭头的 (宽, 长)。"""
        nm = self.name('D')
        L.lt_exec(f'draw -n {nm} -l {{{x1}, {y1}, {x2}, {y2}}}; {nm}.color = color({color}); '
                  f'{nm}.lineWidth = {width}; {nm}.lineType = {dash + 1};')
        if arrow:
            hd = {'Style': 1, 'Width': head[0], 'Length': head[1]}
            tree = {'Arrow': {'End': hd, **({'Begin': hd} if arrow == 'both' else {})}}
            self.s.fmt(self.g.name, L.index(), tree, obj=nm)
        return nm

    def to_data(self, L, frame, x, y, xa, ya, brk=None):
        """页面位置（cm）换成该图层的数据坐标（考虑对数轴和断轴）。"""
        X0, X1, Y0, Y1 = self.ranges(L)
        fx, fy = (x - frame[0]) / frame[2], 1 - (y - frame[1]) / frame[3]
        lin = lambda f, a, b, log: 10 ** (math.log10(a) + f * (math.log10(b) - math.log10(a))) if log else a + f * (b - a)
        if brk:
            pos = brk.get('at', 0.5)
            Y = Y0 + fy / pos * (brk['from'] - Y0) if fy <= pos else brk['to'] + (fy - pos) / (1 - pos) * (Y1 - brk['to'])
        else:
            Y = lin(fy, Y0, Y1, ya.get('log'))
        return lin(fx, X0, X1, xa.get('log')), Y

    def to_page(self, L, frame, x, y):
        """数据坐标换成页面位置（cm），考虑对数轴。"""
        X0, X1, Y0, Y1 = self.ranges(L)
        fx = _to_frac(x, {'from': X0, 'to': X1, 'log': L.get_float('x.type') == 2})
        fy = _to_frac(y, {'from': Y0, 'to': Y1, 'log': L.get_float('y.type') == 2})
        return frame[0] + fx * frame[2], frame[1] + (1 - fy) * frame[3]

    def polyline(self, L, frame, pts, xa, ya, brk=None, color=INK, width=0.4):
        data = [self.to_data(L, frame, x, y, xa, ya, brk) for x, y in pts]
        for (a, b), (c, d) in zip(data, data[1:]):
            if (a, b) != (c, d):
                self.segment(L, a, b, c, d, color, width)

    def new_layer(self, box, first=False):
        """图层按 box=(左, 上, 宽, 高) cm 放置，随即把缩放因子定为 1：否则之后设的字号、线宽会按图层大小缩放。"""
        L = self.g[0] if first else self.g.add_layer(0)
        L.lt_exec('layer.unit=3; layer.left={}; layer.top={}; layer.width={}; layer.height={};'.format(*box))
        self.g.lt_exec('page -afu1;')
        return L

    def ranges(self, L):
        return tuple(L.get_float(k) for k in ('x.from', 'x.to', 'y.from', 'y.to'))

    # ---------- 页面 ----------
    def render(self):
        spec, st = self.spec, self.st
        cells = []
        for p in spec['panels']:
            d = st['panel'].get(p['type'], st['panel']['line'])
            frame = list(p.get('frame') or d['frame'])
            if p['type'] == 'heatmap' and not p.get('frame'):
                frame[1] = len(p['rows']) * d['row_height']        # 每行高度与参考图相同
            m = list(p.get('margin') or d['margin'])
            if p['type'] != 'heatmap' and not p.get('margin'):
                shift, factor = self.axis_room(p)
                m[0] += shift
                if p.get('y2'):
                    shift2, factor2 = self.axis_room(p, 'y2')
                    m[2] = max(m[2], d['margin'][0] + shift2)      # 右纵轴的刻度值和标题
                    factor = factor or factor2
                if factor:
                    m[1] += 1.3 * st['font']['size'] * PT          # 框上方放 ×10ⁿ
            if p.get('caption'):
                m[3] += st['caption']['height']
            cells.append({'frame': frame, 'margin': m, 'fixed': bool(p.get('frame'))})
        lay = spec['layout']
        gap = tuple(lay.get('gap', st['layout']['gap']))
        if lay.get('width'):
            layout.fit_width(cells, lay['rows'], gap, lay['width'], st['layout']['outer'])
        geo = layout.page_layout(cells, lay['rows'], gap, lay.get('width'), st['layout']['outer'])
        self.page = geo['page']
        template = 'heatmap' if any(p['type'] == 'heatmap' for p in spec['panels']) else 'line'
        self.g = g = self.op.new_graph(template=template, lname=Path(spec['output']).name)
        g.lt_exec(f'page.kar=0; page.resx={self.RES}; page.resy={self.RES}; '
                  f'page.width={self.dots(self.page[0])}; page.height={self.dots(self.page[1])};')
        layers = [self.new_layer(frame, first=k == 0) for k, frame in enumerate(geo['frames'])]
        heat = [k for k, p in enumerate(spec['panels']) if p['type'] == 'heatmap']
        reports = {}
        if heat:
            from .heatmap import heatmap_panels
            reports = heatmap_panels(self, [(layers[k], spec['panels'][k], geo['frames'][k]) for k in heat])
        for k, (L, p, frame) in enumerate(zip(layers, spec['panels'], geo['frames'])):
            rep = {'index': k, 'type': p['type'], 'frame_cm': [round(v, 3) for v in frame]}
            rep.update(reports[k] if k in reports else self.xy_panel(L, k, p, frame))
            for script in p.get('labtalk') or []:
                L.lt_exec(script)
            self.panels.append(rep)
        self.captions(layers, geo['frames'])
        self.s.lt('doc -uw;')
        for IL in self.insets:
            IL.lt_exec('label -r legend;')      # 插图图层的自动图例会在刷新时重建，最后再删一次
        for host, text in self.legends.values():
            # 加辅助曲线（椭圆等）后 Origin 刷新时会往图例补条目，最后恢复
            self.s.set_str('__t$', text)
            host.lt_exec('legend.text$ = __t$;')
        for script in spec.get('labtalk') or []:
            g.lt_exec(script)
        g.lt_exec('page -afu1;')

    def axis_room(self, p, key='y'):
        """纵轴刻度值比参考图的“0.95”宽或窄时，留白相应增减，页面边缘的空白保持不变。返回 (增减 cm, 数量级因子)。"""
        if key == 'y':
            _, ya = self.auto_axes(p, p['series'], p['table'], p['type'] == 'bar')
        else:
            _, ya = self.auto_axes({'x': p['x'], 'y': p['y2']}, p['y2']['series'], p['table'], False)
        if ya.get('log'):
            return 0.0, None
        n = int((ya['to'] - ya['first']) / ya['step'] + 1e-9) + 1
        k = 10 ** (ya.get('factor') or 0)
        em = lambda t: sum(0.25 if ch == '.' else 0.5 for ch in t)        # 数字约半个字宽
        w = max(em(f'{(ya["first"] + j * ya["step"]) / k:.{ya["decimals"]}f}') for j in range(max(n, 1)))
        return (w - em('0.95')) * self.st['font']['size'] * PT, ya.get('factor')

    # ---------- 点线 / 散点 / 柱状 ----------
    def xy_panel(self, L, i, p, frame):
        st, op = self.st, self.op
        table, series = p['table'], p['series']
        y2 = p.get('y2')
        right = y2['series'] if y2 else []
        if y2 and p['y'].get('break'):
            raise ValueError(f'面板 {i}：y2（右纵轴）与断轴不能同时使用')
        enc = {**(st.get('encode') or {}), **(p.get('encode') or {})}
        bar = p['type'] == 'bar'
        order = self.bar_order(p, series) if bar else list(range(len(series)))
        # 重叠柱：画在后面的（高的）组颜色浅，前面的深
        group_order = _unique(series[k].get('group') for k in order) if bar and p.get('mode') == 'overlap' else None
        # 左右两轴一起分配样式，同名的柱和曲线同色
        styles = style.encode(series + right, mode=enc.get('color', 'auto'), size=enc.get('size', st['line']['symbol']),
                              size_step=enc.get('size_step', st['line']['symbol_step']),
                              width=enc.get('width', st['line']['width']), families=enc.get('families'),
                              group_order=enc.get('group_order', group_order), palette=enc.get('palette'),
                              shapes=enc.get('shapes'), dashes=enc.get('dashes'),
                              pattern=enc.get('pattern', st['bar'].get('pattern')) if bar else None)
        styles, styles2 = styles[:len(series)], styles[len(series):]
        wks = op.new_sheet('w', lname=f'panel {i + 1}')
        cols = _unique([c for s in series + right for c in (s['x'], s['y'], s.get('yerr')) if c])
        labels = p['x'].get('labels')
        for k, c in enumerate(cols):
            # 分类横轴写成文本列，Origin 按行号定位并拿它作刻度标签
            wks.from_list(k, labels if labels and c == p['x']['col'] else table[c], lname=c)
        idx = {c: k for k, c in enumerate(cols)}
        if bar:
            plots, errs = self.add_bars(L, i, p, wks, idx, series, order)
        else:
            plots, errs = self.add_lines(L, wks, idx, series, styles, p['type'] == 'scatter')
        for k, pl in plots.items():
            self.plot_style(L, pl, styles[k], bar, p['type'] == 'scatter' or series[k].get('line') is False)
        for k, e in errs.items():
            self.errbar(L, e, styles[k], bar)
        xa, ya = self.auto_axes(p, series, table, bar)
        self.axes(L, xa, ya, p)
        self.grid(L, p)
        if bar:
            L.lt_exec('layer.x.ticks=0;')          # 刻度在簇中央，会压在柱子的分界线上
        self.factor_label(L, ya, frame, 'left')
        number = {k: pl.index() + 1 for k, pl in plots.items()}     # 曲线在图层里的序号（\l(n) 用），误差棒也占序号
        shapes = self.occupancy(p, series, styles, xa, bar)
        rep = {}
        lg = p.get('legend') or {}
        if y2:
            R, plots2, ya2 = self.add_right(L, p, wks, idx, right, styles2, xa, frame)
            to_left = lambda v: _from_frac(_to_frac(v, ya2), ya)          # 右轴数值换到左轴坐标，供图例避让
            for sh in self.occupancy(p, right, styles2, xa, False):
                shapes.append(('rect', sh[1], sh[2], to_left(sh[3]), to_left(sh[4])) if sh[0] == 'rect'
                              else ('line', sh[1], [to_left(v) for v in sh[2]], sh[3]))
            rep['y2'] = [ya2['from'], ya2['to']]
        if not lg.get('show', True):
            L.lt_exec('label -r legend;')
        elif y2 and lg.get('layout', 'split') == 'split':
            # 左轴、右轴各一个单列图例，分放两侧的角上（文献 RCWA Fig.5 的做法）；第二个避开第一个
            corners = ('top-left', 'top-right', 'bottom-left', 'bottom-right')
            rep['legend'] = self.legend(L, i, p, series, number, frame, xa, ya, bar, shapes, fixed=True,
                                        auto=corners, ncol=1)
            l, t, w, h = rep['legend']['box_cm']
            (x0, y0), (x1, y1) = self.to_data(L, frame, l, t + h, xa, ya), self.to_data(L, frame, l + w, t, xa, ya)
            number2 = {k: pl.index() + 1 for k, pl in plots2.items()}
            rep['legend2'] = self.legend(L, i, p, right, number2, frame, xa, ya, False, shapes + [('rect', x0, x1, y0, y1)],
                                         fixed=True, host=R, auto=corners[1::-1] + corners[:1:-1], ncol=1)
        else:
            leg = list(series)
            if y2:
                number.update({len(series) + k: f'{R.index() + 1}.{pl.index() + 1}' for k, pl in plots2.items()})
                leg += right
                if not any(s.get('group') for s in leg):
                    # 合成一个图例时按轴分行：行首为轴标题
                    lt, rt = p['y'].get('title') or 'left', y2.get('title') or 'right'
                    leg = [dict(s, group=lt) for s in series] + [dict(s, group=rt) for s in right]
            rep['legend'] = self.legend(L, i, p, leg, number, frame, xa, ya, bar, shapes, fixed=bool(y2))
        if y2 and y2.get('hint'):
            self.y2_hint(L, p, right, ya, ya2)
        if p.get('inset'):
            rep['inset'] = self.inset(L, p, series, styles, frame, wks, idx)
        for mk in p.get('marks') or []:
            self.mark(L, mk, frame, i)
        x0, x1, y0, y1 = self.ranges(L)
        rep.update({'x': [x0, x1], 'y': [y0, y1], 'styles': styles + styles2})
        return rep

    def add_lines(self, L, wks, idx, series, styles, scatter_panel):
        plots, errs = {}, {}
        for k, s in enumerate(series):
            scatter = scatter_panel or s.get('line') is False
            kind = 's' if scatter else 'l' if styles[k]['shape'] == 'none' else 'y'
            plots[k] = L.add_plot(wks, idx[s['y']], idx[s['x']], type=kind,
                                  colyerr=idx[s['yerr']] if s.get('yerr') else -1)
            if s.get('yerr'):
                errs[k] = L.plot_list()[plots[k].index() + 1]      # 误差棒是紧跟在曲线后的一条
        return plots, errs

    def add_right(self, L, p, wks, idx, right, styles2, xa, frame):
        """右纵轴：与主图层同框、横轴联动的图层（Origin 的 Right-Y 图层），画 y2 的曲线。"""
        y2 = p['y2']
        self.g.lt_exec(f'page.active = {L.index() + 1};')
        R = self.g.add_layer(2)
        self.g.lt_exec('page -afu1;')
        plots, errs = self.add_lines(R, wks, idx, right, styles2, y2['type'] == 'scatter')
        for k, pl in plots.items():
            self.plot_style(R, pl, styles2[k], False, y2['type'] == 'scatter' or right[k].get('line') is False)
        for k, e in errs.items():
            self.errbar(R, e, styles2[k], False)
        _, ya2 = self.auto_axes({'x': p['x'], 'y': y2}, right, p['table'], False)
        st, f = self.st, self.font
        ax = st['axis']
        tk = {'in': 1, 'out': 2, 'none': 0}[ax['ticks']]
        R.lt_exec(f'layer.x.from={xa["from"]}; layer.x.to={xa["to"]}; layer.x.showAxes=0; layer.x.showLabels=0; '
                  f'layer.x.ticks=0; layer.x2.ticks=0; layer.tickL={ax["tick_length"]}; layer.tickW={ax["tick_width"]}; '
                  f'layer.y.from={ya2["from"]}; layer.y.to={ya2["to"]}; layer.y.inc={ya2["step"]}; '
                  f'layer.y.firstTick={ya2["first"]}; layer.y.minorTicks={ax["minor"]}; layer.y.showAxes=2; '
                  f'layer.y.showLabels=2; layer.y.ticks=0; layer.y2.ticks={tk}; layer.y2.label.font={f}; '
                  f'layer.y2.label.pt={st["font"]["size"]}; layer.y2.label.numFormat=1; '
                  f'layer.y2.label.decPlaces={ya2["decimals"]}; layer.y2.thickness={ax["thickness"]};')
        if ya2.get('log'):
            R.lt_exec(f'layer.y.type=2; layer.y.labelSubtype=2; layer.y.inc=1; layer.y.firstTick={ya2["from"]};')
        if y2.get('title'):
            self.s.set_str('__t$', self.rich(y2['title']))
            R.lt_exec(f'label -yr "x"; yr.text$ = __t$; yr.font={f}; yr.fsize={st["font"]["title"]};')
        R.lt_exec('label -r xb; label -r yl; label -r xt;')
        self.factor_label(R, ya2, frame, 'right')
        if (p.get('legend') or {}).get('layout', 'split') != 'split' or not (p.get('legend') or {}).get('show', True):
            R.lt_exec('label -r legend;')
            self.insets.append(R)       # 刷新时冒出来的自动图例最后一并删掉
        return R, plots, ya2

    def y2_hint(self, L, p, right, ya, ya2):
        """虚线圈住右轴曲线的末端，再用箭头指向右纵轴（文献 RCWA Fig.5 的做法）。"""
        X0, X1, Y0, Y1 = self.ranges(L)
        ends = [pts[-1] for pts in (self.points(p['table'], s) for s in right) if pts]
        if not ends:
            return
        to_left = lambda v: _from_frac(_to_frac(v, ya2), ya)
        cx = max(x for x, _, _ in ends)
        ys = [to_left(y) for _, y, _ in ends]
        rx, ry = 0.035 * (X1 - X0), (max(ys) - min(ys)) / 2 + 0.06 * (Y1 - Y0)
        cy = (max(ys) + min(ys)) / 2
        color = self.st['mark'].get('hint_color', '#E02020')
        self.mark(L, {'type': 'ellipse', 'center': [cx, cy], 'radius': [rx, ry], 'dash': 'dash', 'color': color,
                      'width': 0.5}, None)
        self.segment(L, cx + rx, cy, X1, cy - 0.12 * (Y1 - Y0), color, 0.5, arrow=True)

    def bar_order(self, p, series):
        """重叠柱（overlap）：同一 group 的柱并排成簇，各 group 之间重叠；先画均值大的 group（在后面）。"""
        if p.get('mode', 'grouped') != 'overlap':
            return list(range(len(series)))
        groups = _unique(s.get('group') for s in series)
        mean = {g: sum(v for s in series if s.get('group') == g for v in p['table'][s['y']] if _ok(v)) for g in groups}
        out = []
        for g in sorted(groups, key=lambda g: -mean[g]):
            out += [k for k, s in enumerate(series) if s.get('group') == g]
        return out

    def add_bars(self, L, i, p, wks, idx, series, order):
        """每簇柱用一次 plotxy 画：Origin 把簇内的柱建成一组并排，误差棒排在组后并跟着各自的柱
        （逐条 add_plot 再建组时，组里夹着误差棒就不再并排）。返回 {序号: 柱}、{序号: 误差棒}。"""
        mode = p.get('mode', 'grouped')
        if mode not in ('grouped', 'stacked', 'overlap'):
            raise ValueError(f'面板 {i}：bar 的 mode 只能是 grouped / stacked / overlap')
        if mode == 'overlap':
            clusters = [[k for k in order if series[k].get('group') == g]
                        for g in _unique(series[k].get('group') for k in order)]
        else:
            clusters = [order]
        rng, plots, errs = wks.lt_range(False), {}, {}
        for ks in clusters:
            base = len(L.plot_list())
            cols = [[series[k]['x'], series[k]['y']] + ([series[k]['yerr']] if series[k].get('yerr') else []) for k in ks]
            xy = ','.join('(' + ','.join(str(idx[c] + 1) for c in cs) + ')' for cs in cols)
            self.s.lt(f'plotxy iy:={rng}!({xy}) plot:=203 ogl:=[{self.g.name}]{L.index() + 1}!;')
            self.s.lt('doc -uw;')       # 等 Origin 把新画的柱建好，再取曲线对象
            pl = L.plot_list()
            plots.update({k: pl[base + j] for j, k in enumerate(ks)})
            errs.update({k: pl[base + len(ks) + j] for j, k in enumerate(k for k in ks if series[k].get('yerr'))})
            if len(ks) > 1:
                plots[ks[0]].set_cmd('-gm 1')      # 组内独立编辑，否则各柱颜色由组的递增列表决定
        if mode == 'stacked':
            self.s.fmt(self.g.name, L.index(), {'Stack': {'Offset': 1}})
        return plots, errs

    def plot_style(self, L, pl, sty, bar, scatter):
        k, li = pl.index(), L.index()
        if bar:
            st = self.st['bar']
            fill = {'FillColor': self.op.ocolor(sty['color'])}
            if sty.get('pattern', 'none') != 'none':
                # 花纹叠在填充色上，黑白打印也能分清（文献 RCWA Fig.3–6 的做法）
                fill['Pattern'] = {'Style': style.PATTERNS[sty['pattern']], 'PatternColor': self.op.ocolor(st['border']),
                                   'Width': st.get('pattern_width', 0.3)}
            tree = {'Pattern': {'Fill': fill, 'Border': {'Color': self.op.ocolor(st['border']), 'Width': st['border_width']}},
                    'Spacing': {'Gap': st['gap']}}
            for _ in range(2):
                self.s.fmt(self.g.name, li, tree, plot=k)
                if 'Pattern/Fill/FillColor' in self.s.dump(self.g.name, li, plot=k):      # 失败时读回的是空树
                    return
                self.s.lt('doc -uw;')       # 偶尔刚画好的柱还没就绪，设置不生效：刷新后再设一次
            self.warnings.append(f'柱 {k + 1} 的颜色没设上，请检查导出图；可重新 build')
            return
        pl.color = sty['color']
        cmds = [f'-k {style.SHAPES[sty["shape"]]}', f'-kf {style.INTERIORS[sty["interior"]]}', f'-z {sty["size"]}']
        if not scatter:
            cmds += [f'-d {style.DASHES[sty["dash"]]}', f'-wp {sty["width"]}']
        pl.set_cmd(*cmds)
        tree = {} if scatter else {'Line': {'LineSymbolOrder': 2}}      # 连线画在符号后面、不在符号处断开
        if sty['interior'] != 'solid' and sty['shape'] != 'none':
            tree['Symbol'] = {'FillColor': -4}           # 无填充：空心、半填充的空白处透明
        if tree:
            self.s.fmt(self.g.name, li, tree, plot=k)

    def errbar(self, L, e, sty, bar):
        """误差棒：点线图随曲线颜色和线宽，柱状图用柱的边框色。"""
        st = self.st['errorbar']
        e.color = self.st['bar']['border'] if bar else sty['color']
        e.set_cmd(f'-wp {self.st["bar"]["border_width"] if bar else sty["width"]}')
        self.s.fmt(self.g.name, L.index(), {'ErrorBar2D': {'CapWidth': st['cap']}}, plot=e.index())

    @staticmethod
    def points(table, s):
        """有效数据点 (x, y, 误差)，没有误差棒时误差为 0。"""
        errs = table[s['yerr']] if s.get('yerr') else [0.0] * len(table[s['y']])
        return [(x, y, e if _ok(e) else 0.0) for x, y, e in zip(table[s['x']], table[s['y']], errs) if _ok(x) and _ok(y)]

    def auto_axes(self, p, series, table, bar):
        xs = [v for s in series for v in table[s['x']] if _ok(v)]
        ys = [v for s in series for _, y, e in self.points(table, s) for v in (y - e, y + e)]
        if not xs or not ys:
            raise ValueError('曲线数据里没有数值')
        if bar and p.get('mode') == 'stacked':
            n = len(table[series[0]['y']])
            ys = [sum(table[s['y']][r] for s in series if _ok(table[s['y']][r])) for r in range(n)]
        step = p['x'].get('step') or (1 if p['x'].get('labels') else None)      # 分类横轴每个类别一个刻度
        if bar and not step:
            ux = sorted(set(xs))
            step = round(min((b - a for a, b in zip(ux, ux[1:])), default=0), 10) or None     # 每簇一个刻度
        xa = layout.x_axis(_unique(xs), step)
        ya = layout.y_axis(min(ys + ([0.0] if bar else [])), max(ys), p['y'].get('step'),
                           target=self.st['axis'].get('y_ticks', 5), baseline=0.0 if bar else None)
        for a, d, vals in (('x', xa, xs), ('y', ya, ys)):
            if p[a].get('scale') == 'log':
                # 对数轴：范围取整十倍，每十倍一个刻度，刻度值写成 10^n
                pos = [v for v in vals if v > 0]
                if not pos:
                    raise ValueError(f'{a} 轴设为对数，但数据里没有正数')
                d.update({'from': 10.0 ** math.floor(math.log10(min(pos))), 'to': 10.0 ** math.ceil(math.log10(max(pos))),
                          'step': 1, 'log': True, 'fixed': True})
        for a, d in (('x', xa), ('y', ya)):
            user = p[a]
            if d.get('log'):
                if user.get('range'):
                    d['from'], d['to'] = user['range']
                d.update({'first': d['from'], 'decimals': 0})
                continue
            if user.get('range'):
                d['from'], d['to'] = user['range']
                d['fixed'] = True
            if user.get('step'):
                d['step'] = user['step']
            d['first'] = user.get('first', self.aligned_first(xs, d) if a == 'x' else layout.first_tick(d['from'], d['step']))
            fine = [d['step']] + ([user['break']['step']] if (user.get('break') or {}).get('step') else [])
            fac = user.get('factor', self.st['axis'].get('factor')) if a == 'y' else None
            if fac == 'auto':
                # 数值上万时刻度值除以 10ⁿ，只留一两位整数（如 32 ×10⁵）
                big = max(abs(d['from']), abs(d['to']))
                fac = math.floor(math.log10(big)) - 1 if big >= 1e4 else None
            if fac:
                d['factor'] = int(fac)
                fine = [v / 10 ** fac for v in fine]
            d['decimals'] = user.get('decimals', max(layout.decimals(round(v, 12)) for v in fine))
        brk = p['y'].get('break')
        if brk and 'at' not in brk:
            a, b = brk['from'] - ya['from'], ya['to'] - brk['to']
            if brk.get('step') and abs(brk['step'] - ya['step']) > 1e-12:
                brk['at'] = 0.6         # 上下两段刻度间距不同（两种量级），按比例尺一致会把一段压没，下段（细节）多占一些
            elif a > 0 and b > 0:
                brk['at'] = round(min(max(a / (a + b), 0.25), 0.8), 4)      # 上下两段比例尺一致
        return xa, ya

    @staticmethod
    def aligned_first(xs, d):
        """数据横坐标等距、且与刻度间距成整数倍时，刻度对齐到数据点（如 15, 45, 75…；180, 300, 420…）。"""
        ux, step = sorted(set(xs)), d['step']
        whole = lambda v: abs(v - round(v)) < 1e-6
        if len(ux) > 1:
            dx = min(b - a for a, b in zip(ux, ux[1:]))
            if all(whole((u - ux[0]) / dx) for u in ux) and (whole(step / dx) or whole(dx / step)):
                return round(ux[0] - math.floor((ux[0] - d['from']) / step + 1e-9) * step, 12)
        return layout.first_tick(d['from'], step)

    def axes(self, L, xa, ya, p, size=None, ticks=None, title_size=None):
        st, f = self.st, self.font
        ax = st['axis']
        title_size = title_size or size or st['font']['title']
        size = size or st['font']['size']
        tk = {'in': 1, 'out': 2, 'none': 0}[ticks or ax['ticks']]
        cmds = [f'layer.tickL={ax["tick_length"]}; layer.tickW={ax["tick_width"]};']
        for a, d in (('x', xa), ('y', ya)):
            cmds.append(f'layer.{a}.from={d["from"]}; layer.{a}.to={d["to"]}; layer.{a}.inc={d["step"]}; '
                        f'layer.{a}.firstTick={d["first"]}; layer.{a}.minorTicks={ax["minor"]}; layer.{a}.ticks={tk}; '
                        f'layer.{a}2.ticks=0; layer.{a}.showAxes=3; layer.{a}.showLabels=1; '
                        f'layer.{a}.label.font={f}; layer.{a}.label.pt={size}; layer.{a}.label.numFormat=1; '
                        f'layer.{a}.label.decPlaces={d["decimals"]}; layer.{a}.thickness={ax["thickness"]}; '
                        f'layer.{a}2.thickness={ax["thickness"]};')
        L.lt_exec(' '.join(cmds))
        for a, d in (('x', xa), ('y', ya)):
            if d.get('log'):
                L.lt_exec(f'layer.{a}.type=2; layer.{a}.labelSubtype=2; layer.{a}.from={d["from"]}; layer.{a}.to={d["to"]}; '
                          f'layer.{a}.inc=1; layer.{a}.firstTick={d["from"]};')
        brk = p['y'].get('break')
        if brk:
            L.lt_exec(f'layer.y.breaks.enable=1; layer.y.breaks.count=1; layer.y.break1.from={brk["from"]}; '
                      f'layer.y.break1.to={brk["to"]}; layer.y.break1.pos={brk.get("at", 0.5) * 100};'
                      + (f' layer.y.break1.inc={brk["step"]};' if brk.get('step') else ''))
        for a, obj in (('x', 'xb'), ('y', 'yl')):
            title = p[a].get('title')
            if title:
                self.s.set_str('__t$', self.rich(title))
                L.lt_exec(f'label -{obj} "x"; {obj}.text$ = __t$; {obj}.font={f}; {obj}.fsize={title_size};')
            else:
                L.lt_exec(f'label -r {obj};')
        L.lt_exec('label -r xt; label -r yr;')      # 模板里上、右轴的标题（框线显示后会冒出来）

    def grid(self, L, p):
        """主刻度网格线：预设 axis.grid（如 JSAC 风格的浅灰短虚线），面板里 x/y.grid 可开关或覆盖。柱状图默认不画竖线。"""
        g = self.st['axis'].get('grid')
        for a, node, sub in (('x', 'X', 'VerticalMajorGrids'), ('y', 'Y', 'HorizontalMajorGrids')):
            on = p[a].get('grid', bool(g) and not (p['type'] == 'bar' and a == 'x'))
            if not on:
                continue
            gs = {**(g or {}), **(on if isinstance(on, dict) else {})}
            self.s.fmt(self.g.name, L.index(), {'Axes': {node: {'Grids': {sub: {
                'Show': 1, 'Color': self.op.ocolor(gs.get('color', '#D0D3D4')),
                'Style': style.DASHES[gs.get('style', 'short_dash')], 'Width': gs.get('width', 0.4)}}}}})

    def factor_label(self, L, ya, frame, side):
        """刻度值除以 10ⁿ 显示，框上方写 ×10ⁿ（JSAC 文献的做法）。"""
        n = ya.get('factor')
        if not n:
            return
        labels = 'LeftLabels' if side == 'left' else 'RightLabels'
        self.s.fmt(self.g.name, L.index(), {'Axes': {'Y': {'Labels': {labels: {'DivideByFactor': f'1E{n}'}}}}})
        nm = self.text(L, f'×10\\+({n})', self.st['font']['size'])
        x = frame[0] if side == 'left' else frame[0] + frame[2]
        self.at_page(L, [(nm, x, frame[1] - 0.04, 'lb' if side == 'left' else 'rb')])

    # ---------- 图例 ----------
    def legend_text(self, p, series, number, ncol=None):
        lg = p.get('legend') or {}
        if lg.get('text'):
            return lg['text']
        names = _unique(s.get('name') for s in series)
        groups = _unique(s.get('group') for s in series if s.get('group') is not None)
        cell = lambda k, label: f'\\l({number[k]}) {label}'.rstrip()
        if len(groups) > 1 and len(names) > 1 and self.brace_layout(p):
            # 一列，按 group 依次列出；组名由右侧的大括号标出（见 legend()）
            return '\n'.join(cell(k, s.get('name')) for g in groups for k, s in enumerate(series) if s.get('group') == g)
        if len(groups) > 1 and len(names) > 1:
            # 矩阵式：每行一个 group（行首为组名），每列一个 name；transpose 时反过来。
            # 制表符分列，各列内容同宽时 Origin 自动对齐（表头行与色块列对不齐，所以不做表头式）
            transpose = lg.get('transpose')
            rows_by, cols_by = ('name', 'group') if transpose else ('group', 'name')
            heads, items = (names, groups) if transpose else (groups, names)
            rows = []
            for h in heads:
                row = [str(h)]
                for it in items:
                    ks = [k for k, s in enumerate(series) if s.get(rows_by) == h and s.get(cols_by) == it]
                    row.append(cell(ks[0], it) if ks else '')
                rows.append('\t'.join(row))
            return '\n'.join(rows)
        label = (lambda s: s.get('group')) if len(groups) > 1 else (lambda s: s.get('name'))
        entries = [cell(k, label(s)) for k, s in enumerate(series)]
        # 柱状图的色块和字一样高，多行时容易挤，放得下就排成一行（太宽时会缩小字号或报警告）
        default = len(entries) if len(entries) <= (6 if p['type'] == 'bar' else 3) else 2 if len(entries) == 4 else 3
        ncol = ncol or lg.get('columns') or self.st['legend'].get('columns') or default
        return '\n'.join('\t'.join(entries[r:r + ncol]) for r in range(0, len(entries), ncol))

    def brace_layout(self, p):
        return (p.get('legend') or {}).get('layout', self.st['legend'].get('layout', 'matrix')) == 'brace'

    def legend(self, L, i, p, series, number, frame, xa, ya, bar, shapes, fixed=False, host=None, auto=None, ncol=None):
        """host：图例对象所在的图层（右纵轴的图例放在右轴图层里），缺省为 L；位置一律按 L 的坐标计算。"""
        lgst = self.st['legend']
        lg = p.get('legend') or {}
        host = host or L
        li = host.index()
        host.lt_exec('legendupdate mode:=0;')
        self.legends[li] = (host, self.rich(self.legend_text(p, series, number, ncol)))
        self.s.set_str('__t$', self.legends[li][1])
        host.lt_exec(f'legend.text$ = __t$; legend.font = {self.font}; legend.background = 0;')
        tree = {'TabWidth': lgst['tab'], 'Symbol': {'LegendSymbolWidth': -lgst['symbol_width']}}
        if lgst.get('line_space') is not None:
            tree.update({'LineSpaceAuto': 0, 'LineSpace': lgst['line_space']})
        frame_st = lg.get('frame', lgst.get('frame'))
        if frame_st:
            # 带边框、白底的图例（JSAC 风格），盖住背后的网格线
            fs = frame_st if isinstance(frame_st, dict) else {}
            host.lt_exec('legend.background = 1;')
            tree['Background'] = {'Border': {'Color': self.op.ocolor(fs.get('color', '#231F20')), 'Width': fs.get('width', 0.4),
                                             'Style': style.DASHES[fs.get('style', 'solid')]},
                                  'Fill': {'Color': self.op.ocolor('#FFFFFF')}}
        self.s.fmt(self.g.name, li, tree, obj='Legend')
        W, H = frame[2], frame[3]
        size = lg.get('size', lgst['size'])
        while True:
            host.lt_exec(f'legend.fsize = {size};')
            self.s.lt('doc -uw;')
            _, _, lw, lh = self.box(host, 'legend')
            if lw + 2 * lgst['side_gap'] <= W or size - 0.5 < lgst['min_size'] or 'size' in lg:
                break
            size -= 0.5        # 太宽时逐步缩小字号，不低于 min_size
        groups = _unique(s.get('group') for s in series if s.get('group') is not None)
        brace = self.brace_layout(p) and len(groups) > 1 and len(_unique(s.get('name') for s in series)) > 1
        tw = lw
        if brace:
            bst = lgst.get('brace') or {}
            row, pad = self.legend_rows(L, li, lh, len(series))
            labels = [self.text(L, g, bst.get('size', size + 1)) for g in groups]
            self.s.lt('doc -uw;')
            wl = max(self.box(L, nm)[2] for nm in labels)
            bw, gap = bst.get('width', 0.1), bst.get('gap', 0.06)
            tw = lw + 2 * gap + bw + wl          # 图例框 + 大括号 + 组名
            parts, k = [(0.0, 0.0, lw, lh)], 0
            for g, nm in zip(groups, labels):
                # 大括号是一条窄带，组名只占组中间的一行高
                n = sum(1 for s in series if s.get('group') == g)
                _, _, wg, hg = self.box(L, nm)
                parts += [(lw + gap, pad + k * row, bw, n * row), (lw + 2 * gap + bw, pad + (k + n / 2) * row - hg / 2, wg, hg)]
                k += n
        info = {'size_pt': size, 'width_cm': round(tw, 2), 'height_cm': round(lh, 2)}
        if tw + 2 * lgst['side_gap'] > W:
            self.warnings.append(f'面板 {i}：图例宽 {tw:.2f} cm，超出框宽 {W} cm；可减少每行条目（legend.columns）、'
                                 '缩短名称或加宽面板')
        brk = p['y'].get('break')
        yr, xr, step = (ya['from'], ya['to']), (xa['from'], xa['to']), ya['step']
        if brk:
            shapes = [self.frac_shape(sh, ya, brk) for sh in shapes]    # 断轴时按框内高度比例算，不改纵轴
            yr, step = (0.0, 1.0), None
        if ya.get('log') or xa.get('log'):
            shapes = [self.log_shape(sh, xa.get('log'), ya.get('log')) for sh in shapes]
            lg10 = lambda r, on: tuple(math.log10(v) for v in r) if on else r
            yr, xr, step = lg10(yr, ya.get('log')), lg10(xr, xa.get('log')), None
        placed = layout.place_legend((W, H), xr, yr, shapes, (tw, lh), pos=lg.get('pos', 'auto'),
                                     parts=parts if brace else None,
                                     margin=lgst['margin'], side_gap=lgst['side_gap'], clear=lgst['clear'], step=step,
                                     fixed=bool(ya.get('fixed') or brk or fixed), floor=0.0 if bar else None,
                                     auto=auto or lgst.get('auto', ('bottom', 'top')))
        if placed['extended']:
            y0, y1 = placed['y']
            L.lt_exec(f'layer.y.from={y0}; layer.y.to={y1}; layer.y.firstTick={layout.first_tick(y0, ya["step"])};')
        cx, cy = layout.legend_center((W, H), placed['y'], placed, (tw, lh), lgst['margin'])
        cx, cy = cx + lg.get('dx', 0), cy + lg.get('dy', 0)
        left, top = frame[0] + cx - tw / 2, frame[1] + H - cy - lh / 2
        obj = host.label('legend')
        obj.set_int('left', self.dots(left))
        obj.set_int('top', self.dots(top))
        if brace:
            # 每组的行右侧画大括号，括号尖端右边写组名
            k, xb = 0, left + lw + gap
            color, width = bst.get('color', INK), bst.get('line_width', 0.4)
            items = []
            for g, nm in zip(groups, labels):
                n = sum(1 for s in series if s.get('group') == g)
                y0c, y1c = top + pad + k * row + 0.12 * row, top + pad + (k + n) * row - 0.12 * row
                self.polyline(L, frame, layout.brace_points(xb, y0c, y1c, bw), xa, ya, brk, color, width)
                items.append((nm, xb + bw + gap, (y0c + y1c) / 2, 'lc'))
                k += n
            self.at_page(L, items)
        if placed['overlap']:
            self.warnings.append(f'面板 {i}：图例与数据重叠（{placed["pos"]}），可设 legend.pos / dx / dy，或放宽坐标范围')
        info.update({k: placed[k] for k in ('pos', 'offset', 'extended', 'overlap')})
        info['box_cm'] = [round(v, 3) for v in (left, top, tw, lh)]
        return info

    def legend_rows(self, L, li, lh, n):
        """图例每行的高度和上下内边距：去掉最后一行再量一次高度。"""
        text = self.legends[li][1]
        self.s.set_str('__t$', text.rsplit('\n', 1)[0])
        L.lt_exec('legend.text$ = __t$;')
        self.s.lt('doc -uw;')
        lh2 = self.box(L, 'legend')[3]
        self.s.set_str('__t$', text)
        L.lt_exec('legend.text$ = __t$;')
        self.s.lt('doc -uw;')
        row = lh - lh2
        return row, (lh - n * row) / 2

    def occupancy(self, p, series, styles, xa, bar):
        """数据在图里占的位置：折线（点上带符号半径，cm）或柱（每根柱的矩形）。"""
        table = p['table']
        if bar:
            total = xa['step'] * (1 - self.st['bar']['gap'] / 100)       # 一簇的宽度
            mode = p.get('mode', 'grouped')
            if mode == 'stacked':
                return [('rect', x - total / 2, x + total / 2, 0.0,
                         sum(table[s['y']][r] for s in series if _ok(table[s['y']][r])))
                        for r, x in enumerate(table[series[0]['x']])]
            # 每根柱单独占位：分组时簇内依次排开；重叠时各 group 内按 name 排开
            names = _unique(s.get('name') for s in series)
            slots = len(names) if mode == 'overlap' else len(series)
            out = []
            for k, s in enumerate(series):
                j = names.index(s.get('name')) if mode == 'overlap' else k
                for x, y, e in self.points(table, s):
                    a = x - total / 2 + j * total / slots
                    out.append(('rect', a, a + total / slots, 0.0, y + e))
            return out
        out = []
        for s, sty in zip(series, styles):
            pts = self.points(table, s)
            r = sty['size'] * PT / 2 + 0.03 if sty['shape'] != 'none' else 0.02
            out.append(('line', [x for x, _, _ in pts], [y for _, y, _ in pts], r))
            out += [('rect', x, x, y - e, y + e) for x, y, e in pts if e]       # 误差棒当作细竖条
        return out

    @staticmethod
    def log_shape(sh, logx, logy):
        f = lambda v, on: math.log10(v) if on and v > 0 else (-99.0 if on else v)
        if sh[0] == 'rect':
            return ('rect', f(sh[1], logx), f(sh[2], logx), f(sh[3], logy), f(sh[4], logy))
        return ('line', [f(v, logx) for v in sh[1]], [f(v, logy) for v in sh[2]], sh[3])

    @staticmethod
    def frac_shape(sh, ya, brk):
        """断轴：数据值换成框内高度比例（断开区间压到断点处）。"""
        lo, hi, a, b, pos = ya['from'], ya['to'], brk['from'], brk['to'], brk.get('at', 0.5)

        def f(y):
            if y <= a:
                return (y - lo) / (a - lo) * pos
            if y >= b:
                return pos + (y - b) / (hi - b) * (1 - pos)
            return pos
        if sh[0] == 'rect':
            return ('rect', sh[1], sh[2], f(sh[3]), f(sh[4]))
        return ('line', sh[1], [f(y) for y in sh[2]], sh[3])

    # ---------- 插图与标注 ----------
    def inset(self, L, p, series, styles, frame, wks, idx):
        ins = p['inset']
        (x0, x1), (y0, y1) = ins['x'], ins['y']
        xs, ys = ins.get('xstep') or layout.nice_step(x1 - x0, 2), ins.get('ystep') or layout.nice_step(y1 - y0, 4)
        xa = {'from': x0, 'to': x1, 'step': xs, 'first': layout.first_tick(x0, xs), 'decimals': layout.decimals(xs)}
        ya = {'from': y0, 'to': y1, 'step': ys, 'first': layout.first_tick(y0, ys), 'decimals': layout.decimals(ys)}
        titles = ins.get('titles', True)
        # box 是插图连同刻度值、标题所占的区域（框内比例）；坐标框再让出左侧和下方的文字位置，
        # 免得刻度值和标题伸出主图框压到主图的刻度
        size = self.st['inset']['size'] * PT
        title = 1.15 * size + 0.06 if titles else 0.0
        digits = max(len(f'{v:.{ya["decimals"]}f}') for v in (y0, y1))
        ml, mb = digits * 0.5 * size + 0.1 + title, 1.15 * size + 0.1 + title
        bx = ins.get('box', [0.02, 0.4, 0.5, 0.38])
        left, top = frame[0] + bx[0] * frame[2] + ml, frame[1] + bx[1] * frame[3]
        w, h = bx[2] * frame[2] - ml, bx[3] * frame[3] - mb
        IL = self.new_layer((left, top, w, h))
        for k in ins.get('series') or range(len(series)):
            pl = IL.add_plot(wks, idx[series[k]['y']], idx[series[k]['x']], type='y')
            self.plot_style(IL, pl, styles[k], False, False)
        sub = {'x': {'title': p['x'].get('title') if titles else None}, 'y': {'title': p['y'].get('title') if titles else None}}
        self.axes(IL, xa, ya, sub, size=self.st['inset']['size'])
        IL.lt_exec(f'layer.tickL={self.st["inset"]["tick_length"]}; label -r legend;')
        self.insets.append(IL)
        X0, X1, Y0, Y1 = self.ranges(L)
        to_x = lambda c: X0 + (c - frame[0]) / frame[2] * (X1 - X0)
        to_y = lambda c: Y1 - (c - frame[1]) / frame[3] * (Y1 - Y0)
        info = {'frame_cm': [round(v, 3) for v in (left, top, w, h)],
                'frame_data': [round(to_x(left), 6), round(to_x(left + w), 6), round(to_y(top + h), 6), round(to_y(top), 6)]}
        if not ins.get('mark', True):
            return info
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2 * 1.15, (y1 - y0) / 2 * 1.15
        info['ellipse'] = {'center': [cx, cy], 'radius': [rx, ry]}
        self.mark(L, {'type': 'ellipse', 'center': [cx, cy], 'radius': [rx, ry], 'dash': 'dash', 'color': '#404040',
                      'width': 0.5}, frame)
        if ins.get('arrow', True):
            # 箭头从虚线圈指向 arrow_to（数据坐标），缺省为插图框离它最近的角
            corners = [(to_x(a), to_y(b)) for a in (left, left + w) for b in (top, top + h)]
            tx, ty = ins.get('arrow_to') or min(corners, key=lambda c: ((c[0] - cx) / rx) ** 2 + ((c[1] - cy) / ry) ** 2)
            d = math.hypot((tx - cx) / rx, (ty - cy) / ry)
            self.segment(L, cx + (tx - cx) / d, cy + (ty - cy) / d, tx, ty, '#404040', 0.5, arrow=True)
            info['arrow_to'] = [tx, ty]
        return info

    def inside(self, L, nm, frame, i, text):
        """文字对象伸出坐标框时给出警告（括注贴在右边框外是常见情况）。"""
        self.s.lt('doc -uw;')
        l, t, w, h = self.box(L, nm)
        tol = 0.05      # 文字对象的框自带一点内边距
        if l < frame[0] - tol or t < frame[1] - tol or l + w > frame[0] + frame[2] + tol or t + h > frame[1] + frame[3] + tol:
            self.warnings.append(f'面板 {i}：标注“{text}”伸出了坐标框，可调 dx / side / at，或放宽坐标范围')

    def mark(self, L, mk, frame, i=0):
        st = self.st['mark']
        kind, color = mk.get('type'), mk.get('color', INK)
        width, dash = mk.get('width', st['width']), style.DASHES[mk.get('dash', 'solid')]
        if kind == 'bracket':
            # 竖线两端带短横，数值竖排在一侧（参考图的提升百分比标注）
            x, (y1, y2) = mk['x'], mk['y']
            X0, X1, _, _ = self.ranges(L)
            per_cm = (X1 - X0) / frame[2]
            cap = mk.get('cap', 0.08) * per_cm
            if mk.get('style') == 'arrow':
                # 双向箭头（JSAC 文献标提升百分比的写法），文字默认横排
                self.segment(L, x, y1, x, y2, color, width, arrow='both', head=(2.5, 4))
            else:
                self.segment(L, x, y1, x, y2, color, width)
                for y in (y1, y2):
                    self.segment(L, x - cap, y, x + cap, y, color, width)
            if mk.get('text'):
                side = 1 if mk.get('side', 'right') == 'right' else -1
                rot = mk.get('rotate', 0 if mk.get('style') == 'arrow' else 90)
                nm = self.text(L, mk['text'], mk.get('size', st['size']), color, rotate=rot)
                if rot == 0:
                    px, py = self.to_page(L, frame, x, (y1 + y2) / 2)
                    self.at_page(L, [(nm, px + side * mk.get('dx', 0.06), py, 'lc' if side > 0 else 'rc')])
                else:
                    self.at_data(L, nm, x + side * mk.get('dx', 0.16) * per_cm, (y1 + y2) / 2)
                self.inside(L, nm, frame, i, mk['text'])
        elif kind == 'text':
            nm = self.text(L, mk['text'], mk.get('size', st['size']), color, mk.get('rotate', 0))
            self.at_data(L, nm, *mk['at'])
            self.inside(L, nm, frame, i, mk['text'])
        elif kind in ('line', 'arrow'):
            self.segment(L, *mk['from'], *mk['to'], color, width, dash, arrow=kind == 'arrow')
        elif kind == 'rect':
            (xa, ya), (xb, yb) = mk['from'], mk['to']
            corners = [(xa, ya), (xb, ya), (xb, yb), (xa, yb), (xa, ya)]
            for (p, q), (r, s) in zip(corners, corners[1:]):
                self.segment(L, p, q, r, s, color, width, dash)
        elif kind == 'ellipse':
            # 用短线段拼成（虚线时隔一段画一段）：不是数据曲线，不会混进图例、也不影响坐标范围
            (cx, cy), (rx, ry) = mk['center'], mk['radius']
            pts = [(cx + rx * math.cos(2 * math.pi * k / 72), cy + ry * math.sin(2 * math.pi * k / 72)) for k in range(73)]
            for k, ((a, b), (c, d)) in enumerate(zip(pts, pts[1:])):
                if dash == 0 or k % 2 == 0:
                    self.segment(L, a, b, c, d, color, width)
        else:
            raise ValueError(f'marks 的 type 不认识：{kind!r}（可用 bracket / text / line / arrow / ellipse / rect）')

    # ---------- 子图标题 ----------
    def below_axis(self, p, title=True):
        """横轴刻度值（和标题）下沿距框底的距离（cm），按字号估算（Origin 不给轴标题的可靠页面坐标）。"""
        size, tsize = self.st['font']['size'] * PT, self.st['font']['title'] * PT
        ticks_out = self.st['axis']['tick_length'] * PT if (self.st['heatmap']['ticks'] if p['type'] == 'heatmap'
                                                             else self.st['axis']['ticks']) == 'out' else 0
        return ticks_out + 0.06 + 1.15 * size + ((0.08 + 1.15 * tsize) if title else 0)

    def captions(self, layers, frames):
        for k, (L, p, frame) in enumerate(zip(layers, self.spec['panels'], frames)):
            if not p.get('caption'):
                continue
            bottom = self.xtitle_bottom.get(k, frame[1] + frame[3] + self.below_axis(p, bool(p['x'].get('title'))))
            nm = self.text(L, p['caption'], self.st['caption']['size'])
            self.at_page(L, [(nm, frame[0] + frame[2] / 2, bottom + self.st['caption']['gap'], 'ct')])

    # ---------- 输出 ----------
    def export(self):
        out = self.spec['output']
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        self.op.save(out + '.opju')
        return [out + '.opju'] + export_graph(self.g, out, self.spec['formats'], self.spec['dpi'], self.page[0])


def export_graph(g, out, formats, dpi, width_cm):
    """导出图页：PNG 按页面宽度和 dpi 定像素并写入 dpi 信息；TIF/JPG 由 PNG 转出；PDF/SVG/EMF/EPS 为矢量。"""
    from PIL import Image
    png = out + '.png'
    if not g.save_fig(png, width=round(width_cm / 2.54 * dpi)):
        raise RuntimeError(f'导出失败：{png}')
    with Image.open(png) as im:
        im = im.convert('RGB')
    im.save(png, dpi=(dpi, dpi))
    files = [png]
    for f in formats:
        path = f'{out}.{f}'
        if f == 'png':
            continue
        if f == 'tif':
            im.save(path, dpi=(dpi, dpi), compression='tiff_lzw')
        elif f == 'jpg':
            im.save(path, dpi=(dpi, dpi), quality=95)
        elif not g.save_fig(path):
            raise RuntimeError(f'导出失败：{path}')
        files.append(path)
    return files
