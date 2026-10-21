# Tumu Roadbook

当前版本：`0.2.0`

YAML 驱动的自驾路线图生成器。输入行程数据后，脚本会解析坐标、计算公路路线、执行基础行程校验，并输出可离线打开的交互式 HTML。

仓库地址：<https://github.com/tumu987/tumu-roadbook>

## 环境

- Python 3.9+
- PyYAML

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

## 生成路线图

```bash
python generate.py trips/zhuozhang-4d.yaml --output docs/zhuozhang-4d.html
python generate.py --version
```

也可以分步运行：

```bash
python resolve.py trips/zhuozhang-4d.yaml
python render.py resolved/zhuozhang-4d.json
```

默认产物写入 `output/`。`resolved/`、`output/` 和 `.cache/` 都是本地产物，不提交到 Git。

`generate.py` 还会扫描 `trips/*.yaml` 并自动重建 `docs/index.html`。也可以单独执行：

```bash
python build_index.py
```

## 行程数据

行程文件位于 `trips/`。`trip.drivers` 表示主驾人数：

```yaml
trip:
  title: 示例行程
  drivers: 2

days:
  - day: 1
    route:
      start: [39.9042, 116.4074]
      via: [[38.0428, 114.5149]]
      end: [36.2000, 113.4390]
```

单主驾高速、山路每日上限分别为 400km、150km；双主驾为 700km、300km。超过上限时生成器会给出告警。

### 数据结构校验

行程 YAML 使用 `schema/trip.schema.json`（JSON Schema Draft 2020-12）校验字段类型、必填项、枚举、坐标范围和时间轴节点结构。文件顶部的 `yaml-language-server` 声明可为支持 YAML Language Server 的编辑器提供补全和即时错误提示。

Schema 负责结构校验；地名解析、OSM 对象核验、重复检查、路线计算和行程风险仍由 Python 语义校验处理。

### 景点坐标严格核验

重要行程可以开启严格模式：

```yaml
trip:
  coordinate_verification: strict

pois:
  - name: 示例景点
    coord: [36.187171, 113.100345]
    rank: major
    coord_source: osm
    osm_id: way/1171947665
    verified_at: "2026-10-21"
```

严格模式要求所有 `major` 景点提供 OSM 对象编号。生成时会从 OSM 读取对象坐标；当前坐标偏差超过 750m 或网络核验失败时，生成会终止，不会继续输出可能错误的路线图。

### 单一日程时间轴

设置 `trip.timeline_mode: merged` 后，每日卡片直接显示 `timeline`，并校验当天不得再提供重复的 `items`。适合已经把行程整理成可执行时间轴的路线；未设置时保持原来的“每日详情 + 可折叠微观日志”模式。

时间轴节点支持两类时间表达：

```yaml
timeline:
  - time: "08:00"
    action: "从住处出发"
    kind: fixed
  - duration: "40分钟"
    action: "平顺 → 大云院"
    kind: drive
  - duration: "30分钟"
    action: "大云院：五代壁画"
    kind: visit
```

`time` 用于出发、闭馆、日落等必要锚点；`duration` 用于车程、游览、用餐和休息。游览节点会显示为“预计30分钟”，其他弹性节点显示为“约1小时”。

### 风险与强度

每日卡片会在时间轴内展示里程、海拔、迎光驾驶和路线近似等风险，并根据时间轴计算计划总耗时，标记为“轻松、正常、偏紧、不建议”。如果 OSRM 无法返回真实道路，地图路线会改为虚线并显示近似路线警告。

## 目录

```text
trips/       行程 YAML
archive/     已停用的历史行程备份
templates/   HTML、CSS、JavaScript 模板
docs/        已生成的发布页面
build_index.py  从行程 YAML 汇总生成路线册首页
resolved/    本地解析缓存（忽略提交）
output/      本地 HTML 产物（忽略提交）
```

## 测试

```bash
python -m unittest discover -s tests -v
```

## 外部服务

生成阶段会使用 Nominatim、OSRM 和 Open-Elevation。结果缓存在 `.cache/`。标准地图使用 Esri Light Gray Canvas 底图和低透明度交通网络，地形图使用 Esri Topographic。生成后的 HTML 仍需联网加载底图；公共接口不可用时，程序会降级为直线路径并在终端提示。
