"""不需要 Origin 的单元测试：审美分配、坐标范围、排版、图例避让、spec 读取。"""
import json

import pytest

from origin_cli import layout, spec, style


def series(names, groups):
    return [{'y': f'{n}_{g}', 'name': n, 'group': g} for g in groups for n in names]


# ---------- 审美分配 ----------

def test_family_mode_matches_reference_line_chart_1():
    """折线图/1：每种方法一个色系，ω 由小到大颜色变深、符号变大、内部变空、线型依次变化。"""
    st = style.encode(series(['DA-KSE', 'B1', 'B2'], [10, 20, 30, 40]))
    blue = style.palettes()['families']['blue']
    assert [s['color'] for s in st if s['shape'] == 'diamond'] == blue
    assert [s['interior'] for s in st[::3]] == ['solid', 'half_up', 'half_down', 'open']
    assert [s['size'] for s in st[::3]] == [3, 4, 5, 6]
    assert [s['dash'] for s in st[::3]] == ['solid', 'short_dash', 'short_dash_dot', 'short_dot']
    assert {s['shape'] for s in st[:3]} == {'diamond', 'up', 'circle'}
    assert all(s['width'] == 0.37 for s in st)


def test_group_mode_matches_reference_line_chart_2():
    """折线图/2：每种 η 一个色系，方法在色系内由深到浅。"""
    st = style.encode(series(['DA-KSE', 'B1', 'B2'], ['0.1', '0.5', '0.9']), mode='group')
    assert [s['color'] for s in st[:3]] == ['#287070', '#289C8C', '#88B07C']
    assert [s['color'] for s in st[3:6]] == ['#003048', '#106480', '#209CBC']
    assert [s['color'] for s in st[6:]] == ['#A82C04', '#D47C28', '#E8A800']
    assert [s['interior'] for s in st[::3]] == ['solid', 'half_up', 'open']


def test_categorical_and_overrides():
    st = style.encode([{'name': 'A'}, {'name': 'B'}, {'name': 'C', 'color': '#123456', 'dash': 'dash'}])
    assert all(s['interior'] == 'solid' and s['dash'] in ('solid', 'dash') for s in st)
    assert st[2]['color'] == '#123456' and st[2]['dash'] == 'dash'
    assert len({s['color'] for s in st}) == 3
    with pytest.raises(ValueError):
        style.encode([{'name': 'A', 'shape': 'blob'}])


def test_shades_and_ramp():
    fam = ['#111111', '#222222', '#333333', '#444444']
    assert style.shades(fam, 3) == fam[1:]          # 不足时取最深的几档
    assert len(style.shades(fam, 6)) == 6
    r = style.ramp(['#000000', '#FFFFFF'], 3)
    assert r == ['#000000', '#808080', '#FFFFFF']
    assert style.interiors(5) == ['solid', 'half_up', 'half_down', 'half_left', 'open']


# ---------- 坐标范围与排版 ----------

def test_axes_like_reference():
    x = layout.x_axis([20, 30, 40, 50, 60, 70, 80, 90])
    assert (x['from'], x['to'], x['step'], x['first']) == (15, 95, 10, 20)
    y = layout.y_axis(0.54, 1.0)
    assert y['step'] == 0.1 and y['to'] == pytest.approx(1.035)
    assert layout.decimals(0.05) == 2 and layout.decimals(10) == 0


def test_page_layout_rows_are_centered():
    cell = {'frame': (6, 4), 'margin': (1, 0.2, 0.3, 1)}
    geo = layout.page_layout([cell] * 3, [1, 2], gap=(0.4, 0.2), outer=0.1)
    (l0, t0, *_), (l1, t1, *_), (l2, *_) = geo['frames']
    assert geo['page'][0] == pytest.approx(2 * 7.3 + 0.4 + 0.2)
    assert l0 == pytest.approx((geo['page'][0] - 7.3) / 2 + 1)     # 第一行居中
    assert t1 == t0 + 5.2 + 0.2 and l2 - l1 == pytest.approx(7.7)
    with pytest.raises(ValueError):
        layout.page_layout([cell] * 2, [1, 2])


def test_legend_shifts_left_when_lines_end_low_on_the_right():
    """右下有线时，图例应向左让开或下延纵轴，而不是压在线上。"""
    frame, xr, yr = (6.2, 4.9), (15, 95), (0.45, 1.035)
    line = ('line', [20, 50, 80, 90], [1.0, 0.85, 0.55, 0.50], 0.08)
    placed = layout.place_legend(frame, xr, yr, [line], (4.0, 1.0), step=0.1)
    assert placed['pos'] == 'bottom' and not placed['overlap']
    assert placed['offset'] < 0 or placed['extended']


def test_legend_goes_to_top_for_bars():
    frame, xr, yr = (6.2, 4.9), (190, 310), (0.0, 0.6)
    bars = [('rect', x - 7, x + 7, 0.0, 0.5) for x in (200, 220, 240, 260, 280, 300)]
    placed = layout.place_legend(frame, xr, yr, bars, (4.0, 0.8), step=0.1, floor=0.0)
    assert placed['pos'] == 'top' and placed['y'][1] > 0.6 and not placed['overlap']


def test_legend_fixed_axis_reports_overlap():
    frame, xr, yr = (6.2, 4.9), (0, 10), (0, 1)
    line = ('line', [0, 10], [0.05, 0.05], 0.05)
    top = ('line', [0, 10], [0.95, 0.95], 0.05)
    placed = layout.place_legend(frame, xr, yr, [line, top], (5.5, 1.5), step=0.1, fixed=True)
    assert placed['overlap']


# ---------- spec ----------

def test_spec_matrix_expansion_and_defaults(tmp_path):
    (tmp_path / 'd.csv').write_text('load,A_1,B_1,A_2,B_2\n1,1,2,3,4\n2,2,3,4,5\n', encoding='utf-8')
    (tmp_path / 's.json').write_text(json.dumps({
        'panels': [{'data': 'd.csv', 'matrix': {'names': ['A', 'B'], 'groups': [1, 2], 'label': 'g{group}'}}]}),
        encoding='utf-8')
    sp = spec.load(tmp_path / 's.json')
    p = sp['panels'][0]
    assert [s['y'] for s in p['series']] == ['A_1', 'B_1', 'A_2', 'B_2']
    assert p['series'][2]['group'] == 'g2' and p['x']['col'] == 'load'
    assert sp['formats'] == ['png'] and sp['output'].endswith('s')
    assert sp['style']['line']['width'] == 0.37


def test_spec_categorical_x_and_error_columns(tmp_path):
    (tmp_path / 'd.csv').write_text('topo,A_1,A_1_std\nNSF,0.9,0.01\nUS,0.8,\n', encoding='utf-8')
    (tmp_path / 's.json').write_text(json.dumps({
        'panels': [{'type': 'bar', 'data': 'd.csv',
                    'matrix': {'names': ['A'], 'groups': [1], 'yerr': '{name}_{group}_std'}}]}), encoding='utf-8')
    p = spec.load(tmp_path / 's.json')['panels'][0]
    assert p['x']['labels'] == ['NSF', 'US'] and p['table']['topo'] == [1.0, 2.0]
    assert p['series'][0]['yerr'] == 'A_1_std'
    (tmp_path / 'bad.json').write_text(json.dumps({
        'panels': [{'data': 'd.csv', 'series': [{'y': 'A_1', 'yerr': 'nope'}]}]}), encoding='utf-8')
    with pytest.raises(ValueError, match='yerr'):
        spec.load(tmp_path / 'bad.json')


def test_spec_errors_are_readable(tmp_path):
    (tmp_path / 'd.csv').write_text('x,y\n1,2\n', encoding='utf-8')
    (tmp_path / 's.json').write_text(json.dumps({'panels': [{'data': 'd.csv', 'series': [{'y': 'nope'}]}]}),
                                     encoding='utf-8')
    with pytest.raises(ValueError, match='nope'):
        spec.load(tmp_path / 's.json')
    (tmp_path / 'h.json').write_text(json.dumps({'panels': [{'type': 'heatmap', 'values': [[1, 2], [3]]}]}),
                                     encoding='utf-8')
    with pytest.raises(ValueError, match='heatmap'):
        spec.load(tmp_path / 'h.json')


def test_fit_width_fills_journal_column():
    cells = [{'frame': [6.2, 4.9], 'margin': [1.25, 0.2, 0.3, 0.95]}]
    layout.fit_width(cells, [1], (0.35, 0.15), 8.5, 0.1)
    w = cells[0]['frame'][0] + 1.25 + 0.3 + 0.2
    assert w == pytest.approx(8.5, abs=1e-3)
    assert cells[0]['frame'][1] / cells[0]['frame'][0] == pytest.approx(4.9 / 6.2, rel=1e-3)
    fixed = [{'frame': [5, 4], 'margin': [1, 0, 0, 0], 'fixed': True}]
    assert layout.fit_width(fixed, [1], (0.35, 0.15), 8.5)[0]['frame'] == [5, 4]


def test_heatmap_cell_ink_only_darkens_pale_cells():
    from origin_cli import heatmap
    ramp = style.heatmap_colors('green', 64)
    assert heatmap.cell_ink(ramp, 0.0) != '#FFFFFF'
    assert heatmap.cell_ink(ramp, 0.5) == '#FFFFFF'
    assert heatmap.cell_ink(ramp, 1.0) == '#FFFFFF'


# ---------- 学自文献的 JSAC 风格 ----------

def test_categorical_palette_with_groups_like_jsac():
    """颜色跟方法走（分类配色），组之间只改填充、大小和线型（Hybrid relay Fig.8）。"""
    st = style.encode(series(['QTx', 'QRx'], ['CO-QBN', 'PTR']), mode='categorical', palette='jsac',
                      shapes=['up', 'down'], dashes=['short_dash', 'solid'], size=2.5, size_step=1.5)
    cats = style.palettes()['categorical']['jsac']
    assert [s['color'] for s in st] == [cats[0], cats[1], cats[0], cats[1]]
    assert [s['shape'] for s in st] == ['up', 'down', 'up', 'down']
    assert [(s['interior'], s['dash'], s['size']) for s in st[::2]] == [('solid', 'short_dash', 2.5), ('open', 'solid', 4.0)]
    with pytest.raises(ValueError):
        style.encode(series(['A'], [1]), palette='nope')


def test_legend_corner_and_parts():
    frame, xr, yr = (5.0, 4.0), (0, 10), (0, 10)
    placed = layout.place_legend(frame, xr, yr, [], (1.5, 1.0), pos='top-left', side_gap=0.1)
    assert placed['pos'] == 'top-left' and placed['offset'] == pytest.approx(-(5.0 - 1.5) / 2 + 0.1)
    # 一条线从整体矩形的右下角穿过，但避开了实际占用的两块（图例框 + 组名）
    line = ('line', [3.2, 3.3], [6.2, 6.2], 0.03)
    whole = layout.place_legend(frame, xr, yr, [line], (2.0, 1.6), pos='top-left', fixed=True, side_gap=0.1)
    parts = layout.place_legend(frame, xr, yr, [line], (2.0, 1.6), pos='top-left', fixed=True, side_gap=0.1,
                                parts=[(0, 0, 1.0, 1.6), (1.1, 0.2, 0.9, 0.3)])
    assert whole['overlap'] and not parts['overlap']


def test_brace_points_shape():
    pts = layout.brace_points(1.0, 0.0, 1.0, 0.1)
    assert pts[0] == pytest.approx((1.0, 0.0)) and pts[-1] == pytest.approx((1.0, 1.0))
    tip = max(pts, key=lambda p: p[0])
    assert tip[0] == pytest.approx(1.1) and tip[1] == pytest.approx(0.5)


def test_preset_extends_and_y2(tmp_path):
    jsac = spec.load_preset('jsac', tmp_path)
    assert jsac['font']['face'] == 'Arial' and jsac['heatmap']['palette'] == 'olive'      # 其余沿用 paper
    (tmp_path / 'd.csv').write_text('x,A|g1,B|g1,ku\n1,1,2,0.5\n2,2,3,0.6\n', encoding='utf-8')
    (tmp_path / 's.json').write_text(json.dumps({'preset': 'jsac', 'panels': [{
        'type': 'bar', 'data': 'd.csv',
        'matrix': {'names': ['A', 'B'], 'groups': ['g1'], 'col': '{name}|{group}', 'label': {'g1': 'η = 1'},
                   'style': {'B': {'pattern': 'cross'}}},
        'y2': {'series': [{'y': 'ku', 'name': 'A'}]}}]}), encoding='utf-8')
    p = spec.load(tmp_path / 's.json')['panels'][0]
    assert p['series'][0]['group'] == 'η = 1' and p['series'][1]['pattern'] == 'cross'
    assert p['y2']['type'] == 'line' and p['y2']['series'][0]['x'] == 'x'
