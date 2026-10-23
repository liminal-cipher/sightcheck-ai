import unittest
from evaluate_review import evaluate


def sample(name='a',unit='px'):
    return {'sample_id':name,'unit':unit,'shape_detection_attempted':True,
            'prediction':{'seat_id':'A:1','center':[10,10]},
            'review':{'status':'pending','shape_correct':None,'text_correct':None,
                      'identity_correct':None,'expected_center':None,'correction':None}}


class ReviewTests(unittest.TestCase):
    def test_pending_accuracy_is_null(self):
        r = evaluate({'schema_version':1,'samples':[sample()]})
        self.assertIsNone(r['metrics']['identity_correct']['rate'])
        self.assertIsNone(r['population_accuracy'])

    def test_denominators_and_units_are_separate(self):
        a,b,c = sample(),sample('b','pt'),sample('pending')
        a['review'].update(status='reviewed',shape_correct=True,text_correct=False,identity_correct=False,expected_center=[13,14])
        b['review'].update(status='reviewed',text_correct=True,expected_center=[10,12])
        r = evaluate({'schema_version':1,'samples':[a,b,c]})
        self.assertEqual(r['metrics']['text_correct']['rate'],.5)
        self.assertEqual(r['metrics']['identity_correct']['evaluated'],1)
        self.assertEqual(r['metrics']['wrong_auto_match']['rate'],1)
        self.assertEqual(r['position_error']['px']['mean'],5)
        self.assertEqual(r['position_error']['pt']['mean'],2)
        self.assertEqual(r['pending'],1)

    def test_uncertain_does_not_count_as_wrong(self):
        a = sample(); a['review'].update(status='uncertain',identity_correct=False)
        r = evaluate({'schema_version':1,'samples':[a]})
        self.assertEqual(r['metrics']['identity_correct']['evaluated'],0)

    def test_duplicate_samples_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            evaluate({'schema_version':1,'samples':[sample(),sample()]})

    def test_pdf_text_boxes_not_scored_as_shape_detection(self):
        a = sample(); a['shape_detection_attempted'] = False
        a['review'].update(status='reviewed',shape_correct=True)
        with self.assertRaisesRegex(ValueError,'not attempted'):
            evaluate({'schema_version':1,'samples':[a]})


if __name__ == '__main__':
    unittest.main()
