import unittest

from make_blind_review import category, select_samples


def sample(sample_id, stratum):
    return {'sample_id': sample_id, 'document': 'd', 'source_sha256': 'x', 'unit': 'px',
            'stratum': stratum, 'crop': f'review-crops/{sample_id}.png'}


class BlindReviewTest(unittest.TestCase):
    def setUp(self):
        self.review = {'samples': [sample(f'm{i}', f'band-{i}-main') for i in range(6)]
                       + [sample(f'b{i}', f'band-{i}-BOX-1') for i in range(3)]
                       + [sample('r0', 'blue-region-000'), {**sample('pdf', 'band-0-main'), 'unit': 'pt'}]}

    def test_category_strips_band_prefix(self):
        self.assertEqual(category('band-12-number_ocr_uncertain'), 'number_ocr_uncertain')
        self.assertEqual(category('band-3-BOX-2'), 'BOX-2')
        self.assertEqual(category('blue-region-004'), 'blue-region')

    def test_exclude_skips_labelled_ids(self):
        picked = select_samples(self.review, 9, 1, exclude={'m0'})
        self.assertNotIn('m0', [s['sample_id'] for s in picked])
        self.assertNotIn('pdf', [s['sample_id'] for s in picked])

    def test_quotas_are_seeded_and_exact(self):
        quotas = {'BOX-1': 2, 'main': 3, 'blue-region': 1}
        picked = [s['sample_id'] for s in select_samples(self.review, 0, 5, {'b0'}, quotas)]
        self.assertEqual(picked, [s['sample_id'] for s in select_samples(self.review, 0, 5, {'b0'}, quotas)])
        self.assertEqual(sorted(x[0] for x in picked), ['b', 'b', 'm', 'm', 'm', 'r'])
        self.assertNotIn('b0', picked)
        with self.assertRaises(ValueError):
            select_samples(self.review, 0, 5, {'b0'}, {'BOX-1': 3})


if __name__ == '__main__':
    unittest.main()
