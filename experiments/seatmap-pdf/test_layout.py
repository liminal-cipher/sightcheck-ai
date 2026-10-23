"""Synthetic geometry tests; no private source fixtures required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
import test_extract_seats
from extract_layout import extract


class BaselineContractTests(test_extract_seats.SeatMapExtractionTests):
    def setUp(self):
        self.override = patch('test_extract_seats.extract',extract)
        self.override.start()
        self.addCleanup(self.override.stop)


def grid(page, x, y, label='A', side='top', tokens=('1-1','1-2','2-1'), scale=1):
    width,height = 90*scale,65*scale
    page.draw_rect(fitz.Rect(x,y,x+width,y+height),color=(0,0,0),width=.8)
    position,rotate = {
        'top':((x+width*.3,y-4*scale),0),
        'bottom':((x+width*.3,y+height+12*scale),0),
        'left':((x-4*scale,y+height*.7),90),
        'right':((x+width+10*scale,y+height*.25),270),
    }[side]
    page.insert_text(position,label+'\ube14\ub85d',fontname='korea',fontsize=8*scale,rotate=rotate)
    for i,text in enumerate(tokens):
        page.insert_text((x+8*scale+(i%2)*35*scale,y+20*scale+(i//2)*20*scale),text,fontsize=8*scale)


class GeometryTests(unittest.TestCase):
    def run_plan(self,build,count=3):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'unknown-name.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=600,height=700)
                build(page)
                page.insert_text((20,680),f'\ucd1d\uc88c\uc11d: {count}\uc11d',fontname='korea',fontsize=10)
                doc.save(path)
            return extract(path)

    def test_each_label_side_and_rotation(self):
        for side in ['top','bottom','left','right']:
            with self.subTest(side=side):
                r = self.run_plan(lambda p:grid(p,150,150,side=side))
                self.assertEqual(r['summary']['matched'],3)
                self.assertTrue(r['summary']['automatic_checks_passed'])

    def test_translation_and_scale_do_not_select_file_specific_coordinates(self):
        for scale in [.7,1.8]:
            r = self.run_plan(lambda p:grid(p,240,280,side='right',scale=scale))
            self.assertEqual(r['summary']['matched'],3)

    def test_side_and_rear_blocks_with_repeated_numbers(self):
        def build(p):
            grid(p,80,100,'K','right'); grid(p,260,100,'O','bottom')
        r = self.run_plan(build,6)
        self.assertEqual({s['seat_id'] for s in r['seats']},{f'{b}:{t}' for b in ['K','O'] for t in ['1-1','1-2','2-1']})

    def test_missing_seats_are_not_filled(self):
        r = self.run_plan(lambda p:grid(p,100,100,tokens=('1-1','1-3')),3)
        self.assertEqual(r['summary']['matched'],2)
        self.assertFalse(r['summary']['automatic_checks_passed'])

    def test_conflicting_labels_abstain(self):
        def build(p):
            grid(p,100,100)
            p.insert_text((127,177),'B\ube14\ub85d',fontname='korea',fontsize=8)
        r = self.run_plan(build)
        self.assertEqual(r['summary']['matched'],0)
        self.assertTrue(all(s['reason']=='block_ambiguous' for s in r['unmatched']))

    def test_duplicate_identity_abstains(self):
        r = self.run_plan(lambda p:grid(p,100,100,tokens=('1-1','1-1','2-1')))
        self.assertEqual(r['summary']['matched'],1)
        self.assertEqual(r['summary']['unmatched'],2)
        self.assertEqual(r['duplicate_ids'],['A:1-1'])

    def test_outside_grid_does_not_inherit_header(self):
        def build(p):
            grid(p,100,100)
            p.insert_text((115,300),'9-9',fontsize=8)
        r = self.run_plan(build,4)
        self.assertEqual(r['summary']['matched'],3)
        self.assertEqual(r['unmatched'][0]['reason'],'no_vector_region')


if __name__ == '__main__':
    unittest.main()
