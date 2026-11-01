"""审美规则：给每条曲线/柱分配颜色、符号形状、填充、大小和线型（纯 Python，不依赖 Origin）。

规则学自参考图（折线图/1、2）：
- 系列有两个维度：name（方法）和 group（参数/场景）。形状跟 name 走；
- group 递进时颜色变深、符号变大、内部变空（实心 → 上半 → 下半 → 空心），线型依次为
  Solid → Short Dash → Short Dash Dot → Short Dot；空心/半填充的未填充部分为“无填充”（透明）。
- 配色两种：family（每个 name 一个色系，group 由浅到深）和 group（每个 group 一个色系，name 由深到浅）。
"""
from .config import load_json

# Origin 的编号：set -k 形状、-kf 内部、-d 线型
SHAPES = {'none': 0, 'square': 1, 'circle': 2, 'up': 3, 'down': 4, 'diamond': 5, 'plus': 6, 'cross': 7,
          'hbar': 9, 'vbar': 10, 'left': 15, 'right': 16, 'hexagon': 17, 'star': 18, 'pentagon': 19}
INTERIORS = {'solid': 0, 'open': 1, 'dot': 2, 'hollow': 3, 'plus': 4, 'cross': 5, 'minus': 6, 'bar': 7,
             'half_up': 8, 'half_right': 9, 'half_down': 10, 'half_left': 11}
DASHES = {'solid': 0, 'dash': 1, 'dot': 2, 'dash_dot': 3, 'dash_dot_dot': 4,
          'short_dash': 5, 'short_dot': 6, 'short_dash_dot': 7}

SHAPE_ORDER = ['diamond', 'up', 'circle', 'square', 'down', 'hexagon', 'pentagon', 'star']
DASH_ORDER = ['solid', 'short_dash', 'short_dash_dot', 'short_dot', 'dash', 'dash_dot', 'dot', 'dash_dot_dot']
# 首尾固定为实心、空心，中间的组依次用这些
MIDDLE_INTERIORS = ['half_up', 'half_down', 'half_left', 'half_right', 'dot']
STYLE_KEYS = ('color', 'shape', 'interior', 'size', 'dash', 'width')

_PALETTES = None


def palettes() -> dict:
    global _PALETTES
    if _PALETTES is None:
        _PALETTES = load_json('palettes.json')
    return _PALETTES


def hex2rgb(c: str) -> tuple:
    c = c.lstrip('#')
    if len(c) == 3:
        c = ''.join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def rgb2hex(rgb) -> str:
    return '#' + ''.join(f'{max(0, min(255, round(v))):02X}' for v in rgb)


def ramp(colors: list, n: int) -> list:
    """在多段渐变上等距取 n 个颜色（参考图的热图色标是 sRGB 线性渐变）。"""
    rgb = [hex2rgb(c) for c in colors]
    if n == 1:
        return [colors[-1]]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(rgb) - 1)
        k = min(int(t), len(rgb) - 2)
        f = t - k
        out.append(rgb2hex([a + (b - a) * f for a, b in zip(rgb[k], rgb[k + 1])]))
    return out


def shades(family: list, n: int) -> list:
    """色系里取 n 个由浅到深的颜色：不足时取最深的 n 个（最浅一档配细线印出来太淡），多于色系时插值。"""
    m = len(family)
    if n <= m:
        return family[m - n:]
    return ramp(family, n)


def family(name: str) -> list:
    fams = palettes()['families']
    if name not in fams:
        raise ValueError(f'没有色系 {name!r}，可用：{", ".join(fams)}')
    return fams[name]


def heatmap_colors(palette, n: int) -> list:
    """热图色阶：palette 为 palettes.json 里的名字或颜色列表（由浅到深）。"""
    if isinstance(palette, str):
        maps = palettes()['heatmap']
        if palette in maps:
            palette = maps[palette]
        else:
            palette = family(palette)
    return ramp(list(palette), n)


def interiors(n: int) -> list:
    if n <= 1:
        return ['solid']
    mids = [MIDDLE_INTERIORS[i % len(MIDDLE_INTERIORS)] for i in range(n - 2)]
    return ['solid'] + mids + ['open']


def _unique(values) -> list:
    out = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def encode(series: list, mode: str = 'auto', size: float = 3.0, size_step: float = 1.0, width: float = 0.37,
           families: list = None, group_order: list = None) -> list:
    """series 为 [{'name':..., 'group':..., 可选覆盖项}]，返回每条的样式字典。

    mode：family（默认，有多个 group 时）/ group / categorical（只有 name 时）。
    families：按顺序使用的色系名，缺省用 palettes.json 的 order。
    group_order：group 的递进顺序（由浅到深），缺省按出现顺序。
    """
    names = _unique(s.get('name') for s in series)
    groups = _unique(s.get('group') for s in series if s.get('group') is not None)
    if group_order:
        groups = [g for g in group_order if g in groups] + [g for g in groups if g not in group_order]
    multi = len(groups) > 1
    if mode == 'auto':
        mode = 'family' if multi or len(names) == 1 else 'categorical'
    if mode not in ('family', 'group', 'categorical'):
        raise ValueError(f'encode.color 只能是 family / group / categorical，收到 {mode!r}')
    order = families or palettes()['order']['group' if mode == 'group' else 'family']
    fills, ng = interiors(len(groups)), max(len(groups), 1)
    out = []
    for s in series:
        ni = names.index(s.get('name'))
        gi = groups.index(s['group']) if s.get('group') in groups else 0
        if mode == 'group':
            color = list(reversed(shades(family(order[gi % len(order)]), len(names))))[ni]
        elif mode == 'family' and (multi or len(names) == 1):
            color = shades(family(order[ni % len(order)]), ng)[gi]
        else:
            fam = family(order[ni % len(order)])
            color = fam[max(len(fam) - 2, 0)]
        style = {'color': color, 'shape': SHAPE_ORDER[ni % len(SHAPE_ORDER)],
                 'interior': fills[gi] if multi else 'solid',
                 'size': size + size_step * (gi if multi else 1),
                 'dash': DASH_ORDER[gi % len(DASH_ORDER)] if multi else 'solid',
                 'width': width}
        style.update({k: s[k] for k in STYLE_KEYS if s.get(k) is not None})
        check(style)
        out.append(style)
    return out


def check(style: dict):
    for key, table in (('shape', SHAPES), ('interior', INTERIORS), ('dash', DASHES)):
        if style[key] not in table:
            raise ValueError(f'{key} 不认识 {style[key]!r}，可用：{", ".join(table)}')
    hex2rgb(style['color'])
