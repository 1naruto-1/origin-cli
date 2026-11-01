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
