"""origin-cli 命令行入口。所有命令把结果以 JSON 打印到标准输出。"""
import argparse
import json
import sys
from pathlib import Path


def _out(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def cmd_doctor(a):
    from .config import CONFIG
    from .origin import Session, origin_pids
    info = {'origin_exe': CONFIG['origin_exe'], 'exists': Path(CONFIG['origin_exe']).exists(),
            'running_origin': sorted(origin_pids())}
    try:
        import originpro  # noqa: F401
        info['originpro'] = 'ok'
    except ImportError as exc:
        info['originpro'] = f'缺少：{exc}（pip install originpro）'
        return _out(info)
    with Session() as s:
        info.update({'mode': s.mode, 'version': s.num('@V'), 'notes': s.notes})
    _out(info)


def cmd_build(a):
    from . import spec as specmod
    from .draw import Figure
    from .origin import Session
    sp = specmod.load(a.spec)
    with Session(show=a.show, keep_open=a.keep_open, mode=a.mode) as s:
        fig = Figure(s, sp)
        fig.render()
        files = fig.export()
        out = {'files': files, 'graph': fig.g.name, 'page_cm': list(fig.page), 'mode': s.mode,
               'warnings': fig.warnings + s.notes,
               'panels': fig.panels}
    _out(out)


def cmd_export(a):
    from .draw import export_graph
    from .origin import Session
    from .spec import strip_ext
    src = Path(a.opju).resolve()
    out = strip_ext(Path(a.out).resolve() if a.out else src)
    formats = [f.strip().lower() for f in a.fmt.split(',') if f.strip()]
    with Session(mode=a.mode) as s:
        s.op.open(str(src), readonly=True)
        g = _graph(s, a.graph)
        width_cm = g.get_float('width') / g.get_float('resx') * 2.54
        files = export_graph(g, out, formats, a.dpi, width_cm)
        name = g.name
    _out({'files': files, 'graph': name, 'mode': s.mode, 'notes': s.notes})


def _graph(s, name):
    graphs = s.op.graph_list()
    if not graphs:
        raise RuntimeError('工程里没有图')
    if name:
        for g in graphs:
            if name in (g.name, g.lname):
                return g
        raise RuntimeError(f'工程里没有图 {name!r}（有：{", ".join(g.name for g in graphs)}）')
    return graphs[0]


def cmd_inspect(a):
    from .inspect import inspect_project
    from .origin import Session
    with Session(mode=a.mode) as s:
        s.op.open(str(Path(a.opju).resolve()), readonly=True)
        _out(inspect_project(s, a.graph))


def cmd_lt(a):
    from .draw import export_graph
    from .origin import Session
    from .spec import strip_ext
    src = Path(a.opju).resolve()
    with Session(mode=a.mode) as s:
        s.op.open(str(src), readonly=not a.save)
        g = _graph(s, a.graph)
        g.lt_exec(f'win -a {g.name};')
        if a.layer:
            s.lt(f'page.active = {a.layer};')
        for script in a.run or []:
            s.lt(script)
        s.lt('doc -uw;')                # 刷新后再读值、保存和导出
        out = {'graph': g.name, 'values': {e: s.text(e) for e in (a.get or '').split(',') if e.strip()}}
        if a.save:
            s.op.save(str(src))
            width_cm = g.get_float('width') / g.get_float('resx') * 2.54
            out['files'] = [str(src)] + export_graph(g, strip_ext(src), ['png'], a.dpi, width_cm)
    _out(out)


def cmd_palette(a):
    from . import style
    pal = style.palettes()
    if a.action == 'list':
        return _out({k: pal[k] for k in ('heatmap', 'families', 'categorical', 'order') if k in pal})
    colors = pal['heatmap'].get(a.name) or pal['families'].get(a.name) or pal.get('categorical', {}).get(a.name)
    if not colors:
        raise ValueError(f'没有调色板 {a.name!r}')
    out = {'name': a.name, 'colors': colors}
    if a.png:
        from PIL import Image, ImageDraw
        cols = style.ramp(colors, 256) if a.name in pal['heatmap'] else colors
        w = 512 if a.name in pal['heatmap'] else 120 * len(cols)
        im = Image.new('RGB', (w, 80), 'white')
        d = ImageDraw.Draw(im)
        step = w / len(cols)
        for i, c in enumerate(cols):
            d.rectangle([round(i * step), 0, round((i + 1) * step), 80], fill=c)
        im.save(a.png)
        out['png'] = str(Path(a.png).resolve())
    _out(out)


def cmd_ref(a):
    from . import ref
    if a.action == 'measure':
        _out(ref.measure(a.paths[0], box=a.box))
    else:
        if len(a.paths) != 2 or not a.out:
            raise ValueError('compare 需要两张图和 -o 输出路径')
        _out(ref.compare(a.paths[0], a.paths[1], a.out))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(prog='origin-cli', description='用本机 Origin 画科研数据图：按 spec 出图、导出、读回格式')
    sub = p.add_subparsers(dest='command', required=True)
    mode = dict(choices=['auto', 'normal', 'automation'], default='auto',
                help='auto：没有其他 Origin 在运行时按普通方式隐藏启动（避开 2024 的文字上划线），否则用自动化实例')

    s = sub.add_parser('doctor', help='检查 Origin、originpro 与连接方式')
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser('build', help='按 spec.json 出图：保存 .opju、导出图片、给出诊断')
    s.add_argument('spec')
    s.add_argument('--show', action='store_true', help='画图时显示 Origin 窗口')
    s.add_argument('--keep-open', action='store_true', help='画完保持 Origin 打开（便于手动微调）')
    s.add_argument('--mode', **mode)
    s.set_defaults(func=cmd_build)

    s = sub.add_parser('export', help='从已有 .opju 导出图片')
    s.add_argument('opju')
    s.add_argument('--fmt', default='png', help='逗号分隔：png,tif,jpg,pdf,svg,emf,eps')
    s.add_argument('--dpi', type=int, default=600)
    s.add_argument('--graph', help='图名（缺省为第一张图）')
    s.add_argument('--out', help='输出路径（不含扩展名，缺省与 .opju 同名）')
    s.add_argument('--mode', **mode)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser('inspect', help='读回 .opju 里图层、曲线、图例、坐标轴的格式')
    s.add_argument('opju')
    s.add_argument('--graph')
    s.add_argument('--mode', **mode)
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser('lt', help='对 .opju 执行/查询 LabTalk（兜底微调）')
    s.add_argument('opju')
    s.add_argument('--run', action='append', help='LabTalk 语句，可写多个')
    s.add_argument('--get', help='逗号分隔的表达式，返回其值，如 layer.x.from,legend.fsize')
    s.add_argument('--layer', type=int, help='先切到第几个图层（从 1 起），layer.* 与 legend 等都指向它')
    s.add_argument('--graph')
    s.add_argument('--save', action='store_true', help='保存回 .opju 并重新导出 PNG')
    s.add_argument('--dpi', type=int, default=600)
    s.add_argument('--mode', **mode)
    s.set_defaults(func=cmd_lt)

    s = sub.add_parser('palette', help='查看调色板')
    s.add_argument('action', choices=['list', 'show'])
    s.add_argument('name', nargs='?')
    s.add_argument('--png', help='show 时把色块存成图片')
    s.set_defaults(func=cmd_palette)

    s = sub.add_parser('ref', help='参考图：measure 测坐标框与主色；compare 与成品并排对比')
    s.add_argument('action', choices=['measure', 'compare'])
    s.add_argument('paths', nargs='+')
    s.add_argument('--box', help='measure：只统计该区域的颜色，x0,y0,x1,y1（像素）')
    s.add_argument('-o', '--out', help='compare：输出图片')
    s.set_defaults(func=cmd_ref)

    a = p.parse_args(argv)
    try:
        a.func(a)
    except (ValueError, KeyError, FileNotFoundError, RuntimeError) as exc:
        _out({'error': f'{type(exc).__name__}: {exc}'})
        sys.exit(1)


if __name__ == '__main__':
    main()
