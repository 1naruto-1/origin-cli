# origin-cli

用本机 Origin 画论文级科研数据图的命令行工具，同时也是一个 Claude Code skill（说明见 [SKILL.md](SKILL.md)）。

它的用法是：写一份 JSON spec，描述数据，以及每条曲线的语义（name 代表方法，group 代表参数）。工具会：
- 在后台启动一个隐藏的 Origin 实例并画图；
- 保存可编辑的 `.opju`；
- 导出 PNG / TIF / PDF / EMF / SVG。

配色、符号、填充、线型和图例位置，都由学自参考图的规则自动给出。

支持的图：点线 / 散点、柱状（分组、堆叠、重叠、花纹填充）、热力图（带色标）、柱线组合的双纵轴图，以及误差棒、断轴、对数轴、分类横轴、局部放大插图、括注和箭头标注。

两套风格预设：

| 预设 | 来源 | 特点 |
|---|---|---|
| `paper`（默认） | 用户给的参考图 `折线图/`、`热力图/` | Times 字体、刻度朝内、图例底部居中无边框、同色系深浅递进 |
| `jsac` | Cao 等, IEEE JSAC 2021 的 Origin 矢量原图 | Arial、刻度朝内带次刻度、浅灰网格、带框图例放角上、亮色按方法配色、大括号分组的图例、×10ⁿ |

```
origin-cli doctor                      # 检查环境
origin-cli build examples/line_omega/spec.json
origin-cli export out/fig.opju --fmt png,pdf --dpi 600
origin-cli inspect out/fig.opju        # 读回格式
```

## 安装

需要：
- Windows
- Origin / OriginPro 2024（其他版本未验证）
- Python ≥ 3.10

```
pip install -e .
```

安装后，`origin-cli` 命令就可以用了；也可以用 `python -m origin_cli` 运行。

用作 Claude Code skill 时，把本目录链接到 skills 目录下：

```
mklink /J %USERPROFILE%\.claude\skills\origin-cli C:\path\to\origin-cli
```

工具默认从注册表里找 Origin 的安装路径。找不到时，在本目录建一个 `config.json`：

```json
{"origin_exe": "D:/OriginLab/Origin2024/Origin64.exe", "work_dir": "D:/tmp/origin-cli", "startup_timeout": 60}
```

## 目录

| 路径 | 内容 |
|---|---|
| `origin_cli/` | 源代码，各文件分工见下表 |
| `presets/paper.json` | 默认风格：字号、框尺寸、线宽、图例参数等 |
| `palettes.json` | 色系和热图渐变（色值取自参考图） |
| `references/` | spec 字段说明、审美规则与理由、Origin 自动化的坑 |
| `examples/` | 复刻参考图的完整例子（spec + 数据 + 参考图 + 输出） |
| `tests/` | 单元测试，不需要 Origin |

`origin_cli/` 里的文件：

| 文件 | 作用 |
|---|---|
| `cli.py` | 命令行入口 |
| `origin.py` | 启动和连接 Origin 会话 |
| `spec.py` | 读取 spec |
| `style.py` | 审美规则 |
| `layout.py` | 排版与图例避让 |
| `draw.py` | 点线图和柱状图的绘制 |
| `heatmap.py` | 热力图 |
| `inspect.py` | 读回 .opju 的格式 |
| `ref.py` | 参考图测量与对比 |
| `fmt.c` | Origin C 辅助函数（必须保存为 UTF-8 带 BOM） |

## 测试

```
python -m pytest tests
```

单元测试覆盖审美分配、坐标范围、排版、图例避让和 spec 校验。

画图本身需要真实的 Origin，用 `examples/` 里的 spec 来验证。验证时用 `origin-cli ref compare` 生成并排对比图，与参考图对照。

## 已知问题

- **文字上划线**：Origin 2024 以自动化方式启动时，导出图片里的文字上方会多一条横线。工具默认用普通方式隐藏启动来避开它。如果本机已有 Origin 在运行，工具会改用自动化实例，并在输出里提示：关掉 Origin 后用 `export` 重新导出即可。
- **箭头**：插图的指示箭头是直线，不是弧线。
- **暂不支持**：面积图、饼图、三维图。
