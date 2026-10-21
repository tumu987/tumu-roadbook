#!/usr/bin/env python3
"""Build the route index from active trip YAML files."""

from __future__ import annotations

import html
import sys
from pathlib import Path

import yaml

from version import __version__

BASE_DIR = Path(__file__).resolve().parent
TRIPS_DIR = BASE_DIR / 'trips'
TEMPLATE_PATH = BASE_DIR / 'templates' / 'index.html'
DEFAULT_OUTPUT = BASE_DIR / 'docs' / 'index.html'


def load_trips() -> list[dict]:
    trips = []
    for path in sorted(TRIPS_DIR.glob('*.yaml')):
        data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        trip = data.get('trip', {})
        index = trip.get('index', {}) or {}
        stats = trip.get('stats', {}) or {}
        colors = trip.get('colors', {}) or {}
        days = int(stats.get('days') or len(data.get('days', [])) or 0)
        trips.append({
            'path': path,
            'page': f'{path.stem}.html',
            'title': str(trip.get('title') or path.stem),
            'subtitle': str(trip.get('subtitle') or ''),
            'summary': str(index.get('summary') or trip.get('subtitle') or ''),
            'region': str(index.get('region') or trip.get('dates') or '自驾路线'),
            'color': str(index.get('color') or colors.get('D1') or '#c49a6c'),
            'order': int(index.get('order', 999)),
            'days': days,
            'distance': str(stats.get('distance') or '').lstrip('~'),
            'drivers': int(trip.get('drivers') or 1),
        })
    return sorted(trips, key=lambda item: (item['order'], item['title']))


def render_trip_card(trip: dict) -> str:
    distance = f"约 {html.escape(trip['distance'])} km" if trip['distance'] else ''
    driver_text = f"{trip['drivers']} 位主驾"
    footer = ' · '.join(part for part in (distance, driver_text) if part)
    return f'''      <a class="trip" href="{html.escape(trip['page'])}" style="--trip-color:{html.escape(trip['color'])}">
        <div class="meta"><span>{html.escape(trip['region'])}</span><span class="tag">{trip['days']}天</span></div>
        <h2>{html.escape(trip['title'])}</h2>
        <p>{html.escape(trip['summary'])}</p>
        <div class="foot"><span>{footer}</span><span class="open">打开路线 →</span></div>
      </a>'''


def render_index(trips: list[dict]) -> str:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    days = [trip['days'] for trip in trips if trip['days'] > 0]
    replacements = {
        '{{TOTAL_DAYS}}': str(sum(days)),
        '{{ROUTE_COUNT}}': str(len(trips)),
        '{{DAY_RANGE}}': f'{min(days)}–{max(days)}' if days else '0',
        '{{TRIP_CARDS}}': '\n\n'.join(render_trip_card(trip) for trip in trips),
        '{{VERSION}}': __version__,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def build(output_path: Path = DEFAULT_OUTPUT) -> Path:
    trips = load_trips()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_index(trips), encoding='utf-8')
    return output_path


def main() -> None:
    output_path = DEFAULT_OUTPUT
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])
    path = build(output_path)
    print(f'✅ 路线册索引: {path}')


if __name__ == '__main__':
    main()
