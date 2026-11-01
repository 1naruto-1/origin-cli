"""与本机 Origin 的会话：启动/连接、执行 LabTalk、读写格式树、导出、收尾清理。

Origin 2024（10.1）以自动化服务器方式启动时，导出图里的文字上方会多出一条横线（2024b 修复）。
所以优先按普通方式隐藏启动（Origin64.exe -h）再连接；本机已有 Origin 在运行时无法确定连上的是哪一个，
改用独立的自动化实例（结果里会提示）。只关闭自己启动的进程，以及它崩溃时弹出的错误报告窗口。
"""
import ctypes
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path
from xml.sax.saxutils import escape

from .config import CONFIG

HERE = Path(__file__).resolve().parent
_k32, _u32 = ctypes.windll.kernel32, ctypes.windll.user32


class _ProcEntry(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_void_p), ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]


def _procs():
    """(pid, 父 pid, 可执行文件名) 列表"""
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
    entry = _ProcEntry()
    entry.dwSize = ctypes.sizeof(entry)
    out, ok = [], _k32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        out.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
        ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    _k32.CloseHandle(snap)
    return out


def origin_pids() -> set:
    return {pid for pid, _, exe in _procs() if exe.lower() in ('origin64.exe', 'origin.exe')}


def _alive(pid) -> bool:
    return any(p == pid for p, _, _ in _procs())


def _kill(pid):
    h = _k32.OpenProcess(0x0001, False, pid)
    if h:
        _k32.TerminateProcess(h, 1)
        _k32.CloseHandle(h)


def _main_title(pid) -> str:
    """进程主窗口（MFC 主框架）的标题；隐藏启动时窗口不可见，但标题照样能读到。"""
    titles = []
    proc_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        owner = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            cls = ctypes.create_unicode_buffer(64)
            _u32.GetClassNameW(hwnd, cls, 64)
            if cls.value.startswith('Afx:0000'):
                buf = ctypes.create_unicode_buffer(256)
                _u32.GetWindowTextW(hwnd, buf, 256)
                titles.append(buf.value)
        return True
    _u32.EnumWindows(proc_t(cb), 0)
    return titles[0] if titles else ''


def _xml(tree: dict) -> str:
    out = []
    for k, v in tree.items():
        out.append(f'<{k}>{_xml(v) if isinstance(v, dict) else escape(str(v))}</{k}>')
    return ''.join(out)


class Session:
    """一次 Origin 会话。用法：with Session() as s: ..."""

    def __init__(self, show=False, keep_open=False, mode='auto'):
        self.show, self.keep_open, self.mode = show, keep_open, mode
        self.proc, self.pid, self.own, self.notes = None, None, set(), []
        self.tmp = Path(CONFIG['work_dir']) / 'tmp'
        self.tmp.mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close(failed=exc_type is not None)

    def open(self):
        before, t0 = origin_pids(), time.time()
        while before and time.time() - t0 < 8:
            # 可能是上一次出图的实例还在退出，稍等再判断
            time.sleep(0.5)
            before = origin_pids()
        if self.mode == 'auto':
            self.mode = 'automation' if before else 'normal'
        if self.mode == 'automation':
            why = '本机已有 Origin 在运行，' if before else ''
            self.notes.append(f'{why}用的是独立的自动化实例：Origin 2024 下导出图的文字上方可能多一条横线，'
                              '关闭其他 Origin 后用 export 命令重新导出即可（.opju 本身不受影响）')
        import originpro as op
        self.op = op
        if self.mode == 'normal':
            if not Path(CONFIG['origin_exe']).exists():
                raise RuntimeError(f'找不到 Origin：{CONFIG["origin_exe"]}。在 skill 目录建 config.json，写上 origin_exe')
            self.proc = subprocess.Popen([CONFIG['origin_exe'], '-h'])
            t0 = time.time()
            while ' - ' not in _main_title(self.proc.pid):
                if time.time() - t0 > CONFIG['startup_timeout'] or self.proc.poll() is not None:
                    raise RuntimeError('Origin 启动超时')
                time.sleep(0.3)
            op.attach()
        else:
            op.lt_float('@V')
        self.own = origin_pids() - before
        op.set_show(self.show)
        self.lt('sec -poc;')
        self.lt(f'__e = run.loadoc("{HERE / "fmt.c"}");')
        if self.num('__e') != 0:
            raise RuntimeError('Origin C 辅助函数 fmt.c 编译失败')
        self.pid = int(self.num('oc_pid()'))
        if self.mode == 'normal' and self.pid != self.proc.pid:
            raise RuntimeError(f'连到了别的 Origin 实例（{self.pid}），已放弃')
        self.own.add(self.pid)

    def close(self, failed=False):
        op = self.op
        if self.keep_open and not failed:
            op.set_show(True)
            op.detach()
            return
        try:
            self.lt('doc -s;')
            op.exit()
        except Exception:
            pass
        t0 = time.time()
        while any(_alive(p) for p in self.own) and time.time() - t0 < 20:
            time.sleep(0.3)
        for pid, ppid, _ in _procs():
            if pid in self.own or ppid in self.own:
                _kill(pid)

    # ---------- LabTalk ----------
    def lt(self, script: str):
        if not self.op.lt_exec(script):
            raise RuntimeError(f'LabTalk 执行失败：{script[:300]}')

    def num(self, expr: str) -> float:
        self.op.lt_exec(f'__v = {expr};')
        return self.op.lt_float('__v')

    def text(self, expr: str) -> str:
        self.op.lt_exec(f'__s$ = $({expr});')
        return self.op.get_lt_str('__s$')

    def set_str(self, var: str, value: str):
        """经 LabTalk 字符串变量传文字，避免 % 和引号被当作替换或语法。"""
        self.op.set_lt_str(var, value)

    # ---------- 格式树 ----------
    def fmt(self, page: str, layer: int, tree: dict, plot: int = -1, obj: str = ''):
        """应用只含目标节点的小格式树，如 {'Symbol': {'FillColor': -4}}。"""
        path = self.tmp / f'fmt_{os.getpid()}.xml'
        path.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<OriginStorage><Root>{_xml(tree)}</Root>'
                        '</OriginStorage>', encoding='utf-8')
        rc = self.num(f'fmt_apply("{page}", {layer}, {plot}, "{obj}", "{path}")')
        if rc != 0:
            raise RuntimeError(f'格式设置失败（{rc:g}）：{tree}')

    def dump(self, page: str, layer: int, plot: int = -1, obj: str = '') -> dict:
        """读格式树，返回 {'Symbol/Size': '3', ...}；对象不存在时返回 {}。"""
        path = self.tmp / f'dump_{os.getpid()}.xml'
        if self.num(f'fmt_dump("{page}", {layer}, {plot}, "{obj}", "{path}")') != 0:
            return {}
        flat = {}

        def walk(e, p):
            kids = list(e)
            if not kids:
                flat[p] = e.text or ''
            for k in kids:
                walk(k, f'{p}/{k.tag}' if p else k.tag)
        root = ET.parse(path).getroot()
        if len(root):
            walk(root[0], '')
        return flat
