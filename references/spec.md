# spec 字段说明

spec 是一个 JSON 文件，描述一张图（一个 Origin 图页），图页里可以有多个子图（面板）。
没写的字段都有默认值，默认值来自预设 `presets/paper.json`，以及从参考图学到的规则。

## 目录

1. [顶层字段](#1-顶层字段)
2. [面板通用字段](#2-面板通用字段)
3. [数据与曲线：data / x / series / matrix](#3-数据与曲线)
4. [样式分配：encode 与单条覆盖](#4-样式分配)
5. [坐标轴：范围、刻度、对数、断轴、分类](#5-坐标轴)
6. [图例：legend](#6-图例)
7. [柱状图：mode](#7-柱状图)
8. [双纵轴：y2](#8-双纵轴)
9. [误差棒：yerr](#9-误差棒)
10. [插图：inset](#10-插图)
11. [标注：marks](#11-标注)
12. [热力图](#12-热力图)
13. [style：覆盖预设](#13-style覆盖预设)
14. [LabTalk 兜底](#14-labtalk-兜底)
15. [build 的输出](#15-build-的输出)

---

## 1. 顶层字段

| 字段 | 默认 | 说明 |
|---|---|---|
| `output` | 与 spec 同名，放在同目录 | 输出路径，不含扩展名。相对路径以 spec 所在目录为准。 |
| `formats` | `["png"]` | 可选 `png` `tif` `jpg` `pdf` `svg` `emf` `eps`；PNG 总会生成（用来看图）。详见下文。 |
| `dpi` | 600 | 位图分辨率。像素宽 = 页面宽(cm) / 2.54 × dpi。 |
| `preset` | `"paper"` | `presets/` 下的预设名，或一个 .json 文件路径（相对路径以 spec 所在目录为准）。现有 `paper`（学自 `折线图/`、`热力图/` 的参考图）和 `jsac`（学自 IEEE JSAC 文献，见 §13）。 |
| `style` | — | 对预设的逐项覆盖（深合并），见 §13。 |
| `layout` | — | 多个子图的排法，见下表。 |
| `data` | — | 各面板共用的数据；面板自己没写 `data` 时用它。 |
| `panels` | 必填 | 子图列表，按从左到右、从上到下的顺序。 |
| `labtalk` | `[]` | 全部画完后，在图页上执行的 LabTalk 语句。 |

`formats` 里各格式的生成方式：
- TIF、JPG 由 PNG 转出，带 dpi 信息；TIF 用 LZW 压缩。
- PDF、SVG、EMF、EPS 是矢量图，由 Origin 直接导出。

`layout` 的字段：

| 字段 | 默认 | 说明 |
|---|---|---|
| `rows` | 每行 1 个 | 每行放几个面板。例如 `[1, 2]` 表示上面 1 个（居中）、下面 2 个。各行加起来要等于面板数。 |
| `gap` | `[0.35, 0.15]` | 单位 cm：同一行内相邻面板的间距，以及行与行之间的间距（都是外框到外框）。 |
| `width` | — | 页面宽度（cm），比如期刊要求的单栏 8.5、双栏 17.5。没写 `frame` 的面板会等比放大或缩小，使最宽的一行正好铺满；字号、线宽不变。 |

页面大小由各面板的框尺寸加上留白自动算出，不需要手动指定。

## 2. 面板通用字段

| 字段 | 默认 | 说明 |
|---|---|---|
| `type` | `"line"` | `line`：点线；`scatter`：只画符号；`bar`：柱状；`heatmap`：热力图。 |
| `caption` | — | 子图标题，放在横轴标题下方、居中。例如 `"(a)"`、`"(a) \\i(η) = 0.1"`。 |
| `frame` | line/bar 为 `[6.2, 4.9]`；heatmap 宽 9.0、高为 行数 × 0.733 | 坐标框的宽和高（cm）。写了之后，`layout.width` 不再缩放它。 |
| `margin` | 见预设 | 框外的留白 `[左, 上, 右, 下]`（cm），用来放刻度值和标题。没写时，左侧留白按纵轴刻度值的宽度自动增减（以“0.95”为基准）；有 caption 时，下方自动再加 0.45。 |
| `labtalk` | `[]` | 该面板画完后，在它的图层上执行的 LabTalk 语句。 |

文字（标题、图例名、标注）里可以用 Origin 的转义写法。在 JSON 里，反斜杠要写成两个：

| 写法 | 效果 |
|---|---|
| `\\i(x)` | 斜体 |
| `\\b(x)` | 粗体 |
| `\\-(x)` | 下标 |
| `\\+(x)` | 上标 |

例如 `"\\i(E)\\-(b)/\\i(N)\\-(0)"` 显示为 *E*<sub>b</sub>/*N*<sub>0</sub>。

另外两点：
- η、ω、∈、±、° 等 Unicode 字符直接写即可。
- 中文字符会自动用宋体，其余字符仍用 Times New Roman。

## 3. 数据与曲线

### data

三种写法（相对路径以 spec 所在目录为准，也可以写绝对路径）：
- CSV 文件路径：按 UTF-8 读取（带 BOM 也可以）。第一行是列名。
- `"文件.xlsx#工作表"`：不写 `#工作表` 时读第一个工作表。
- 内联写法：`{"load": [20, 30, 40], "A": [0.9, 0.8, 0.7]}`。

空单元格视为缺测，不会参与画图和坐标范围的计算。

### x

| 字段 | 说明 |
|---|---|
| `col` | 横轴列名。默认是第一列。 |
| `title` | 横轴标题。 |

其余字段（`step`、`range` 等）见 §5。

### series

列出每条曲线。可以写成字符串（列名），也可以写成对象：

| 字段 | 说明 |
|---|---|
| `y` | 纵轴列名，必填。 |
| `x` | 横轴列名。默认是面板的 `x.col`。 |
| `yerr` | 误差列名，见 §9。 |
| `name` | 方法或方案名，决定符号形状和色系。默认取列名。 |
| `group` | 参数或场景，决定颜色深浅、大小、填充和线型。只有一个维度时不要写。 |
| `line` | 写 `false` 时只画符号（散点）。 |
| `color` `shape` `interior` `size` `dash` `width` | 单条覆盖，见 §4。 |

既不写 `series` 也不写 `matrix` 时，除横轴列以外的每一列都画成一条曲线，列名就是 name。

### matrix（name × group 的简写）

```json
"matrix": {"names": ["DA-KSE", "Benchmark-1", "Benchmark-2"],
           "groups": [10, 20, 30, 40],
           "col": "{name}_{group}",
           "label": "\\i(ω)\\-(e) = {group}",
           "yerr": "{name}_{group}_std"}
```

它会展开成 `names × groups` 条曲线，展开顺序是：先按 group，同一 group 内再按 name。

| 字段 | 默认 | 说明 |
|---|---|---|
| `col` | `"{name}_{group}"` | 数据列名的模板。 |
| `label` | `"{group}"` | group 在图例里显示的文字。也可以写成 `{group: 文字}`，如 `{"eta1": "\\i(η)\\-(r) = 1"}`。 |
| `yerr` | — | 误差列名的模板（可选）。 |
| `style` | — | 按 name 的单条覆盖，如 `{"ILP": {"line": false}, "RANDOM": {"shape": "none"}}`（只画符号 / 只画线）。 |

注意：展开后，曲线的 group 值就是 `label` 生成的那段文字。所以在 `encode.group_order` 里引用 group 时，要写这段文字，而不是原始值。

## 4. 样式分配

### encode（面板级）

| 字段 | 默认 | 说明 |
|---|---|---|
| `color` | `"auto"` | 取值见下表。 |
| `families` | 见 `palettes.json` 的 order | 依次使用的色系名，例如 `["navy", "warm", "teal"]`。 |
| `group_order` | 出现顺序 | group 递进的顺序（由浅到深、由实到空）。 |
| `size` | 3 | 第一组符号的大小（pt）。 |
| `size_step` | 1 | 每往后一组，符号增大多少（pt）。 |
| `width` | 0.37 | 线宽（pt）。 |
| `palette` | — | categorical 模式改用一组分类颜色：`jsac`、`jlt`、`access`（取自文献矢量图），或颜色列表。 |
| `shapes` | 菱形、上三角、圆… | 形状的使用顺序，如 `["up", "down", "circle"]`。 |
| `dashes` | Solid、Short Dash… | 各组线型的顺序，如 `["short_dash", "solid"]`（第一组虚线、第二组实线）。 |
| `pattern` | `none` | 柱的花纹，见 §7。 |

预设里也可以写 `encode`，作为各面板的默认值；面板的 `encode` 再逐项覆盖。

`color` 的取值：

| 取值 | 含义 |
|---|---|
| `auto` | 有多个 group 时用 family，只有 name 时用 categorical。 |
| `family` | 每个 name 一个色系，group 由浅到深。 |
| `group` | 每个 group 一个色系，name 在色系内由深到浅。 |
| `categorical` | 每个 name 取一个色系里倒数第二深的那一档；给了 `palette` 时改用分类颜色。有多个 group 时，group 仍然只改填充、大小和线型（JSAC 文献的做法）。 |

只有 name、没有 group 时，符号都是实心、实线，大小为 `size + size_step`（默认 4 pt）。

可用的色系（`origin-cli palette list` 可以查看色值）：

| 色系 | 来源 |
|---|---|
| blue、red、brown（各 4 档） | 学自参考图“折线图/1” |
| teal、navy、warm（各 3 档） | 学自参考图“折线图/2” |
| purple、gray | 补充 |

group 数多于色系的档数时，在色系内插值；少于档数时，取最深的几档。

色系的使用顺序：family 模式按 name 依次为 blue、red、brown、teal…；group 模式按 group 依次为 teal、navy、warm、blue…（即参考图“折线图/2”的前三套）。想换就写 `encode.families`。

### 单条覆盖（写在 series 里）

| 字段 | 可选值 |
|---|---|
| `color` | `"#RRGGBB"` |
| `shape` | `none`（纯线）`square` `circle` `up` `down` `diamond` `plus` `cross` `hbar` `vbar` `left` `right` `hexagon` `star` `pentagon` |
| `interior` | `solid` `open` `half_up` `half_down` `half_left` `half_right` `dot` `hollow` `plus` `cross` `minus` `bar` |
| `size` | 符号大小（pt） |
| `dash` | `solid` `short_dash` `short_dash_dot` `short_dot` `dash` `dash_dot` `dash_dot_dot` `dot` |
| `width` | 线宽（pt） |
| `pattern` | 柱的花纹（§7） |
| `line` | `false` 时只画符号 |

只要 `interior` 不是 `solid`，未填充的部分一律透明（“无填充”）。`shape` 为 `none` 时只画线。

## 5. 坐标轴

`x` 和 `y` 都可以写以下字段：

| 字段 | 说明 |
|---|---|
| `title` | 轴标题。 |
| `step` | 主刻度间距。默认按数据范围自动取 1/2/2.5/5×10ⁿ。 |
| `range` | `[起, 止]`，固定坐标范围。固定后，图例不会再为了让位去延长纵轴。 |
| `first` | 第一个刻度的位置。 |
| `decimals` | 刻度值的小数位数。默认与 step 的小数位数一致；断轴两段间距的位数不同时，两段各自定位数。写了 `decimals` 则全轴统一。 |
| `scale` | 写 `"log"` 为对数轴。范围取整十倍，每十倍一个刻度，刻度值显示为 10ⁿ 形式。数据须为正数。 |
| `factor` | 纵轴专用。整数 n：刻度值除以 10ⁿ 显示，框左上方写 ×10ⁿ；`"auto"`：数值上千时自动选 n，让刻度值只留一两位整数；`null`：不用。默认取预设（jsac 为 auto，paper 不用）。只改显示，数据不变。 |
| `grid` | `true`/`false` 开关主刻度网格线，或写 `{"color", "style", "width"}` 覆盖。默认取预设 `axis.grid`（jsac 有，paper 无）；柱状图默认不画竖线。 |

自动范围的规则：
- 横轴两端留白：数据等距时留半个数据间距（至少四分之一个刻度），否则留半个刻度。数据横坐标等距、且与刻度间距成整数倍时，刻度对齐到数据点（如 15, 45, 75…）。
- 柱状图的横轴刻度间距默认取数据间距（每簇一个刻度）。
- 纵轴上下各留约 0.35 个刻度间距；刻度个数由预设 `axis.y_ticks` 决定（paper 约 5 个，jsac 约 7 个）。
- 柱状图的纵轴从 0 开始。

自动范围的两端通常不落在刻度上（如 0.4455–1.035），这是参考图的做法：首尾的点不贴框。想让两端落在整刻度上，就写 `range`（例如 `[0, 100]`），并确认图例仍放得下。

### 分类横轴

横轴列是文字时，按类别等距排开（位置依次为 1、2、3…），刻度标签就是这些文字。不需要额外设置。

### 断轴（只支持纵轴，一处断点）

```json
"y": {"title": "Success probability", "range": [0.3, 1.02], "step": 0.1,
      "break": {"from": 0.72, "to": 0.96, "at": 0.35, "step": 0.01}}
```

| 字段 | 说明 |
|---|---|
| `from`、`to` | 被省略的区间。 |
| `at` | 断点放在纵轴高度的哪个比例处（0–1）。默认让上下两段比例尺一致。 |
| `step` | 断点上方那一段的刻度间距。不写时与 `y.step` 相同。 |

使用断轴时建议同时写 `y.range`。有断轴时，图例不会延长纵轴；放不下就换到顶部，或者在诊断里报告重叠。

几点取值经验：
- 断点上方的刻度是 `break.step` 的整数倍；正好落在 `from` 或 `to` 上的刻度不显示。
- `at` 不写时，工具按 `at = (from − y0) / ((from − y0) + (y1 − to))` 让上下两段比例尺一致（读者不会误判差距），其中 y0、y1 是 `y.range` 的两端，并限制在 0.25–0.8。
- 上下两段量级不同、`break.step` 与 `y.step` 不一样时（例如下段 0–0.8 s、上段 150–900 s），比例尺一致会把一段压没，`at` 默认取 0.6。例子见 `examples/bar_break_twoscale`。
- 柱状图同样可以断轴，纵轴仍从 0 开始，跨过断点的柱会在断口处留出缺口。上限要给顶部图例留出位置。

## 6. 图例

每个面板一个图例，放在框内。paper 预设无边框、无底色；jsac 预设带细框、白底（盖住网格线）。

| 字段 | 默认 | 说明 |
|---|---|---|
| `show` | `true` | 写 `false` 时不显示图例。 |
| `pos` | `"auto"` | `auto` 依次试预设 `legend.auto` 列出的位置（paper：底部、顶部；jsac：左上、右上、右下、左下），选代价小的。也可以写 `bottom`、`top`（居中，可左右平移）或 `top-left`、`top-right`、`bottom-left`、`bottom-right`（贴角）。 |
| `dx`、`dy` | 0 | 在自动位置的基础上微调（cm）。正值分别表示向右、向上。 |
| `size` | 6.5 | 字号（pt）。写了之后就不会再自动缩小。 |
| `columns` | 自动 | 列表式图例每行放几个条目。点线图默认 3 个及以下放一行、4 个排两列、更多排三列；柱状图 6 个及以下放一行（色块和字一样高，多行容易挤，且 Origin 对列表式的第二列对不齐）。 |
| `transpose` | `false` | 矩阵式图例行列互换：改为每行一个 name、每列一个 group。 |
| `layout` | 取预设 | 有 name 和 group 两个维度时的排法：`matrix`（矩阵，paper 默认）或 `brace`（一列，每组右侧用大括号标出组名，jsac 默认）。双纵轴面板另有 `split`（默认）：左右轴各一个单列图例。 |
| `frame` | 取预设 | `true`/`false`，或 `{"color", "width", "style"}`，如 `{"style": "dash"}` 为虚线框（RCWA 文献的做法）。 |
| `text` | — | 完全自定义的图例文字，用 Origin 语法。 |

`text` 的写法：
- `\\l(n)` 表示第 n 条曲线的图例符号；
- 制表符 `\t` 分列，`\n` 分行。

n 的编号规则：
- 按曲线在图层里的顺序编号；
- 带误差棒的曲线，其误差棒占用紧随其后的那个编号；
- overlap 柱状图按 group 均值从大到小的顺序画，编号顺序也随之改变。

拿不准编号时，先 build 一次，再用 `inspect` 查看。

图例格式：
- 有多个 group 也有多个 name 时：
  - `matrix`：每行一个 group，行首是 group 名，后面每格是“符号 + name”；
  - `brace`：所有条目排成一列（按 group 依次列出），每组右侧画一个大括号，括号尖端右边写组名。只有括号和组名那几行参与避让，空白处不算占用。
- 只有一个维度时，排成列表（列数见 `columns`，jsac 预设默认一列）。

自动定位的规则：
1. 先放在底部（或顶部）居中，和曲线、符号、误差棒、柱子保持一点间距；
2. 不行就左右平移，最多移到离边框 0.1 cm；
3. 还不行，就把纵轴往图例那一侧延长（最多延长 60%，并取整到半个刻度）；
4. 仍然重叠时，选重叠最轻的位置，并在 warnings 里报告。

图例太宽时，字号每次缩小 0.5 pt，最小到 5.5 pt。

## 7. 柱状图

```json
{"type": "bar", "mode": "grouped", ...}
```

`mode` 的取值：

| 取值 | 说明 |
|---|---|
| `grouped`（默认） | 同一横坐标处的各条序列并排成一簇。 |
| `stacked` | 堆叠。纵轴范围按各列之和计算。 |
| `overlap` | 同一 group 的序列并排成一簇，不同 group 的簇叠画在同一位置。 |

`overlap` 适合表示“总量和其中的分量”，例如参考文献里的 Intra-domain / Global / Inter-domain。它的画法是：
- 均值大的 group 先画，排在后面，颜色浅；
- 均值小的画在前面，颜色深。

柱子的配色规则与点线图相同。

花纹画在填充色上、用边框色，黑白打印也能分清各方案：
- 种类：`diag`（斜线 /）、`back`（反斜线 \）、`cross`（斜网格）、`horizontal`、`vertical`；`none` 为无。
- 每种有三档疏密：加后缀 `_dense` 为密，`_sparse` 为疏，如 `diag_dense`、`back_sparse`。这已是 Origin 内置花纹的全部档位，密档仍比 RCWA 原图稀。
- 写在 `encode.pattern`（整个面板）或单条的 `pattern`。`encode.pattern` 写成列表时按 name 轮换，如 `["diag_dense", "back_dense"]` 得到斜线、反斜线交替（RCWA 文献的样式）。

其他外观由预设的 `bar` 一节控制：
- 横轴刻度：刻度朝内时不画（会压在柱子的分界线上）；`style.axis.ticks` 为 `out` 时画朝外的主刻度（簇中央），有次刻度时次刻度落在两簇之间（RCWA 文献的样式）；
- 边框颜色：`border`，默认 #1A1A1A；
- 边框宽度：`border_width`，默认 0.5 pt；
- 簇间距：`gap`，默认 30%。

## 8. 双纵轴

把一组数据画在右纵轴上（文献 RCWA Fig.5：柱为阻塞率、线为密钥利用率）：

```json
{"type": "bar", "data": "data.csv", "x": {"col": "ratio", "title": "..."},
 "y": {"title": "Blocking probability", "range": [0, 0.5]},
 "series": [{"y": "BP_XTP", "name": "RCWA-XTP"}, {"y": "BP_SP", "name": "RCWA-SP"}],
 "y2": {"title": "Key utilization", "range": [0.4, 1.0], "step": 0.1, "hint": true,
        "series": [{"y": "KU_XTP", "name": "RCWA-XTP"}, {"y": "KU_SP", "name": "RCWA-SP"}]}}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `series` / `matrix` | 必填其一 | 右轴的曲线，写法同 §3，与左轴共用面板的数据和横轴。 |
| `type` | `line` | `line` 或 `scatter`（右轴不画柱）。 |
| `title`、`range`、`step`、`decimals`、`scale`、`factor` | 自动 | 同 §5。 |
| `hint` | `false` | 写 `true` 时用虚线圈住右轴曲线的末端，再用箭头指向右纵轴，提示这些线读右边的刻度。圈的高度为末端各点的范围加上下各 3% 轴高；图例会避开圈和箭头，实在避不开时 `warnings` 里报重叠，这时调 `y2.range` 让末端离开图例。 |

- 左右两轴一起分配样式：同名的柱和曲线同色，读者能把同一方法的两项指标对应起来。
- 图例默认左右各一个（`legend.layout: "split"`），分放两侧的角上，第二个会避开第一个；写 `"layout": "matrix"` 合成一个图例，按轴分行，行首为轴标题。
- 右纵轴的留白自动按刻度值宽度预留。
- 不能与断轴同时使用。

## 9. 误差棒

- 在 series 里写 `"yerr": "列名"`，或在 matrix 里写 `"yerr"` 模板。
- 误差值是对称的 ±err。
- 点线图的误差棒与曲线同色、同线宽；柱状图的误差棒用柱的边框色。
- 端帽宽度由 `style.errorbar.cap` 设置，默认 4。
- 自动坐标范围和图例避让都会把误差棒算进去。
- 插图里不画误差棒。

## 10. 插图

在主图里把一段局部放大显示。

```json
"inset": {"x": [57, 63], "y": [0.898, 0.914], "box": [0.02, 0.4, 0.5, 0.38]}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `x`、`y` | 必填 | 要放大的数据范围。 |
| `box` | `[0.02, 0.4, 0.5, 0.38]` | 插图所占的区域 `[左, 上, 宽, 高]`，用主框的比例表示，原点在左上角。 |
| `series` | 全部 | 插图里画哪几条曲线（序号从 0 开始）。 |
| `xstep`、`ystep` | 自动 | 插图的刻度间距。 |
| `titles` | `true` | 是否显示插图的轴标题（沿用主图的标题，字号更小）。 |
| `mark` | `true` | 是否在主图里用虚线椭圆圈出被放大的范围。 |
| `arrow` | `true` | 是否画一支从椭圆指向插图框的箭头。 |
| `arrow_to` | 插图框离椭圆最近的角 | 箭头终点（主图的数据坐标 `[x, y]`），箭头压线时用它换个落点。 |

`box` 的区域包含插图的刻度值和标题；插图坐标框会自动让出左侧和下方的文字位置。

虚线椭圆的中心是放大范围的中点，半径为放大范围半宽、半高的 1.15 倍。build 输出的 `panels[i].inset` 里有插图框的位置（`frame_cm`，以及换算到主图数据坐标的 `frame_data: [x0, x1, y0, y1]`）、椭圆和箭头终点，可以据此检查是否压线。

选放大范围：只框主图里挤在一起、分不清的那几条，纵向范围要比主图小得多才有放大效果；本来就分得开的曲线可以留在插图外。

摆放插图时，`box` 要避开：
- 图例（底部约 25% 的高度）；
- 被放大的那段曲线本身。

## 11. 标注

`marks` 是一个列表，坐标都用数据坐标：

```json
"marks": [
  {"type": "bracket", "x": 91.5, "y": [0.776, 0.920], "text": "18.2%", "color": "#9C8A3C"},
  {"type": "text", "text": "峰值", "at": [60, 0.95]},
  {"type": "arrow", "from": [40, 0.8], "to": [50, 0.9]},
  {"type": "line", "from": [15, 0.9], "to": [95, 0.9], "dash": "short_dash"},
  {"type": "rect", "from": [55, 0.88], "to": [65, 0.93]},
  {"type": "ellipse", "center": [60, 0.91], "radius": [4, 0.01], "dash": "dash"}
]
```

| type | 字段 |
|---|---|
| `bracket` | 带端帽的竖线，文字竖排在一侧，常用来标提升百分比。字段：`x`、`y: [下, 上]`、`text`、`side`（`right`/`left`）、`dx`（文字中心离竖线的距离，默认 0.16 cm；最后一个点离右框很近时取 0.13 左右）、`cap`（端帽半宽，默认 0.08 cm）。 |
| `text` | 文字。字段：`text`、`at: [x, y]`（文字中心的位置）、`rotate`（角度）。 |
| `line` / `arrow` | 线段或箭头。字段：`from: [x, y]`、`to: [x, y]`。 |
| `rect` | 矩形框。字段：`from`、`to`，为两个对角点。 |
| `ellipse` | 椭圆，由短线段拼成（不是数据曲线，不会混进图例）。字段：`center`、`radius: [rx, ry]`。 |

所有类型都可以加 `color`、`width`（pt）、`dash`、`size`（字号，pt）。

`bracket` 另有 `"style": "arrow"`：画成双向箭头、不带端帽（JSAC 文献标 60% 提升的写法），文字默认横排，放在箭头左侧或右侧（`side`），`dx` 为文字到箭头的间隙（默认 0.06 cm）。`rotate` 可指定文字角度（端帽样式默认 90，即竖排）。

## 12. 热力图

```json
{"type": "heatmap", "caption": "(a) \\i(η) = 0.1", "palette": "olive",
 "rows": ["WF", "TO", "SF"], "cols": [0.1, 0.2, 0.3],
 "values": [[0.8768, 0.8768, 0.8764], [0.8095, 0.8145, 0.8128], [0.8294, 0.8355, 0.8416]],
 "x": {"title": "\\i(m)"}, "colorbar": {"title": "Success Probability"}}
```

数据有两种写法：
- `values`：二维数组，第一行显示在最上方，并配上 `rows`（行标签）和 `cols`（列标签）。
- `data`：一张表。第一列是行标签，其余各列的列名就是列标签。

`cols` 全为等距数值时（Excel 表头存成文本 "0.1" 也算），按数值坐标画；否则按分类标签画，标签写在每列下方。两种情况都可以写 `x.title`。

| 字段 | 默认 | 说明 |
|---|---|---|
| `palette` | `"olive"` | 可以是 `olive`、`green`、`ocean`、任一色系名，或颜色列表（由浅到深，按 sRGB 线性插值）。 |
| `z.min` | `"shared"` | 色标下限。`shared`：同图所有热图的最小值，向下取整到 0.01；`own`：本幅最小值；也可以直接写一个数。 |
| `z.max` | `"own"` | 色标上限。`own`：本幅最大值，保留 3 位小数；`shared`：同图所有热图的最大值；也可以直接写一个数。 |
| `cells.show` | `true` | 是否在格内显示数值。 |
| `cells.decimals` | 4 | 格内数值的小数位数。 |
| `cells.color` | `"auto"` | 格内数值的颜色。`auto`：白字（参考图风格），只有白字几乎看不清的浅色格（与白色对比度低于 1.8）改用深色字；也可以写定一个颜色，如 `"#FFFFFF"` 全白。全局默认在 `style.heatmap.cell_color`，面板的 `cells.color` 优先。 |
| `cells.size` | 6.5 | 格内数值的字号（pt）。 |
| `colorbar.title` | — | 色标标题，竖排在热图与色标之间。 |
| `colorbar.ticks` | 6 | 色标的刻度个数。 |
| `colorbar.decimals` | 3 | 色标刻度值的小数位数。 |
| `colorbar.gap` | 0.45 | 色标与热图的间距（cm）。 |
| `colorbar.width` | 0.25 | 色标的宽度（cm）。 |
| `colorbar.size` | 6.5 | 色标文字的字号（pt）。 |
| `colorbar.show` | `true` | 是否显示色标。 |

多幅热图上下排列时，用默认的 `layout.rows`（每行一幅）即可。

## 13. style：覆盖预设

`style` 里的键与 `presets/paper.json` 一致，只写要改的项。例如：

```json
"style": {"font": {"size": 8, "title": 9}, "line": {"width": 0.5},
          "panel": {"line": {"frame": [7, 5]}}, "legend": {"size": 7}}
```

| 键 | 内容 |
|---|---|
| `font` | `face`（西文字体）、`cjk`（中文字体）、`size`（刻度值字号）、`title`（轴标题字号）。 |
| `axis` | `thickness`（轴线粗细）、`tick_length`、`tick_width`、`ticks`（`in`/`out`/`none`）、`minor`（相邻主刻度之间的次刻度个数，方向同主刻度；对数轴为每十倍 8 个）、`grid`（网格：`color`、`style`、`width`）、`factor`（`auto` 或整数）、`y_ticks`（纵轴大约几个刻度）、`title_gap`（纵轴标题再往外移多少 cm）。 |
| `encode` | 各面板 `encode` 的默认值（§4），如 jsac 的分类配色和形状、线型顺序。 |
| `line` | `width`（线宽）、`symbol`（第一组符号大小）、`symbol_step`（每组增量）。 |
| `legend` | `size`、`min_size`、`margin`（距框边）、`side_gap`、`clear`（与数据的间隙）、`symbol_width`（符号宽度，% 字宽）、`tab`、`line_space`、`columns`、`layout`、`frame`、`auto`（自动定位依次尝试的位置）、`brace`（大括号的 `width`、`gap`、`size`、`line_width`、`color`）。 |
| `panel` | `line`、`bar`、`heatmap` 三类面板各自的 `frame` 和 `margin`。 |
| `caption` | `size`、`gap`（与轴标题的间距）、`height`（为子图标题预留的高度）。 |
| `layout` | `gap`、`outer`（页面四周留白）。 |
| `bar` | `gap`（簇间距 %）、`border`、`border_width`、`pattern`（默认花纹）、`pattern_width`。 |
| `errorbar` | `cap`（端帽宽度）。 |
| `heatmap` | `palette`、`levels`、`cell_decimals`、`cell_color`、`cell_size`、`grid`、`grid_width`、`ticks`，以及 `colorbar` 的默认值。 |
| `inset` | `size`（插图字号）、`tick_length`。 |
| `mark` | `width`、`size`（标注的默认线宽和字号）、`hint_color`（`y2.hint` 的颜色）。 |

长度单位是 cm，字号和线宽的单位是 pt。

预设文件可以写 `"extends": "paper"`，只列与底稿不同的项（`presets/jsac.json` 就是这样写的）。

## 14. LabTalk 兜底

spec 管不到的细节，可以用 LabTalk 处理：
- 面板的 `labtalk`：在该面板的图层上执行，`layer.*`、`legend` 等都指向这个面板。
- 顶层的 `labtalk`：在全部画完后，在图页上执行。

Origin 不认识的命令会让 `warnings` 里出现“labtalk 第 n 条执行失败”。但属性名写错（如 `layer.x.tiks`）或对象不存在时，Origin 静默忽略、不报错，改完要看图，或用 `lt --get`、`inspect` 核对。

常用属性和已知的坑见 [labtalk.md](labtalk.md)。

改已有的成品：

```
origin-cli lt out/fig5.opju --layer 2 --run "layer.y.to=1.05;" --get "layer.y.from,layer.y.to" --save
```

## 15. build 的输出

```json
{"files": [".../fig5.opju", ".../fig5.png", ".../fig5.pdf"],
 "graph": "Graph1",
 "page_cm": [16.05, 6.7],
 "mode": "normal",
 "warnings": [],
 "panels": [{"index": 0, "type": "line", "frame_cm": [1.35, 0.3, 6.2, 4.9],
             "legend": {"size_pt": 6.5, "width_cm": 3.1, "height_cm": 0.27, "pos": "bottom",
                        "offset": -0.15, "extended": true, "overlap": false},
             "x": [15, 95], "y": [0.45, 1.035],
             "styles": [{"color": "#B0C4E0", "shape": "diamond", "interior": "solid", "size": 3,
                         "dash": "solid", "width": 0.37}]}]}
```

- `graph`：图页的短名，`lt` 命令的 `--graph` 和 LabTalk 里引用图页时用。
- `mode`：`normal` 表示隐藏的普通实例，导出的图正常。`automation` 时，导出的图文字上方可能有横线，处理方法见 SKILL.md。
- 有插图时，面板里还有 `inset`（插图框位置、椭圆、箭头终点）。
- 标注文字伸出坐标框时，`warnings` 里会提示。
- `legend.box_cm` 是图例（连同大括号和组名）的位置 `[左, 上, 宽, 高]`。
- 双纵轴面板另有 `y2`（右轴范围）和 `legend2`（右轴图例）。
- 热力图面板没有 `legend` 和 `styles`，改为 `z: [色标下限, 上限]`。色标上限按 3 位小数四舍五入，略高于上限的格子显示为最深色。
