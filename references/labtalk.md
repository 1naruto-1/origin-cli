# Origin 2024 自动化：验证过的写法与坑

本文的每一条都在本机 Origin 2024（10.1.0.178）上用 spike 脚本验证过；脚本在 `origin-cli-workspace/spike/`。
写面板的 `labtalk` 字段、使用 `lt` 命令，或者修改 `origin_cli/` 的代码之前，先看这里。

## 目录

1. [启动与退出](#1-启动与退出)
2. [格式树与 Origin C 辅助函数](#2-格式树与-origin-c-辅助函数)
3. [页面与图层](#3-页面与图层)
4. [曲线样式](#4-曲线样式)
5. [柱状图与误差棒](#5-柱状图与误差棒)
6. [坐标轴](#6-坐标轴)
7. [文字](#7-文字)
8. [图例](#8-图例)
9. [热力图与色标](#9-热力图与色标)
10. [标注对象](#10-标注对象)
11. [导出](#11-导出)
12. [排查问题的习惯](#12-排查问题的习惯)

---

## 1. 启动与退出

### 文字上划线问题

Origin 2024 以 COM 自动化服务器方式启动时，导出图片里所有文字的上方都会多一条横线。这个 bug 在 2024b 才修复，设置 `@TO` 也无效。

绕开的办法是：用普通方式隐藏启动，再连接上去。步骤：
1. 执行 `Origin64.exe -h`；
2. 轮询它的主窗口标题（窗口类名以 `Afx:0000` 开头），直到标题里出现 `" - "`，约需 4 秒；
3. 调用 `originpro.attach()`。

连接之后：
- 用 Origin C 的 `GetCurrentProcessId()` 核对 PID，确认连上的就是自己启动的那个实例；
- 本机已有 Origin 在运行时，attach 可能连到用户的实例。此时改用自动化实例，并提示用户上划线问题。

### 其他启动细节

- 普通方式启动时，要先执行 `sec -poc;`，否则 `run.loadoc` 会返回 8。
- 命令行参数 `-rs` 附带的脚本在这种启动方式下不会执行，不要依赖它。

### 退出

1. 执行 `doc -s; op.exit()`；
2. 等待进程退出；
3. 再强制结束**自己的** PID 及其子进程。Origin 崩溃时会弹出 CrashSender 报错窗口，它是 Origin 的子进程，也要一并结束。

绝不要按进程名结束 Origin，那样会连带关掉用户自己的 Origin。

## 2. 格式树与 Origin C 辅助函数

### fmt.c

`origin_cli/fmt.c` 提供三个函数：
- `fmt_dump`：读出格式树（GetFormat）；
- `fmt_apply`：应用格式树（ApplyFormat）；
- `oc_pid`：返回当前进程 PID。

编译与加载的注意事项：
- 文件必须是 **UTF-8 带 BOM**，否则 `run.loadoc` 返回 2。
- 路径必须用**反斜杠**，否则返回 3。

### 只应用“小树”

格式树只写要改的节点，例如：

```xml
<OriginStorage><Root><Symbol><FillColor>-4</FillColor></Symbol></Root></OriginStorage>
```

- 应用前要调用 `UpdateThemeIDs(tr.Root)` 补上节点 ID，否则不会生效。
- `fmt_apply` 的返回值：0 表示成功；100 + n 表示有 n 个节点不认识（节点名写错时就会这样，例如误差棒的节点是 `ErrorBar2D`，不是 `ErrBar`）。

### 严禁回写完整的树

**绝不要**把 GetFormat 得到的完整树用 ElementTree 读进来、修改后再写回去：里面的二进制块节点会被命名空间改坏，Origin 直接崩溃，并弹出 “Origin has stopped working” 窗口。

### 读取节点名

想知道某个属性的节点名，先 dump 一份看看：

```python
s.dump(graph, layer, plot=k)   # {'Symbol/Size': '3', 'Line/Width': '0.37', ...}
```

常用节点：

| 节点 | 含义 |
|---|---|
| `Symbol/FillColor` | -4 为无，-9 为自动 |
| `Line/LineSymbolOrder` | 2 表示线在符号后面、不断开 |
| `Pattern/Fill/FillColor` | 柱的填充色 |
| `Pattern/Border/Color`、`Pattern/Border/Width` | 柱的边框 |
| `Spacing/Gap` | 柱间距 |
| `ErrorBar2D/CapWidth` | 误差棒端帽宽度 |
| `Stack/Offset` | 堆叠，写在图层上，值为 1 |
| `Arrow/End/Style`、`Width`、`Length` | 箭头，写在线对象上；`Arrow/Begin/...` 为起点箭头（双向箭头两个都设） |
| `Axes/X/Grids/VerticalMajorGrids/Show`、`Color`、`Style`、`Width` | 竖向主网格线（图层上）；横向为 `Axes/Y/Grids/HorizontalMajorGrids/...`。`Style` 的编号与 `set -d` 相同（5 为 short dash） |
| `Axes/Y/Labels/LeftLabels/DivideByFactor` | 刻度值除以的因子，字符串，如 `"1E5"`；右轴为 `RightLabels` |
| `Background/Border/Color`、`Width`、`Style` | 图例（或文字对象）的边框，配合 `legend.background = 1`；`Background/Fill/Color` 为底色 |
| `Pattern/Fill/Pattern/Style`、`PatternColor`、`Width` | 柱的花纹，见第 5 节 |

格式树里的颜色是 `0x01BBGGRR` 形式的整数，用 `op.ocolor('#RRGGBB')` 生成。

## 3. 页面与图层

**页面**：

```
page.kar=0; page.resx=600; page.resy=600; page.width=<点>; page.height=<点>;
```

页面单位是 1/600 英寸（点）。

**图层**：

```
layer.unit=3; layer.left=..; layer.top=..; layer.width=..; layer.height=..;
```

`unit=3` 表示单位为 cm。定位后**立刻**执行 `page -afu1;`，把缩放因子固定为 1。否则之后设置的字号和线宽会按图层大小缩放。踩过的坑：色标图层很窄，刻度值被缩到 0.5 pt，看不见了。

**新增图层**：用 `g.add_layer(0)`。图层上的属性在该图层的 `lt_exec` 里设置。

**切换活动图层**：用 `page.active = n;`。写成 `layer2.x.from` 的语法在这里取不到值（返回 `--`）。`lt --layer n` 就是靠 `page.active` 实现的。

**右纵轴图层**：
1. 先 `page.active = n;` 激活主图层；
2. `g.add_layer(2)`（即 `layadd type:=righty`），新图层与主图层同框、横轴联动，`layer.unit` 为 7（相对主图层的百分比，0–100）；
3. 随即 `page -afu1;`；
4. 设置 `layer.x.showAxes=0; layer.x.showLabels=0;` 隐藏横轴，`layer.y.showAxes=2; layer.y.showLabels=2; layer.y.ticks=0; layer.y2.ticks=...` 只显示右侧的纵轴，刻度值格式用 `layer.y2.label.*`，标题用 `label -yr`。

图例里可以用 `\l(2.1)` 引用第 2 个图层的第 1 条曲线，所以一个图例能同时列出左右两轴的曲线。

## 4. 曲线样式

`set` 命令的选项（在 originpro 里用 `plot.set_cmd('-k 5', '-kf 1', ...)`）：

| 选项 | 含义 | 取值 |
|---|---|---|
| `-k` | 形状 | 1 方 2 圆 3 上三角 4 下三角 5 菱形 6 加号 7 叉 9 横杠 10 竖杠 15 左三角 16 右三角 17 六边形 18 星 19 五边形 |
| `-kf` | 内部 | 0 实心 1 空心 2 带点 3 hollow 8 上半 9 右半 10 下半 11 左半 |
| `-d` | 线型 | 0 实线 1 dash 2 dot 3 dash dot 4 dash dot dot 5 short dash 6 short dot 7 short dash dot |
| `-wp` | 线宽 | 单位 pt，0.37 就写 0.37 |
| `-z` | 符号大小 | 单位 pt |
| `-gm 1` | 组内独立编辑 | 不加时，组内各曲线的颜色由组的递增列表决定，单独设的颜色无效 |

颜色直接用 `plot.color = '#RRGGBB'` 设置。

空心和半填充符号还需要格式树 `{'Symbol': {'FillColor': -4}}`，未填充部分才是透明的。只用 `-kf` 的话，未填充部分用的是默认填充色（不透明），会盖住后面的连线。

## 5. 柱状图与误差棒

**误差棒**：

```python
L.add_plot(wks, y, x, colyerr=e, type='y')
```

误差棒是一条单独的曲线，紧跟在它所属的曲线后面。这有两个后果：
- 它占用图层里的一个序号，图例里的 `\l(n)` 要相应顺延；
- 设置它的样式时，要单独拿到这条曲线：`.color`、`set -wp`，以及 `ErrorBar2D/CapWidth`。

**分组柱 + 误差棒**：

- 逐条 `add_plot(..., colyerr=...)` 之后再用 `layer -g` 建组，组里夹着误差棒，柱子**不会并排**。
- 正确的做法是每一簇用一次 plotxy：

```
plotxy iy:=[Book]Sheet!((1,2,3),(1,4,5),(1,6,7)) plot:=203 ogl:=[Graph]1!;
```

这样画出来，同簇的柱自动成组并排；误差棒排在这一组之后，各自跟着自己的柱。图层里的顺序是：这一簇的所有柱，然后是它们的误差棒。

**堆叠**：在图层上应用格式树 `{'Stack': {'Offset': 1}}`。

**花纹**：`Pattern/Fill/Pattern/Style` 的编号每三档一种（密、中、疏）：1–3 斜线 `/`，4–6 反斜线 `\`，7–9 斜网格，10–12 横线，13–15 竖线；0 为无。`PatternColor` 为花纹颜色，`FillColor` 仍是底色。

- 最密一档在 600 dpi 下线距约 46 px，仍比 RCWA 原图（约 19 px）稀。格式树里的 `Pattern/XScale`、`YScale` 能写进去、读回也对，但对内置花纹不起作用。要更密只能在 Origin 里换自定义花纹。

**偶发的设置不生效**：plotxy 刚画完时，偶尔取到的柱对象读回的格式树是空的，设置颜色也没有效果（导出图是 Origin 默认的浅色柱、彩色边框）。plotxy 之后先 `doc -uw;` 再取曲线对象，设置后读回 `Pattern/Fill/FillColor` 确认，不在就刷新后再设一次。

**分类横轴**：X 列写成文本列即可。Origin 按行号 1..n 定位，并用这列文字作刻度标签（`layer.x.label.type = 2`）。此后再设置 `numFormat` 也不会把标签改回数字。

## 6. 坐标轴

基本设置（以 x 轴为例，y 轴同理）：

```
layer.x.from=..; layer.x.to=..; layer.x.inc=..; layer.x.firstTick=..; layer.x.minorTicks=0;
layer.x.ticks=1;            // 1 主刻度朝内，2 朝外，0 无；再加 4（次刻度朝内）或 8（朝外），如 5 = 主次都朝内
layer.x2.ticks=0;           // 上轴不要刻度
layer.x.showAxes=3;         // 上下两条轴线都显示，形成封闭的框
layer.x.label.font=..; layer.x.label.pt=..; layer.x.label.numFormat=1; layer.x.label.decPlaces=..;
layer.x.thickness=..; layer.tickL=..; layer.tickW=..;
```

**对数轴**：

```
layer.y.type=2; layer.y.labelSubtype=2; layer.y.inc=1;
```

`labelSubtype=2` 让刻度值显示为 10ⁿ 形式；`inc=1` 表示每十倍一个刻度。

**断轴**：

```
layer.y.breaks.enable=1; layer.y.breaks.count=1;
layer.y.break1.from=..; layer.y.break1.to=..; layer.y.break1.pos=35; layer.y.break1.inc=..;
```

`pos` 的单位是 %。断点上下两段的刻度间距不同时，刻度值的小数位数要按两段中更细的那个取，否则会出现一串重复的 “1.0”。

**轴标题**：

```
label -xb "x"; xb.text$ = __t$;
label -yl "x"; yl.text$ = __t$;
```

注意：
- 模板自带的上轴、右轴标题（`xt`、`yr`）会在显示框线后冒出来，要用 `label -r xt; label -r yr;` 删掉。
- 不要依赖 `xb.top` 等读回的值，它们给出的位置不可靠。工具是按字号估算轴标题的下沿位置的。

**热图模板**：会把 x 轴刻度值旋转，要用 `layer.x.label.rotate=0;` 改回来。

## 7. 文字

**新建文字对象**：

```
label -n T1 "x"; T1.text$ = __t$;
```

文字先用 `op.set_lt_str('__t$', ...)` 放进字符串变量再赋值。这样可以避免 `%`、引号等字符被 LabTalk 当作替换符或语法。

**字体**：
- `font(Times New Roman)`、`font(宋体)` 能拿到字体编号；
- 中文字体的英文别名（如 SimSun）不行。

**中英混排**：中文片段用 `\f:宋体(…)` 包起来，其余字符沿用对象本身的字体。`Figure.rich()` 会自动做这件事。

**定位**，有两种方式：
- 按数据坐标：`T1.attach=2; T1.x=..; T1.y=..;`。x、y 是对象中心的位置，对象会随坐标轴一起移动。
- 按页面位置：先执行 `doc -uw;`，再读 `width`、`height`，然后设置 `left`、`top`（单位为点）。

**读回文字**：`GraphObject.GetText()` 会把 η、ω 等非 ASCII 字符转坏。要读回文字，从格式树的 `Text` 节点读。

**旋转**：`T1.rotate = 90;`。

## 8. 图例

1. 执行 `legendupdate mode:=0;`。
2. 用 `legend.text$ = __t$;` 写入图例文字：
   - `\l(n)` 是第 n 条曲线的图例符号；
   - 制表符分列，换行分行。
3. 设置外观：`legend.font=..; legend.fsize=..; legend.background=0;`，`background=0` 表示无边框、无底色。
4. 用格式树（作用在 `Legend` 对象上）调整排版：

```
{'TabWidth': 2, 'Symbol': {'LegendSymbolWidth': -60}, 'LineSpaceAuto': 0, 'LineSpace': -15}
```

| 节点 | 说明 |
|---|---|
| `LegendSymbolWidth` | 负数表示“字宽的百分比”；写正数基本没有效果。 |
| `TabWidth` | 制表符的宽度。 |
| `LineSpace` | 行距，要配合 `LineSpaceAuto: 0` 才生效。 |

关于列对齐：
- `MultiColAutoAlign` 会让各列内容同宽的矩阵自动对齐；
- 但表头行对不齐，所以工具不做带表头的表格式图例；
- 列表式图例分多行时，第一列文字宽度不同（如 “Ours” 和 “Base-B”），第二列也会左右错开，加大 `TabWidth` 反而更糟。所以柱状图图例默认排成一行。

**图例尺寸**：执行 `doc -uw;` 后，读 `legend.width`、`legend.height`（单位为页面点）。

**定位**：设置 `legend.left`、`legend.top`。

**Origin 会自动往图例里补条目**：
- 每往图层里加一条曲线（包括画椭圆用的辅助曲线），Origin 都会往图例里自动补一条。所以全部画完后，要把自定义的图例文字再写一遍。
- 新建图层（插图、色标）会自带图例，用 `label -r legend;` 删掉。全部画完后再删一次，因为刷新时它会重新出现。

## 9. 热力图与色标

**画热力图**：

```python
g = op.new_graph(template='heatmap')
ms = op.new_sheet('m'); ms.from_np(np.flipud(values)); ms.xymap = (x0, x1, 1.0, n_rows)
L.add_mplot(ms, 0, type=105)
L.rescale()             # 不 rescale 时，色阶属性还没初始化，设置会失败
```

`np.flipud` 是为了让第一行显示在最上方。

**删掉模板自带的对象**：`label -r SPECTRUM1; label -r legend;`。`SPECTRUM1` 是模板自带的色标。

**设置色阶**：

```
layer.cmap.zmin=..; layer.cmap.zmax=..; layer.cmap.numMajorLevels=64; layer.cmap.numMinorLevels=0;
layer.cmap.SetLevels(1);
layer.cmap.color1=color(#EFEB95); ... layer.cmap.color64=color(#6E500D);
layer.cmap.colorBelow=color(..); layer.cmap.colorAbove=color(..); layer.cmap.updateScale();
```

**色标**：单独占一个窄图层。做法如下：
- 用一个竖向渐变的矩阵画出色条，色阶设置与热图相同。用**图像图**（`add_mplot(ms, 0, type=220)`）而不是热图（105）：热图在 PDF 里是几百个相邻小矩形，开着抗锯齿的阅读器会显示出细横纹；图像图导出为一整张位图。图像图铺满 xymap 的范围，所以横轴取 0–1，不像热图那样要留半格；
- 刻度值放在右侧：`layer.y.ticks=0; layer.y2.ticks=2; layer.y.showLabels=2;`，再用 `layer.y2.label.*` 设置字体、字号和格式。

## 10. 标注对象

**线段**：

```
draw -n D1 -l {x1, y1, x2, y2}; D1.color=color(#000000); D1.lineWidth=0.75; D1.lineType=1;
```

坐标是数据坐标；`lineType` 等于线型编号加 1。

**箭头**：在线段对象上应用格式树 `{'Arrow': {'End': {'Style': 1, 'Width': 4, 'Length': 6}}}`。

**椭圆**：用 72 段短线段拼成，虚线时隔一段画一段。以前画成数据曲线，Origin 会在导出时往图例里补一条（存进 .opju 的文字是对的，导出的 PNG 却多了一行），所以改成线段。

**大括号**：同样用线段拼成（`layout.brace_points` 算出折线点），坐标由页面位置换算到数据坐标（`Figure.to_data`，考虑对数轴和断轴）。

## 11. 导出

- **PNG**：`g.save_fig(path, width=像素)`，像素宽 = 页面宽(cm) / 2.54 × dpi。导出后用 PIL 写入 dpi 信息。
- **TIF、JPG**：由 PNG 转出，带 dpi 信息；TIF 用 LZW 压缩。
- **PDF、SVG、EMF、EPS**：`g.save_fig(path)` 按扩展名导出矢量图。
- **自动化实例的问题**：用自动化实例导出的图片会有文字上划线（见第 1 节），.opju 本身没问题。

## 12. 排查问题的习惯

- **改图层属性优先写在面板的 `labtalk` 字段**：它在图层上执行、可复现。`lt --run` 在应用层执行，虽然先切了活动图层，仍遇到过读回的值已改、导出图却没变的情况；现在 `lt` 在保存和导出前会先 `doc -uw` 刷新，仍不对就改用面板 `labtalk` 重新 build。

- **`op.lt_exec` 的返回值说明不了属性有没有设成功。** 只有命令本身不存在时它才返回 False；属性名写错、对象不存在（如 `xb.left` 而图里没有 xb）都会被静默忽略。图层的 `lt_exec` 干脆不返回结果，要用 `L.obj.LT_execute` 拿返回值（build 执行 spec 里的 labtalk 时就是这样报失败的）。设置之后，用 `lt --get`、`inspect` 或读格式树确认。
- **一次只验证一件事。** 把最小复现写成 spike 脚本，放在 `origin-cli-workspace/spike/` 下，用 `Session()` 打开 Origin，导出 PNG 来看效果。结论补充到本文。
- **Origin 崩溃过一次后，先确认没有残留进程**，再开始下一次 build：工具启动时若发现 Origin 进程，会等待最多 8 秒。
