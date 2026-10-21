# 自驾游路线图生成器 — 项目书

## 1. 项目目标

开发一个数据驱动的 HTML 路线图生成工具，使得**未来任何自驾行程**只需编写一份 YAML 数据文件，运行一条命令即可生成完整可用的交互式 HTML 路线图。免去手动编辑数千行 HTML/CSS/JS 的重复劳动。

## 2. 核心原则

| 原则 | 说明 |
|------|------|
| **数据与表现分离** | YAML 只写"去哪儿、住哪儿、有什么景点"，不关心颜色、坐标、样式 |
| **一次配置，到处生成** | 行程模板固定后，配色、标注、路线层逻辑由脚本统一处理 |
| **可复现** | 同样数据文件在任何机器产出同样的 HTML（OSRM 在线 API 除外） |
| **渐进增强** | 先覆盖晋东南需求的全部功能，再抽象为通用工具 |

## 3. 数据文件规格（YAML）

```yaml
# trips/jindongnan.yaml — 示例
trip:
  title: 晋东南古建自驾
  subtitle: 浊漳河谷 · 长治 · 高平 · 皇城
  dates: "6月8日 — 6月14日"
  basemap: light          # light / dark / terrain
  drivers: 2              # 1 = 单主驾，2 = 双主驾
  coordinate_verification: strict
  timeline_mode: merged   # 每日详情直接使用 timeline

days:
  - day: 1
    label: "6/8（一）"
    theme: "北京 → 浊漳河谷"
    start: [39.9042, 116.4074]      # 出发地坐标
    via: [[38.0428, 114.5149]]      # 经停（可选）
    end: [36.200, 113.439]          # 目的地坐标
    distance: "576km · 6.8h"
    items:
      - "早 7:00 从北京出发"
      - "龙门寺 | ⭐ 六朝木构于一寺"
      - "淳化寺 | 金代大殿"
      - "🏨 宿平顺/河谷区"
    pois:
      - name: 龙门寺
        coord: [36.390227, 113.623042]
        rank: major          # major / minor
        dynasty: 五代
        coord_source: osm
        osm_id: way/1252171732
        verified_at: "2026-10-21"
      - name: 淳化寺
        coord: [36.25, 113.58]
        rank: major
```

同一天若有多条路线段（如 D7 皇城→交汇点 + 北京段），用 `segments` 表示。

### 数据文件设计原则

- 坐标支持 `[lat, lng]` 数组
- 每条路线段支持 `start → via[] → end` 三级
- 经停点 `via` 不显示为住宿点或城市标签，仅用于指引 OSRM 算路
- 城市标签／住宿城市从 `start / end` 智能推断
- 主要景点（major）和次要景点（minor）在 YAML 中声明，脚本自动按 zoom 级别分层显示

## 4. 脚本功能（generate.py）

### 4.1 工作流

```
YAML 数据 → OSRM 算路 → 颜色分配 → 标签定位 → HTML 输出
```

### 4.2 子模块

```
generate.py
├── 1. 读 YAML
├── 2. OSRM 路线计算       # 调用在线 OSRM API，获取真实公路 polyline
├── 3. 颜色分配             # 从预设色盘轮取每日路线色
├── 4. HTML 模板渲染        # Jinja2 或 f-string 模板
│   ├── 地图层（Leaflet）
│   ├── 路线层（多段线 + zoom 分层）
│   ├── 标注层（景点 + 城市标签 + 避让定位）
│   └── 卡片层（时间轴 + 每日卡片）
└── 5. 输出 HTML
```

### 4.3 OSRM 算路

- 使用 `https://router.project-osrm.org/route/v1/driving/...` 在线服务
- 返回的 polyline 坐标存入 HTML 内联变量
- 支持带 `via` 经停的多段路线
- **限流保护**：最多 2 个并发请求，失败后重试 1 次，避免被 OSRM 封 IP

### 4.4 颜色系统

预设色盘（7 色，与晋东南一致）：

| 索引 | 色号 | 用途 |
|------|------|------|
| 0 | `#e74c3c` | D1 |
| 1 | `#f39c12` | D2 |
| 2 | `#27ae60` | D3 |
| 3 | `#00bcd4` | D4 |
| 4 | `#3f51b5` | D5 |
| 5 | `#9c27b0` | D6 |
| 6 | `#e91e63` | D7 |

行程超过 7 天时从索引 0 循环（第 8 天复用 D1 色，但用虚线或透明度区分）。

### 4.5 标签避让算法

沿用晋东南验证过的两套参数：

| 缩放级别 | 最小间距 | 试探步数 |
|----------|----------|----------|
| zoom < 9（总览） | 0.08° | 20 步 |
| zoom ≥ 9（详情） | 0.025° | 8 步 |

算法：目标坐标周围 8 方向（N/NE/E/SE/S/SW/W/NW）递增距离试探，排除路线途经点的干扰。

### 4.6 Zoom 分层

| 层级 | 显示内容 |
|------|----------|
| zoom < 9 | 干线（D1/D7）淡显，城市名称 + 引线，Dx 标签 |
| zoom ≥ 9 | 所有路线 + 主要景点（major） |
| zoom ≥ 10 | 次要景点（minor） |

支线/支脉逻辑可配置（YAML 中 `route_class: main / branch / minor`）。

## 5. 模板系统

### 5.1 输出结构

生成的 HTML 为**单文件自包含**（静态文件，零后端依赖），结构：

```html
<!DOCTYPE html>
<html>
<head>
  <style> /* 统一样式：地图、卡片、响应式、配色变量 */ </style>
</head>
<body>
  <!-- 行程标题 + 日期 -->
  <!-- Leaflet 地图（路线 + 标注 + 图例） -->
  <!-- 时间轴 + 每日卡片 -->
  <!-- JS：地图初始化、路线绘制、分层逻辑、避让算法 -->
  <script src="CDN leaflet.js"></script>
</body>
</html>
```

CDN 依赖仅限 Leaflet（CSS + JS），其余全部内联。

### 5.2 样式变量化

CSS 中使用的颜色、字号、间距通过 Python 字符串模板注入，不硬编码在模板中。

## 6. 目录结构

```
tumu-roadbook/
├── VERSION                  # 当前版本
├── CHANGELOG.md             # 版本变更记录
├── README.md                # 安装与使用说明
├── requirements.txt         # Python 依赖
├── generate.py              # 主生成脚本
├── templates/
│   ├── map.html             # 页面结构
│   ├── map.css              # 页面样式
│   └── map.js               # 地图与标签逻辑
├── trips/
│   ├── jindongnan.yaml      # 晋东南数据
│   └── ...                   # 未来行程
├── docs/
│   ├── index.html            # 路线册索引
│   └── *.html                # 已发布产物
├── tests/                    # 校验与算路回归测试
├── output/                   # 本地临时产物（忽略提交）
├── resolved/                 # 本地解析缓存（忽略提交）
└── PROJECT.md               # 本文件
```

## 7. 后续扩展（V2）

- 暗色版自动生成（`basemap: dark` 时切换底图和配色）
- PDF / 分享版（内嵌打印样式）
- 多行程索引页
- 已有行程的 YAML 逆向工程（从现有 HTML 提取数据）
- 行程耗时估算辅助（根据景点密度调整）

## 8. 时间线（预估）

| 阶段 | 内容 | 预估 |
|------|------|------|
| P0 | generate.py 骨架 + YAML 解析 + 晋东南迁移验证 | 半天 |
| P1 | OSRM 集成 + 路线渲染 + zoom 分层 | 半天 |
| P2 | 标签避让算法移植 + 景点标注 | 半天 |
| P3 | 卡片 / 时间轴 + 配色系统 | 半天 |
| P4 | 输出 HTML 验收（对比当前 v0.1.1 效果） | 半天 |
| P5 | 调优、首份新行程测试 | 柔性 |

## 9. 验收标准

1. 运行 `python generate.py trips/jindongnan.yaml` 生成的 HTML，视觉和交互效果**不低于**当前手动维护的 v0.1.1
2. 同样的 YAML 文件在别的机器能生成同样的结果（OSRM 返回的 polyline 可能有细微差异，不影响视觉）
3. 数据文件去掉 1 天或添加 1 天，输出自动适配，无需碰代码
4. 标签避让在晋东南场景下不出现堆叠（zoom 7-13 范围测试）
