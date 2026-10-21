#!/usr/bin/env python3
"""
render.py — 自驾路线图渲染器

从 resolved JSON 读取完整数据，结合 templates/ 输出 HTML。

用法:
  python3 render.py resolved/xxx.json [--output output/xxx.html]

数据流:
  YAML → resolve.py → resolved/xxx.json → render.py → output/xxx.html
"""

from __future__ import annotations

import sys
import os
import json

from version import __version__

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_template(name: str) -> str:
    """读取模板文件"""
    path = os.path.join(TEMPLATE_DIR, name)
    if not os.path.exists(path):
        print(f"❌ 模板文件不存在: {path}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def load_leaflet():
    """返回内联 Leaflet JS 和 CSS"""
    base = BASE_DIR
    js_path = os.path.join(base, 'leaflet.js')
    css_path = os.path.join(base, 'leaflet.css')

    leaflet_js = ''
    leaflet_css = ''
    if os.path.exists(js_path):
        with open(js_path, 'r') as f:
            leaflet_js = f.read()
    if os.path.exists(css_path):
        with open(css_path, 'r') as f:
            leaflet_css = f.read()

    if not leaflet_js:
        leaflet_js = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
    else:
        leaflet_js = f'<script>{leaflet_js}</script>'

    if not leaflet_css:
        leaflet_css = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
    else:
        leaflet_css = f'<style>{leaflet_css}</style>'
    return leaflet_css, leaflet_js


def render(resolved_path: str, output_path: str | None = None):
    """读取 resolved JSON 并生成 HTML"""
    
    # ── 读 resolved JSON ──
    print(f"\n📖 读取 resolved: {resolved_path}")
    with open(resolved_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    trip = data.get('trip', {})
    cities = data.get('cities', [])
    pois = data.get('pois', {})
    routes_data = data.get('routes', {})
    dx_data = data.get('dx_data', [])
    sidebar_items = data.get('sidebar', [])
    day_card_items = data.get('day_cards', [])
    legend_html = data.get('legend_html', '')
    stats_html = data.get('stats_html', '')
    warnings_html = data.get('warnings_html', '')
    footer_html = f'Tumu Roadbook v{__version__} · YAML 驱动的自驾路线图'
    stop_css = data.get('stop_css', '')
    tile_url = data.get('tile_url', '')
    center = data.get('center', {"lat": 36.0, "lng": 113.5})
    main_routes = routes_data.get('main', [])
    spur_routes = routes_data.get('spur', [])
    major_spots = pois.get('major', [])
    minor_spots = pois.get('minor', [])
    
    title = trip.get('title', '自驾路线图')
    subtitle = trip.get('subtitle', '')
    focus = trip.get('focus')
    
    # ── 生成 route data JS ──
    route_js_parts = []
    # Route polylines: r_1, r_2, ...
    for idx, r in enumerate(main_routes):
        pts_str = json.dumps([[round(p[0],6), round(p[1],6)] for p in r['polyline']])
        route_js_parts.append(f'var r_{idx+1} = {pts_str};')
    for idx, r in enumerate(spur_routes):
        pts_str = json.dumps([[round(p[0],6), round(p[1],6)] for p in r['polyline']])
        route_js_parts.append(f'var sr_{idx+1} = {pts_str};')
    
    # mainRoutes / spurRoutes arrays
    main_routes_js = 'var mainRoutes = [\n' + '\n'.join(f"  ['{r['color']}', r_{i+1}]," for i, r in enumerate(main_routes)) + '\n];'
    if spur_routes:
        spur_routes_js = 'var spurRoutes = [\n' + '\n'.join(f"  ['{r['color']}', sr_{i+1}]," for i, r in enumerate(spur_routes)) + '\n];'
    else:
        spur_routes_js = 'var spurRoutes = [];'
    
    # City data
    cities_js = 'var cityPosData = ' + json.dumps(cities, ensure_ascii=False) + ';'
    
    # Dx data
    dx_data_js = 'var dxData = ' + json.dumps([{'name': d['name'], 'lat': d['lat'], 'lng': d['lng'], 'color': d['color'], 'dist': d['dist'], 'sub': d['sub']} for d in dx_data], ensure_ascii=False) + ';'
    
    # POI data
    major_js = 'var majorSpots = ' + json.dumps(major_spots, ensure_ascii=False) + ';'
    minor_js = 'var spots = ' + json.dumps(minor_spots, ensure_ascii=False) + ';'
    
    route_js_block = '\n'.join(route_js_parts) + '\n' + main_routes_js + '\n' + spur_routes_js + '\n' + cities_js + '\n' + dx_data_js + '\n' + major_js + '\n' + minor_js
    
    # ── 加载模板 ──
    leaflet_css, leaflet_js = load_leaflet()
    html_template = load_template('map.html')
    map_css = load_template('map.css').replace('{{STOP_CSS}}', stop_css)
    map_js = load_template('map.js')
    
    # ── 替换占位符 ──
    map_js = map_js.replace('{{CENTER_LAT}}', str(center['lat']))
    map_js = map_js.replace('{{CENTER_LNG}}', str(center['lng']))
    map_js = map_js.replace('{{TILE_URL}}', tile_url)
    map_js = map_js.replace('{{FOCUS_JSON}}', json.dumps(focus, ensure_ascii=False))
    
    html = html_template
    html = html.replace('{{TITLE}}', title)
    html = html.replace('{{SUBTITLE}}', subtitle)
    html = html.replace('{{LEAFLET_CSS}}', leaflet_css)
    html = html.replace('{{MAP_CSS}}', map_css)
    html = html.replace('{{LEAFLET_JS}}', leaflet_js)
    html = html.replace('{{STATS_HTML}}', stats_html)
    html = html.replace('{{LEGEND_HTML}}', legend_html)
    html = html.replace('{{WARNINGS_HTML}}', warnings_html)
    html = html.replace('{{FOOTER_HTML}}', footer_html)
    html = html.replace('{{SIDEBAR_HTML}}', '\n'.join(sidebar_items))
    html = html.replace('{{CARDS_HTML}}', '\n'.join(day_card_items))
    html = html.replace('{{ROUTE_JS}}', route_js_block)
    html = html.replace('{{MAP_JS}}', map_js)
    
    # ── 写入 ──
    if output_path:
        out_file = output_path
    else:
        base = os.path.splitext(os.path.basename(resolved_path))[0]
        out_file = os.path.join(OUTPUT_DIR, f"{base}.html")
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 生成成功: {out_file}")
    print(f"   大小: {os.path.getsize(out_file):,} 字节")
    print(f"\n🌐 预览: http://localhost:9120/{os.path.basename(out_file)}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 render.py resolved/xxx.json [--output output/xxx.html]")
        sys.exit(1)
    
    resolved_path = sys.argv[1]
    output_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]
    
    if not os.path.exists(resolved_path):
        print(f"❌ 文件不存在: {resolved_path}")
        sys.exit(1)
    
    render(resolved_path, output_path)


if __name__ == '__main__':
    main()
