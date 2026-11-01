"""本机路径与默认配置：缺省值按本机注册表查找 Origin，可用 skill 目录下的 config.json 覆盖。"""
import json
import os
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def _origin_exe() -> str:
    """从注册表里 Origin 记录的安装目录找 Origin64.exe，装了多个版本时取最新的；找不到时用默认安装路径。"""
    found = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\OriginLab') as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                name = winreg.EnumKey(root, i)          # 如 Origin 10.1（即 2024）
                try:
                    with winreg.OpenKey(root, name + r'\International') as key:
                        exe = Path(winreg.QueryValueEx(key, 'Executable Path')[0]) / 'Origin64.exe'
                except OSError:
                    continue
                m = re.search(r'\d+(\.\d+)?', name)
                if exe.exists():
                    found.append((float(m.group()) if m else 0.0, str(exe)))
    except (ImportError, OSError):
        pass
    return max(found)[1] if found else r'C:\Program Files\OriginLab\Origin2024\Origin64.exe'


def _load() -> dict:
    path = SKILL_DIR / 'config.json'
    user = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return {'origin_exe': user.get('origin_exe') or _origin_exe(),
            'work_dir': user.get('work_dir') or str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'origin-cli'),
            'startup_timeout': user.get('startup_timeout', 60)}


CONFIG = _load()


def load_json(name: str) -> dict:
    return json.loads((SKILL_DIR / name).read_text(encoding='utf-8'))
