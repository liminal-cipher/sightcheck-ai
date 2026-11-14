import unittest

from make_preread_manifests import load_template, render, split


class PrereadManifestTest(unittest.TestCase):
    def test_split_is_seeded_and_covers_each_jpeg_sample_once(self):
        review = {'samples': [{'sample_id': f's{i:02d}', 'unit': 'px'} for i in range(23)]
                  + [{'sample_id': 'pdf', 'unit': 'pt'}]}
        parts = split(review, 10, 7)
        flat = [x for part in parts for x in part]
        self.assertEqual(sorted(flat), [f's{i:02d}' for i in range(23)])
        self.assertEqual(parts, split(review, 10, 7))

    def test_template_fills_both_paths(self):
        text = render(load_template(), 'M.json', 'R.json')
        self.assertIn('Open ONLY this manifest: M.json', text)
        self.assertIn('R.json', text)
        self.assertNotIn('{manifest_path}', text)
        self.assertNotIn('{result_path}', text)


if __name__ == '__main__':
    unittest.main()
