import unittest

from compare_readings import compare, matches, ocr_reading


def sample(sample_id, **prediction):
    return {'sample_id': sample_id, 'unit': 'px', 'stratum': 'band-0-main',
            'prediction': {'kind': 'regular_seat_shape_candidate', **prediction}}


class CompareReadingsTest(unittest.TestCase):
    def test_seat_needs_zone_row_and_number(self):
        truth = {'is_seat': 'yes', 'zone': 'main', 'row': 'a', 'number': '6'}
        self.assertTrue(matches({'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '6'}, truth))
        self.assertFalse(matches({'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '9'}, truth))
        self.assertFalse(matches({'is_seat': 'yes', 'zone': 'BOX-1', 'row': 'A', 'number': '6'}, truth))

    def test_non_seat_region_scores_only_the_non_seat_call(self):
        truth = {'is_seat': 'no', 'zone': 'main', 'row': 'L', 'number': '12, 13'}
        blue = ocr_reading({'kind': 'accessibility_or_blue_region', 'seat_id': None})
        self.assertTrue(matches(blue, truth))

    def test_unresolved_ocr_is_not_correct(self):
        self.assertIsNone(ocr_reading({'kind': 'regular_seat_shape_candidate', 'seat_id': None}))

    def test_only_blind_items_are_scored_and_disagreements_are_queued(self):
        review = {'samples': [
            sample('s1', seat_id='main:A-6', block='main', row='A', number=6),
            sample('s2', seat_id='main:B-1', block='main', row='B', number=1),
            sample('s3', seat_id='main:C-2', block='main', row='C', number=2),
        ]}
        blind = {'samples': [{'sample_id': 's1', 'label': {'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '9'}}]}
        model = {
            's1': {'sample_id': 's1', 'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '9'},
            's2': {'sample_id': 's2', 'is_seat': 'yes', 'zone': 'main', 'row': 'B', 'number': '7'},
            's3': {'sample_id': 's3', 'is_seat': 'yes', 'zone': 'main', 'row': 'C', 'number': '2'},
        }
        result = compare(review, blind, model, spot_checks=5, seed=1)
        self.assertEqual(result['summary']['scored_items'], 1)
        self.assertEqual(result['summary']['ocr_correct'], 0)
        self.assertEqual(result['summary']['model_correct'], 1)
        self.assertEqual([x['sample_id'] for x in result['review_queue']], ['s2'])
        self.assertEqual([x['sample_id'] for x in result['spot_checks']], ['s3'])


if __name__ == '__main__':
    unittest.main()
