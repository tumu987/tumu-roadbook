import unittest
from pathlib import Path

import yaml

import resolve as route_resolve
from version import __version__
from resolve import (
    _haversine_km,
    _straight_line,
    daily_ceiling,
    day_theme_html,
    map_distance_label,
    validate_trip_data,
    verify_pois_with_osm,
)


class RouteValidationTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, '0.1.8')

    def test_repository_trips_pass_schema_validation(self):
        for path in sorted(Path('trips').glob('*.yaml')):
            with self.subTest(path=path.name):
                data = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertEqual(validate_trip_data(data), [])

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
        self.assertGreater(result['distance_km'], direct)
        self.assertGreaterEqual(result['distance_km'], round(_haversine_km(start, via) + _haversine_km(via, end)) - 1)

    def test_map_label_keeps_distance_without_estimated_time(self):
        self.assertEqual(map_distance_label('587km · 9h8', 587), '587km')
        self.assertEqual(map_distance_label('', 122), '122km')
        self.assertEqual(map_distance_label('', 0), '')

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


if __name__ == '__main__':
    unittest.main()
