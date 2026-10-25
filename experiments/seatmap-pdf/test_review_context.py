"""PDF context coverage and review persistence contracts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz
from PIL import Image, ImageDraw
from run_experiment import pdf_context_bounds, write_pdf_contexts, write_jpeg_contexts, write_review_ui, seat_cell_bounds, draw_cell_corners
from run_experiment import write_seat_crop, refresh_seat_crops, SEAT_HIGHLIGHT_PADDING


class ContextTests(unittest.TestCase):
    def test_enlargement_padding_preserves_bbox_pixels_in_both_units(self):
        with tempfile.TemporaryDirectory() as directory:
            for unit, scale in [('pt',2), ('px',1)]:
                with self.subTest(unit=unit):
                    source = Image.new('RGB',(160,160),'white')
                    box = [30,30,50,50]
                    pixel_box = tuple(int(v*scale) for v in box)
                    ImageDraw.Draw(source).rectangle(pixel_box, fill='gray')
                    bounds = [10,10,140,140]
                    dest = Path(directory)/f'{unit}.png'
                    write_seat_crop(source,box,scale,bounds,unit,dest)
                    with Image.open(dest) as result:
                        local = tuple(v-10 for v in pixel_box)
                        self.assertEqual(result.crop(local).tobytes(),source.crop(pixel_box).tobytes())
                        self.assertEqual(result.size,(130,130))
                        margin = SEAT_HIGHLIGHT_PADDING[unit]*scale
                        self.assertEqual(result.getpixel((int(local[0]-margin),int(local[1]))),(255,51,0))
                        self.assertEqual(result.getpixel((local[0]-1,local[1]+5)),(255,255,255))

    def test_crop_refresh_preserves_review_and_saved_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output/'theatre-2').mkdir()
            Image.new('RGB',(200,200),'white').save(output/'theatre-2/rgb.png')
            Image.new('RGB',(80,70),'white').save(output/'crop.png')
            review = {'samples':[{'document':'theatre-2','unit':'px','crop':'crop.png',
                       'crop_origin':[12,18],'render_scale':1,'prediction':{'bbox':[30,40,50,60]},
                       'review':{'status':'reviewed','expected_center':[42,49]}}]}
            before = copy.deepcopy(review)
            refresh_seat_crops(output,review)
            self.assertEqual(review,before)
            with Image.open(output/'crop.png') as result:
                self.assertEqual(result.size,(80,70))
                self.assertEqual(result.getpixel((30-3-12,40-18)),(255,51,0))

    def test_jpeg_full_plan_preserves_labels_numbers_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            source = output/'theatre-2'
            source.mkdir()
            original = Image.new('RGB', (240,320), (250,235,190))
            draw = ImageDraw.Draw(original)
            draw.text((5,5), 'Floor 2 / BOX-1', fill='black')
            draw.rectangle([80,100,120,140], fill='gray')
            draw.text((90,110), '12', fill='white')
            draw.text((3,300), 'A / Floor 1', fill='black')
            original.save(source/'rgb.png')
            review = {'samples':[{'sample_id':'theatre-2--seat', 'document':'theatre-2',
                       'unit':'px','prediction':{'bbox':[80,100,120,140]},
                       'review':{'status':'reviewed','notes':'Keep this'}}]}
            before = copy.deepcopy(review)
            contexts = write_jpeg_contexts(output, review)
            self.assertEqual(review, before)
            with Image.open(output/contexts['theatre-2--seat']['image']) as image:
                self.assertEqual(image.size, original.size)
                self.assertEqual(image.crop((80,100,121,141)).tobytes(), original.crop((80,100,121,141)).tobytes())
                changes = 0
                for y in range(image.height):
                    for x in range(image.width):
                        a, b = original.getpixel((x,y)), image.getpixel((x,y))
                        if a != b:
                            changes += 1
                            self.assertEqual(a, (250,235,190))
                            self.assertEqual(b, (255,51,0))
                self.assertGreater(changes, 0)

    def test_cell_uses_grid_not_text_extent(self):
        rules = [fitz.Rect(10,10,50,10), fitz.Rect(10,50,50,50),
                 fitz.Rect(10,10,10,50), fitz.Rect(50,10,50,50)]
        for box in ([20,25,40,30], [25,20,30,40]):
            self.assertEqual(seat_cell_bounds({'bbox':box}, rules), [10,10,50,50])
        self.assertIsNone(seat_cell_bounds({'bbox':[20,25,40,30]}, rules[:2]))

    def test_corners_preserve_cell_interior_and_source_ink(self):
        image = Image.new('RGB', (80,80), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle([20,20,60,60], outline='black', width=2)
        draw.text((30,30), '1-8', fill='black')
        draw.line([0,17,79,17], fill='#0072b2', width=2)
        original = image.copy()
        draw_cell_corners(image, [20,20,60,60])
        self.assertEqual(image.crop((20,20,61,61)).tobytes(), original.crop((20,20,61,61)).tobytes())
        changed = 0
        for y in range(image.height):
            for x in range(image.width):
                before, after = original.getpixel((x,y)), image.getpixel((x,y))
                if before != after:
                    changed += 1
                    self.assertEqual(before, (255,255,255))
                    self.assertEqual(after, (255,51,0))
        self.assertGreater(changed, 0)

    def test_all_label_directions_and_seat_are_inside(self):
        for label in ([5, 25, 15, 180], [175, 25, 190, 180],
                      [30, 185, 160, 198], [30, 2, 160, 15]):
            with self.subTest(label=label):
                region = {'block':'A', 'bbox_pt':[20, 20, 170, 180], 'label_bbox_pt':label}
                candidate = {'block':'A', 'bbox':[25, 30, 40, 40]}
                bounds, matches = pdf_context_bounds(candidate, [region], [200, 200])
                self.assertEqual(matches, [region])
                for box in [label, region['bbox_pt'], candidate['bbox']]:
                    self.assertLessEqual(bounds[0], box[0])
                    self.assertLessEqual(bounds[1], box[1])
                    self.assertGreaterEqual(bounds[2], box[2])
                    self.assertGreaterEqual(bounds[3], box[3])
                self.assertTrue(0 <= bounds[0] < bounds[2] <= 200)
                self.assertTrue(0 <= bounds[1] < bounds[3] <= 200)

    def test_seat_outside_prediction_still_visible(self):
        region = {'block':'A', 'bbox_pt':[20, 20, 50, 50], 'label_bbox_pt':[20, 10, 50, 15]}
        bounds, _ = pdf_context_bounds({'block':'A','bbox':[150, 150, 160, 160]}, [region], [200,200])
        self.assertGreater(bounds[2], 160)
        self.assertGreater(bounds[3], 160)

    def test_unmatched_uses_full_page_without_inventing_region(self):
        self.assertEqual(pdf_context_bounds({'bbox':[1,2,3,4]}, [], [200,300]), ([0,0,200,300], []))

    def test_context_is_display_only_and_jpeg_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            source = output/'theatre-1'/'plan'
            source.mkdir(parents=True)
            inputs = output/'input/theatre-1'
            inputs.mkdir(parents=True)
            with fitz.open() as pdf:
                page = pdf.new_page(width=100,height=100)
                page.draw_rect([25,25,40,40])
                pdf.save(inputs/'plan.pdf')
            region = {'block':'A', 'bbox_pt':[20,20,80,80], 'label_bbox_pt':[20,82,80,95]}
            (source/'seats.json').write_text(json.dumps({'page_size_pt':[100,100], 'block_regions':[region]}))
            Image.new('RGB', (200,200), 'white').save(source/'page.png')
            review = {'schema_version':1, 'samples':[
                {'sample_id':'plan--A', 'document':'plan', 'unit':'pt',
                 'prediction':{'block':'A', 'bbox':[30,30,35,35]}, 'review':{'status':'reviewed'}},
                {'sample_id':'jpeg--1', 'document':'jpeg', 'unit':'px'}]}
            original = copy.deepcopy(review)
            with patch('run_experiment.BASE', output):
                contexts = write_pdf_contexts(output, review)
            write_review_ui(output, review, contexts)
            self.assertEqual(review, original)
            self.assertEqual(list(contexts), ['plan--A'])
            with Image.open(output/contexts['plan--A']['image']) as image:
                colours = {colour for _, colour in image.getcolors(image.width*image.height)}
                self.assertIn((0,114,178), colours)
                self.assertIn((255,51,0), colours)
            self.assertIn('미검증 예측', (output/'review.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
