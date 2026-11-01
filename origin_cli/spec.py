"""读取 spec：合并预设、加载数据（内联 / CSV / XLSX）、补默认值、检查常见错误。"""
import copy
import json
import math
from pathlib import Path

from .config import SKILL_DIR

KINDS = ('line', 'scatter', 'bar', 'heatmap')
FORMATS = ('png', 'tif', 'jpg', 'pdf', 'svg', 'emf', 'eps')


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def load_preset(name: str, base: Path) -> dict:
    path = Path(name) if name.endswith('.json') else SKILL_DIR / 'presets' / f'{name}.json'
    if not path.is_absolute():
        path = (base / path) if name.endswith('.json') else path
    if not path.exists():
        raise ValueError(f'找不到预设 {name}（presets/ 下有：{", ".join(p.stem for p in (SKILL_DIR / "presets").glob("*.json"))}）')
    return json.loads(path.read_text(encoding='utf-8'))


def _num(v):
    if v is None or (isinstance(v, str) and v.strip() == ''):
        return math.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def load_table(data, base: Path) -> dict:
    """返回 {列名: [值...]}（保持列顺序）。data 为内联字典，或 CSV/XLSX 路径（xlsx 可写成 文件.xlsx#工作表）。"""
    if data is None:
        raise ValueError('面板缺少 data（内联 {列名: [数值]} 或 CSV/XLSX 路径）')
    if isinstance(data, dict):
        cols = {str(k): list(v) if isinstance(v, (list, tuple)) else [v] for k, v in data.items()}
    else:
        import pandas as pd
        name, _, sheet = str(data).partition('#')
        path = Path(name) if Path(name).is_absolute() else base / name
        if not path.exists():
            raise ValueError(f'数据文件不存在：{path}')
        if path.suffix.lower() in ('.xlsx', '.xls'):
            df = pd.read_excel(path, sheet_name=sheet or 0)
        else:
            df = pd.read_csv(path, encoding='utf-8-sig')
        cols = {str(c): df[c].tolist() for c in df.columns}
    return {k: [_num(v) for v in vals] for k, vals in cols.items()}


def _expand(m):
    """name × group 的简写：{"names": [...], "groups": [...], "col": "{name}_{group}", "label": "η = {group}"}
    展开成 series（先按 group、再按 name）。"""
    if not m:
        return None
    col, label, err = m.get('col', '{name}_{group}'), m.get('label', '{group}'), m.get('yerr')
    return [{'y': col.format(name=n, group=g), 'name': n, 'group': label.format(name=n, group=g),
             **({'yerr': err.format(name=n, group=g)} if err else {})}
            for g in m['groups'] for n in m['names']]


def _xy_panel(p: dict, i: int, base: Path, shared):
    table = load_table(p.get('data', shared), base)
    names = list(table)
    p['x'] = dict(p.get('x') or {})
    xcol = p['x'].setdefault('col', names[0])
    if xcol not in table:
        raise ValueError(f'面板 {i}：横轴列 {xcol!r} 不在数据里（有：{", ".join(names)}）')
    if any(isinstance(v, str) for v in table[xcol]):
        # 分类横轴：数值换成位置 1..n，文字留作刻度标签（Origin 对文本 X 列也是按行号定位）
        p['x']['labels'] = [str(v) for v in table[xcol]]
        table[xcol] = [float(k + 1) for k in range(len(table[xcol]))]
    series = p.get('series') or _expand(p.get('matrix')) or [{'y': c} for c in names if c != xcol]
    out = []
    for k, s in enumerate(series):
        s = dict(s) if isinstance(s, dict) else {'y': s}
        s.setdefault('x', xcol)
        for key in ('y', 'x', 'yerr'):
            if (key == 'y' or s.get(key) is not None) and s.get(key) not in table:
                raise ValueError(f'面板 {i} 第 {k + 1} 条曲线：{key} 列 {s.get(key)!r} 不在数据里（有：{", ".join(names)}）')
            if s.get(key) is not None and len(table[s[key]]) != len(table[s['y']]):
                raise ValueError(f'面板 {i}：列 {s[key]!r} 与 {s["y"]!r} 长度不同')
        s.setdefault('name', s['y'])
        out.append(s)
    p['series'], p['table'] = out, table
    p['y'] = dict(p.get('y') or {})


def _heatmap_panel(p: dict, i: int, base: Path, shared):
    if 'values' not in p:
        table = load_table(p.get('data', shared), base)
        names = list(table)
        p['rows'] = p.get('rows') or [str(v) for v in table[names[0]]]
        p['cols'] = p.get('cols') or names[1:]
        p['values'] = [[table[c][r] for c in names[1:]] for r in range(len(p['rows']))]
    values = p['values']
    nr, nc = len(values), len(values[0]) if values else 0
    if not nr or any(len(r) != nc for r in values):
        raise ValueError(f'面板 {i}：heatmap 的 values 必须是行列齐整的二维数组')
    p.setdefault('rows', [str(k + 1) for k in range(nr)])
    p.setdefault('cols', [str(k + 1) for k in range(nc)])
    if len(p['rows']) != nr or len(p['cols']) != nc:
        raise ValueError(f'面板 {i}：rows/cols 个数与 values 不符（{nr}×{nc}）')
    p['x'], p['y'] = dict(p.get('x') or {}), dict(p.get('y') or {})


def load(path) -> dict:
    path = Path(path).resolve()
    spec = json.loads(path.read_text(encoding='utf-8'))
    base = path.parent
    spec['style'] = merge(load_preset(spec.get('preset', 'paper'), base), spec.get('style'))
    out = Path(spec.get('output') or path.with_suffix('').name)
    out = out if out.is_absolute() else base / out
    if out.suffix.lower().lstrip('.') in FORMATS + ('opju',):
        out = out.with_suffix('')       # 只去掉图片/工程扩展名，fig_eta0.6 这类名字保持原样
    spec['output'] = str(out)
    spec['formats'] = [f.lower().lstrip('.') for f in spec.get('formats') or ['png']]
    for f in spec['formats']:
        if f not in FORMATS:
            raise ValueError(f'formats 不支持 {f!r}（可用：{", ".join(FORMATS)}）')
    if 'png' not in spec['formats']:
        spec['formats'].insert(0, 'png')
    spec['dpi'] = int(spec.get('dpi', 600))
    panels = spec.get('panels')
    if not panels:
        raise ValueError('spec 里没有 panels')
    spec['layout'] = dict(spec.get('layout') or {})
    spec['layout'].setdefault('rows', [1] * len(panels))
    for i, p in enumerate(panels):
        p.setdefault('type', 'line')
        if p['type'] not in KINDS:
            raise ValueError(f'面板 {i}：type 只能是 {"/".join(KINDS)}')
        (_heatmap_panel if p['type'] == 'heatmap' else _xy_panel)(p, i, base, spec.get('data'))
    return spec
