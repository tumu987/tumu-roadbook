import unittest
from pathlib import Path

import yaml

import resolve as route_resolve
from version import __version__
import build_index
from resolve import (
    _haversine_km,
    _straight_line,
    analyze_route_elevation,
    calculate_poi_zoom,
    daily_ceiling,
    day_theme_html,
    map_distance_label,
    assess_day_load,
    parse_timeline_minutes,
    sample_route_points,
    validate_trip_data,
    validate_trip_schema,
    verify_pois_with_osm,
)


class RouteValidationTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, '0.2.0')

    def test_repository_trips_pass_schema_validation(self):
        for path in sorted(Path('trips').glob('*.yaml')):
            with self.subTest(path=path.name):
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertEqual(validate_trip_schema(data), [])
                self.assertEqual(validate_trip_data(data), [])
                self.assertEqual(data['trip'].get('coordinate_verification'), 'strict')

    def test_missing_route_is_rejected(self):
        data = {
            'trip': {'title': 'bad', 'drivers': 1},
            'days': [{'day': 1}],
        }
        errors = validate_trip_data(data)
        self.assertTrue(any('route 缺失' in error for error in errors))

    def test_invalid_driver_count_is_rejected(self):
        data = {
            'trip': {'title': 'bad', 'drivers': 0},
            'days': [{'day': 1, 'route': {'start': 'A', 'end': 'B'}}],
        }
        errors = validate_trip_data(data)
        self.assertTrue(any('trip.drivers' in error for error in errors))

    def test_json_schema_rejects_invalid_structure(self):
        data = {
            'trip': {'title': 'bad', 'drivers': 0, 'typo_field': True},
            'days': [{
                'day': 1,
                'label': 'D1',
                'theme': 'A → B',
                'route': {'start': [91, 113], 'end': 'B'},
            }],
        }
        errors = validate_trip_schema(data)
        self.assertTrue(any('$.trip.drivers' in error for error in errors))
        self.assertTrue(any('typo_field' in error for error in errors))
        self.assertTrue(any('$.days[0].route.start' in error for error in errors))

    def test_strict_coordinate_mode_requires_osm_provenance(self):
        data = {
            'trip': {'title': 'strict', 'drivers': 1, 'coordinate_verification': 'strict'},
            'days': [{'day': 1, 'route': {'start': 'A', 'end': 'B'}}],
            'pois': [{'name': '示例景点', 'coord': [36.2, 113.1], 'rank': 'major'}],
        }
        errors = validate_trip_data(data)
        self.assertTrue(any('coord_source: osm' in error for error in errors))
        self.assertTrue(any('osm_id' in error for error in errors))

    def test_timeline_node_requires_time_or_duration(self):
        data = {
            'trip': {'title': 'timeline', 'drivers': 1, 'timeline_mode': 'merged'},
            'days': [{
                'day': 1,
                'route': {'start': 'A', 'end': 'B'},
                'timeline': [{'action': '缺少时间信息'}],
            }],
        }
        errors = validate_trip_data(data)
        self.assertTrue(any('必须提供 time 或 duration' in error for error in errors))


class DistanceRuleTests(unittest.TestCase):
    def test_single_and_dual_driver_ceilings(self):
        self.assertEqual(daily_ceiling('highway', 1)[0], 400)
        self.assertEqual(daily_ceiling('mountain', 1)[0], 150)
        self.assertEqual(daily_ceiling('highway', 2)[0], 700)
        self.assertEqual(daily_ceiling('mountain', 2)[0], 300)

    def test_straight_line_fallback_counts_via_distance(self):
        start = [39.9042, 116.4074]
        via = [38.0428, 114.5149]
        end = [36.2000, 113.4390]
        result = _straight_line(start, end, [via])
        direct = round(_haversine_km(start, end))
        self.assertEqual(result['quality'], 'estimated')
        self.assertGreater(result['distance_km'], direct)
        self.assertGreaterEqual(result['distance_km'], round(_haversine_km(start, via) + _haversine_km(via, end)) - 1)

    def test_map_label_keeps_distance_without_estimated_time(self):
        self.assertEqual(map_distance_label('587km · 9h8', 587), '587km')
        self.assertEqual(map_distance_label('', 122), '122km')
        self.assertEqual(map_distance_label('', 0), '')

    def test_poi_zoom_adapts_to_trip_extent(self):
        zhuozhang = yaml.safe_load(Path('trips/zhuozhang-4d.yaml').read_text(encoding='utf-8'))
        north = yaml.safe_load(Path('trips/north-xinjiang-14d.yaml').read_text(encoding='utf-8'))
        self.assertEqual(calculate_poi_zoom(zhuozhang['pois']), {'major': 10, 'minor': 11})
        self.assertEqual(calculate_poi_zoom(north['pois']), {'major': 8, 'minor': 9})

    def test_timeline_duration_parsing(self):
        self.assertEqual(parse_timeline_minutes({'duration': '3小时'}), 180)
        self.assertEqual(parse_timeline_minutes({'duration': '1小时30分钟'}), 90)
        self.assertEqual(parse_timeline_minutes({'time': '08:30-09:40'}), 70)

    def test_day_load_status(self):
        easy = assess_day_load(50, 30, [{'duration': '2小时'}], 2)
        normal = assess_day_load(200, 120, [{'duration': '7小时30分钟'}], 2)
        tight = assess_day_load(470, 360, [{'duration': '9小时'}], 2)
        avoid = assess_day_load(750, 600, [{'duration': '8小时'}], 2)
        mountain_avoid = assess_day_load(480, 400, [{'duration': '8小时'}], 2, 'mountain')
        self.assertEqual(easy['status'], '轻松')
        self.assertEqual(normal['status'], '正常')
        self.assertEqual(tight['status'], '偏紧')
        self.assertEqual(avoid['status'], '不建议')
        self.assertEqual(mountain_avoid['status'], '不建议')

    def test_route_elevation_detects_peak_from_cache(self):
        original_cache = route_resolve._elev_cache
        route_resolve._elev_cache = {
            '36.2,113.4': 1200,
            '36.3,113.5': 4300,
            '36.4,113.6': 1800,
        }
        try:
            result = analyze_route_elevation([
                [36.2, 113.4],
                [36.3, 113.5],
                [36.4, 113.6],
            ])
        finally:
            route_resolve._elev_cache = original_cache
        self.assertEqual(result['elevation'], 4300)

    def test_route_sampling_is_bounded(self):
        points = [[index / 100, index / 100] for index in range(100)]
        sampled = sample_route_points(points, max_points=10)
        self.assertEqual(len(sampled), 10)
        self.assertEqual(sampled[0], points[0])
        self.assertEqual(sampled[-1], points[-1])


class IndexBuildTests(unittest.TestCase):
    def test_index_is_generated_from_trip_metadata(self):
        trips = build_index.load_trips()
        rendered = build_index.render_index(trips)
        self.assertEqual(len(trips), 4)
        self.assertEqual(trips[0]['page'], 'zhuozhang-4d.html')
        self.assertIn('href="north-xinjiang-14d.html"', rendered)
        self.assertIn(f'Tumu Roadbook v{__version__}', rendered)
        self.assertNotIn('{{TRIP_CARDS}}', rendered)

    def test_day_theme_separates_route_and_focus(self):
        html = day_theme_html('平顺 → 长治 · 明代悬塑')
        self.assertIn('<span class="day-route-path">平顺 → 长治</span>', html)
        self.assertIn('<span class="day-route-focus">明代悬塑</span>', html)


class DataAccuracyTests(unittest.TestCase):
    def test_zhuozhang_major_pois_have_osm_provenance(self):
        data = yaml.safe_load(Path('trips/zhuozhang-4d.yaml').read_text(encoding='utf-8'))
        self.assertEqual(data['trip'].get('coordinate_verification'), 'strict')
        expected = {
            '天台庵': ('node/5256332104', 36.383242, 113.398436),
            '原起寺': ('node/5256251859', 36.353334, 113.425748),
            '淳化寺': ('way/1449573449', 36.353256, 113.586226),
            '龙门寺': ('way/1252171732', 36.390227, 113.623042),
            '大云院': ('way/543740693', 36.367072, 113.438718),
            '长治观音堂': ('way/1157444902', 36.227635, 113.076745),
            '上党门': ('way/1171947665', 36.187171, 113.100345),
        }
        for poi in data['pois']:
            if poi['name'] not in expected:
                continue
            osm_id, lat, lng = expected[poi['name']]
            self.assertEqual(poi.get('coord_source'), 'osm')
            self.assertEqual(poi.get('osm_id'), osm_id)
            self.assertAlmostEqual(poi['lat'], lat, places=6)
            self.assertAlmostEqual(poi['lng'], lng, places=6)

    def test_osm_mismatch_over_tolerance_fails(self):
        original_cache = route_resolve._poi_verify_cache
        route_resolve._poi_verify_cache = {
            'way/123': {'lat': 36.227635, 'lng': 113.076745},
        }
        try:
            errors = verify_pois_with_osm([{
                'name': '错误示例',
                'rank': 'major',
                'lat': 36.195,
                'lng': 113.115,
                'osm_id': 'way/123',
            }])
        finally:
            route_resolve._poi_verify_cache = original_cache
        self.assertTrue(any('超过 0.75km 阈值' in error for error in errors))

    def test_zhuozhang_uses_single_merged_timeline(self):
        data = yaml.safe_load(Path('trips/zhuozhang-4d.yaml').read_text(encoding='utf-8'))
        self.assertEqual(data['trip'].get('timeline_mode'), 'merged')
        for day in data['days']:
            with self.subTest(day=day['day']):
                self.assertNotIn('items', day)
                self.assertTrue(day.get('timeline'))
                for item in day['timeline']:
                    self.assertTrue(item.get('time') or item.get('duration'))

    def test_new_north_xinjiang_route_is_complete(self):
        path = Path('trips/north-xinjiang-14d.yaml')
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        self.assertEqual(data['trip'].get('coordinate_verification'), 'strict')
        self.assertEqual(data['trip'].get('timeline_mode'), 'merged')
        self.assertEqual(len(data['days']), 14)
        self.assertEqual(len({day['day'] for day in data['days']}), 14)
        self.assertFalse(Path('trips/北疆.yaml').exists())

    def test_new_southeast_shanxi_route_is_complete(self):
        data = yaml.safe_load(
            Path('trips/southeast-shanxi-7d.yaml').read_text(encoding='utf-8')
        )
        self.assertEqual(data['trip'].get('coordinate_verification'), 'strict')
        self.assertEqual(data['trip'].get('timeline_mode'), 'merged')
        self.assertEqual(len(data['days']), 7)
        self.assertEqual(sum(poi['rank'] == 'major' for poi in data['pois']), 14)
        self.assertTrue(all(
            poi.get('osm_id') and poi.get('coord_source') == 'osm'
            for poi in data['pois'] if poi['rank'] == 'major'
        ))
        self.assertFalse(Path('trips/jindongnan.yaml').exists())


class TemplateSmokeTests(unittest.TestCase):
    def test_standard_tile_is_only_registered_once(self):
        map_js = Path('templates/map.js').read_text(encoding='utf-8')
        self.assertEqual(map_js.count("L.tileLayer('{{TILE_URL}}'"), 1)

    def test_controls_do_not_use_inline_click_handlers(self):
        map_html = Path('templates/map.html').read_text(encoding='utf-8')
        map_js = Path('templates/map.js').read_text(encoding='utf-8')
        self.assertNotIn('onclick=', map_html)
        self.assertNotIn('onclick=', map_js)

    def test_poi_dots_are_pinned_to_coordinates(self):
        map_js = Path('templates/map.js').read_text(encoding='utf-8')
        self.assertIn("L.circleMarker([s[0], s[1]]", map_js)
        self.assertIn('dot.bindTooltip', map_js)
        self.assertNotIn('iconAnchor: [s[4]+20', map_js)

    def test_warnings_are_rendered_inside_day_cards(self):
        map_html = Path('templates/map.html').read_text(encoding='utf-8')
        resolve_source = Path('resolve.py').read_text(encoding='utf-8')
        self.assertNotIn('{{WARNINGS_HTML}}', map_html)
        self.assertIn('day-alert-list', resolve_source)
        self.assertIn('tl-alert-row', resolve_source)


if __name__ == '__main__':
    unittest.main()
