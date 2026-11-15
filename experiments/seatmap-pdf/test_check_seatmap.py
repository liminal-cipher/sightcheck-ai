import unittest

from check_seatmap import check, longest_run, measure, norm

CELL = 36


def grid(rows, numbers, step=1, x0=100, y0=100):
    """Seat shapes for rows of touching cells; returns (seats, readings)."""
    seats, readings = [], {}
    for r, row in enumerate(rows):
        for i, n in enumerate(numbers):
            cid = f'{row}{n}'
            seats.append({'candidate_id': cid, 'center_px': [x0 + i * (CELL + 3), y0 + r * 46]})
            readings[cid] = norm({'zone': 'main', 'row': row, 'number': str(n * step)})
    return seats, readings


class CheckSeatmapTest(unittest.TestCase):
    def test_clean_rows_raise_no_flags(self):
        seats, readings = grid('ABC', range(1, 9))
        result = check(seats, readings, CELL, {'total': 24})
        self.assertEqual(result['flags'], {})
        self.assertEqual(result['summary']['count_mismatches'], [])

    def test_lookalike_digit_breaks_order_and_adjacency(self):
        seats, readings = grid('AB', range(1, 9))
        readings['A6'] = {**readings['A6'], 'number': '9'}
        flags = check(seats, readings, CELL)['flags']
        self.assertIn('out_of_order', flags['A6'])
        self.assertIn('adjacent_jump', flags['A6'])

    def test_neighbor_number_is_a_duplicate(self):
        seats, readings = grid('A', range(1, 9))
        readings['A4'] = {**readings['A4'], 'number': '5'}
        flags = check(seats, readings, CELL)['flags']
        self.assertIn('duplicate_id', flags['A4'])
        self.assertIn('duplicate_id', flags['A5'])

    def test_wrong_row_letter_is_off_the_line(self):
        seats, readings = grid('ABC', range(1, 9))
        readings['B3'] = {**readings['B3'], 'row': 'C'}
        flags = check(seats, readings, CELL)['flags']
        self.assertIn('row_misaligned', flags['B3'])

    def test_row_letters_must_run_down_the_page(self):
        seats, readings = grid('ABC', range(1, 5))
        for n in range(1, 5):
            readings[f'B{n}'] = {**readings[f'B{n}'], 'row': 'D'}
        flags = check(seats, readings, CELL)['flags']
        self.assertIn('row_letter_order', flags['B1'])
        self.assertNotIn('A1', flags)

    def test_odd_even_rows_use_their_own_step(self):
        seats, readings = grid('A', range(1, 9), step=2)
        self.assertEqual(check(seats, readings, CELL)['flags'], {})

    def test_unread_non_seat_and_count_mismatch(self):
        seats, readings = grid('A', range(1, 5))
        del readings['A2']
        readings['A3'] = norm({'is_seat': 'no', 'zone': 'other', 'number': ''})
        result = check(seats, readings, CELL, {'total': 4})
        self.assertEqual(result['flags']['A2'], ['unread'])
        self.assertEqual(result['flags']['A3'], ['not_a_seat'])
        self.assertEqual(result['summary']['count_mismatches'], [{'key': 'total', 'expected': 4, 'actual': 2}])

    def test_second_reader_disagreement_is_flagged(self):
        seats, readings = grid('A', range(1, 5))
        other = {'A1': dict(readings['A1']), 'A2': {**readings['A2'], 'number': '7'},
                 'A3': norm({'is_seat': 'no', 'zone': 'other'})}
        flags = check(seats, readings, CELL, compare=other)['flags']
        self.assertNotIn('A1', flags)
        self.assertEqual(flags['A2'], ['reader_disagreement'])
        self.assertEqual(flags['A3'], ['reader_disagreement'])

    def test_longest_run_and_seeded_measurement(self):
        self.assertEqual(longest_run([1, 2, 9, 4, 5]), {0, 1, 3, 4})
        seats, readings = grid('ABCD', range(1, 13))
        first = measure(seats, readings, CELL, 40, 3)
        self.assertEqual(first, measure(seats, readings, CELL, 40, 3))
        self.assertEqual(first['planted'], 40)
        self.assertGreaterEqual(first['caught'], 36)


if __name__ == '__main__':
    unittest.main()
