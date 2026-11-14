import unittest

from score_readers import queue_truth, score


class ScoreReadersTest(unittest.TestCase):
    def test_queue_verdicts_become_labels(self):
        model = {'is_seat': 'yes', 'zone': 'main', 'row': 'o', 'number': '22'}
        self.assertEqual(queue_truth({'model': model, 'review': {'verdict': 'model'}})['row'], 'O')
        self.assertIsNone(queue_truth({'model': model, 'review': {'verdict': 'unsure'}}))
        fixed = queue_truth({'model': model, 'review': {'verdict': 'neither', 'is_seat': 'yes', 'zone': 'main',
                                                         'row': 'P', 'number': '3'}})
        self.assertEqual(fixed, {'is_seat': 'yes', 'zone': 'main', 'row': 'P', 'number': '3'})

    def test_missing_reading_counts_as_wrong(self):
        truth = {'s1': {'is_seat': 'yes', 'zone': 'main', 'row': 'A', 'number': '6'}}
        result = score({}, truth)
        self.assertEqual((result['correct'], result['missing']), (0, 1))


if __name__ == '__main__':
    unittest.main()
