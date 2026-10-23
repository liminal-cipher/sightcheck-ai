import unittest
from PIL import Image, ImageDraw
from image_baseline import detect_shapes, assign_identity, bound_box_zones, gap_candidates


class ImageTests(unittest.TestCase):
    def test_gray_cells_not_blue_accessibility_or_stage(self):
        image = Image.new('RGB',(600,400),'white'); draw = ImageDraw.Draw(image)
        for x in [20,60,100,140]:
            draw.rectangle((x,100,x+29,129),fill=(130,130,130))
        draw.rectangle((200,100,259,129),fill=(70,140,235))
        draw.rectangle((20,200,550,380),outline=(70,140,235),width=5)
        seats,rows,blue,_ = detect_shapes(image)
        self.assertEqual(len(seats),4)
        self.assertEqual(len(blue),1)

    def test_conflicting_and_single_row_marker_abstain(self):
        rows = [{'text':'A','confidence':95,'center_px':[10,100]},
                {'text':'B','confidence':95,'center_px':[200,100]}]
        self.assertIsNone(assign_identity([80,85,30,30],1,rows,[],30)['seat_id'])
        self.assertIsNone(assign_identity([80,85,30,30],1,rows[:1],[],30)['seat_id'])

    def test_box_does_not_reach_next_floor(self):
        zones = [{'text':'BOX-1','bbox':{'x0':10,'x1':50,'y0':10,'y1':30}}]
        boxes = [[15,45,30,30],[15,85,30,30],[15,300,30,30]]
        bound_box_zones(zones,boxes,30)
        self.assertEqual(assign_identity(boxes[0],1,[],zones,30)['seat_id'],'BOX-1:1')
        self.assertIsNone(assign_identity(boxes[2],1,[],zones,30)['seat_id'])

    def test_gap_is_not_promoted_to_a_seat(self):
        gaps = gap_candidates([{'center_px':[20,50]},{'center_px':[80,50]}],30)
        self.assertEqual(len(gaps),1)
        self.assertFalse(gaps[0]['is_seat'])


if __name__ == '__main__':
    unittest.main()
