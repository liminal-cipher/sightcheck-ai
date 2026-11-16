from pathlib import Path
import json
import tempfile
import unittest

from check_seatmap import collect
from make_map_review import build_theatre, write_page


def seat(i, number, row='A', x0=100):
    x = x0 + i * 39
    return {'candidate_id': f'shape-{i:04}', 'bbox_px': [x, 100, x + 36, 136], 'center_px': [x + 18, 118],
            'block': 'main' if row else None, 'row': row, 'number': number,
            'seat_id': f'main:{row}-{number}' if row and number else None}


class MapReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        (self.out/'t').mkdir()
        seats = [seat(0, 1), seat(1, 2), seat(2, None, row=None), seat(3, 4)]
        region = {'candidate_id': 'blue-region-000', 'bbox_px': [300, 100, 370, 136]}
        (self.out/'t'/'seats.json').write_text(json.dumps({
            'size_px': [600, 300], 'parameters': {'modal_cell_size_px': 36},
            'seats': seats, 'accessibility_regions': [region]}), encoding='utf-8')
        (self.out/'model').mkdir()
        readings = [{'sample_id': 't--shape-0001', 'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '7'},
                    {'sample_id': 't--shape-0002', 'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '3'}]
        (self.out/'model'/'result-01.json').write_text(json.dumps(readings), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_cells_carry_readings_flags_and_regions(self):
        theatre = build_theatre(self.out, 't', ['model', 'ocr'], 'ocr')
        cells = {c['id']: c for c in theatre['cells']}
        self.assertEqual(len(cells), 5)
        self.assertEqual(cells['t--blue-region-000']['kind'], 'region')
        wrong = cells['t--shape-0001']
        self.assertEqual(wrong['source'], 'model')
        self.assertEqual(wrong['ocr']['number'], '2')
        self.assertTrue(wrong['severe'])
        self.assertIn('reader_disagreement', wrong['flags'])
        self.assertEqual(cells['t--shape-0002']['source'], 'model')
        self.assertIsNone(cells['t--shape-0002']['ocr'])
        self.assertFalse(cells['t--shape-0000']['severe'])

    def test_reviewer_corrections_take_priority_when_rechecked(self):
        export = {'kind': 'map-review', 'samples': [
            {'sample_id': 't--shape-0001', 'label': {'status': 'reviewed', 'is_seat': 'yes', 'zone': 'main',
                                                     'row': 'A', 'number': '2'}},
            {'sample_id': 't--shape-0003', 'label': {'status': 'pending', 'is_seat': 'yes', 'number': '9'}}]}
        (self.out/'fix.json').write_text(json.dumps(export), encoding='utf-8')
        seats = json.loads((self.out/'t'/'seats.json').read_text(encoding='utf-8'))['seats']
        readings, origin = collect(self.out, 't', ['fix.json', 'model', 'ocr'], seats)
        self.assertEqual((readings['shape-0001']['number'], origin['shape-0001']), ('2', 'fix.json'))
        self.assertEqual(origin['shape-0003'], 'ocr')
        theatre = build_theatre(self.out, 't', ['fix.json', 'model', 'ocr'], 'ocr')
        self.assertFalse(any(c['severe'] for c in theatre['cells']))

    def test_page_embeds_data_without_raw_script_breaks(self):
        theatre = build_theatre(self.out, 't', ['ocr'])
        theatre['cells'][0]['flags'] = ['</script>']
        write_page(self.out, [theatre], ['ocr'], None, 'test')
        html = (self.out/'map-review.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('</script>'), 1)
        self.assertIn('"name": "t"', html)


if __name__ == '__main__':
    unittest.main()
