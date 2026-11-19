from pathlib import Path
import json
import tempfile
import unittest

from PIL import Image, ImageDraw

from make_cell_items import build, draw_cell, verify


class MakeCellItemsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        theatre = self.out/'theatre-9'
        theatre.mkdir()
        image = Image.new('RGB', (400, 300), 'white')
        draw = ImageDraw.Draw(image)
        self.cells = [{'candidate_id': f'shape-{i:04}', 'bbox_px': [40 + 60 * i, 120, 80 + 60 * i, 160]} for i in range(3)]
        for cell in self.cells:
            draw.rectangle(cell['bbox_px'], fill='#b0b0b0')
        image.save(theatre/'rgb.png')
        (theatre/'seats.json').write_text(json.dumps({'seats': self.cells}), encoding='utf-8')
        # One cell is an existing review sample, drawn the same way as run_experiment.py does.
        (self.out/'review-contexts').mkdir()
        (self.out/'review-crops').mkdir()
        sid = 'theatre-9--shape-0001'
        with Image.open(theatre/'rgb.png') as source:
            draw_cell(source.convert('RGB'), self.cells[1]['bbox_px'],
                      self.out/f'review-contexts/{sid}.png', self.out/f'review-crops/{sid}.png')
        review = {'samples': [{'sample_id': sid, 'unit': 'px', 'crop': f'review-crops/{sid}.png'}]}
        (self.out/'review-template.json').write_text(json.dumps(review), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_reuses_review_samples_and_draws_the_rest_once(self):
        items, drawn = build(self.out, ['theatre-9'])
        self.assertEqual([it['sample_id'] for it in items],
                         [f'theatre-9--shape-{i:04}' for i in range(3)])
        self.assertEqual(items[1]['context'], 'review-contexts/theatre-9--shape-0001.png')
        self.assertEqual(items[0]['crop'], 'cell-crops/theatre-9--shape-0000.png')
        self.assertEqual(drawn, 2)
        for it in items:
            self.assertTrue((self.out/it['context']).exists() and (self.out/it['crop']).exists())
        self.assertEqual(build(self.out, ['theatre-9'])[1], 0)

    def test_verify_detects_changed_review_images(self):
        items, _ = build(self.out, ['theatre-9'])
        self.assertEqual(verify(self.out, items), (1, []))
        crop = self.out/'review-crops/theatre-9--shape-0001.png'
        with Image.open(crop) as image:
            changed = image.copy()
        changed.putpixel((0, 0), (1, 2, 3))
        changed.save(crop)
        self.assertEqual(verify(self.out, items), (1, ['review-crops/theatre-9--shape-0001.png']))


if __name__ == '__main__':
    unittest.main()
