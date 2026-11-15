from pathlib import Path
from types import SimpleNamespace
import json
import struct
import tempfile
import unittest
import zlib

from claude_preread import (build_params, estimate, fix_run, load_prompt, parse_message, select_items,
                            write_results)


def tiny_png(path, width=4, height=3):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\x00' + b'\x00' * width * 3 for _ in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def message(text, stop='end_turn'):
    return SimpleNamespace(model='claude-haiku-5-5', id='msg_1', stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20),
                           content=[SimpleNamespace(type='thinking'), SimpleNamespace(type='text', text=text)])


class ClaudePrereadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        (self.out/'review-contexts').mkdir()
        (self.out/'review-crops').mkdir()
        for sid in ('a', 'b'):
            tiny_png(self.out/'review-contexts'/f'{sid}.png', 75, 10)
            tiny_png(self.out/'review-crops'/f'{sid}.png')
        self.review = {'samples': [{'sample_id': s, 'unit': 'px', 'crop': f'review-crops/{s}.png'} for s in ('a', 'b')]
                       + [{'sample_id': 'pdf', 'unit': 'pt', 'crop': 'x.png'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_prompt_is_single_item_and_keeps_field_definitions(self):
        prompt = load_prompt()
        self.assertIn('THE ITEM has two images', prompt)
        self.assertIn('other = anything that is not an individual seat', prompt)
        self.assertNotIn('{manifest_path}', prompt)
        self.assertNotIn('Write tool', prompt)

    def test_select_items_reads_txt_and_samples_json(self):
        self.assertEqual([i['sample_id'] for i in select_items(self.review, self.out)], ['a', 'b'])
        (self.out/'ids.txt').write_text('b\n', encoding='utf-8')
        self.assertEqual([i['sample_id'] for i in select_items(self.review, self.out, self.out/'ids.txt')], ['b'])
        (self.out/'s.json').write_text(json.dumps({'samples': [{'sample_id': 'a'}]}), encoding='utf-8')
        self.assertEqual([i['sample_id'] for i in select_items(self.review, self.out, self.out/'s.json')], ['a'])
        (self.out/'bad.txt').write_text('pdf\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            select_items(self.review, self.out, self.out/'bad.txt')

    def test_request_sets_effort_schema_and_image_order(self):
        item = select_items(self.review, self.out)[0]
        params = build_params(item, 'PROMPT', 'claude-sonnet-5-5', 'medium', 999)
        self.assertEqual(params['output_config']['effort'], 'medium')
        self.assertEqual(params['output_config']['format']['type'], 'json_schema')
        self.assertEqual(params['thinking'], {'type': 'adaptive'})
        kinds = [b.get('text', b['type']) for b in params['messages'][0]['content']]
        self.assertEqual(kinds, ['PROMPT', 'context_image:', 'image', 'crop_image:', 'image'])

    def test_estimate_counts_image_area_and_halves_for_batch(self):
        items = select_items(self.review, self.out)
        full = estimate(items, 'x' * 30, 'claude-opus-5-5', 1000, batch=False)
        half = estimate(items, 'x' * 30, 'claude-opus-5-5', 1000, batch=True)
        self.assertEqual(full['input_tokens_upper'], round(2 * (1 + 12 / 750) + 2 * 60))
        self.assertAlmostEqual(half['usd_upper'], full['usd_upper'] / 2, places=2)

    def test_parse_message_accepts_json_and_flags_truncation(self):
        good = parse_message('a', message('{"is_seat":"yes","zone":"main","row":"A","number":"3",'
                                          '"confidence":"high","note":""}'))
        self.assertTrue(good['ok'])
        self.assertEqual(good['reading']['sample_id'], 'a')
        self.assertFalse(parse_message('a', message('{"is', stop='max_tokens'))['ok'])
        self.assertFalse(parse_message('a', message('not json'))['ok'])

    def test_results_keep_latest_answer_and_run_settings_are_fixed(self):
        run_dir = self.out/'run'
        fix_run(run_dir, {'model': 'claude-haiku-5-5', 'effort': 'low'})
        with self.assertRaises(SystemExit):
            fix_run(run_dir, {'model': 'claude-haiku-5-5', 'effort': 'high'})
        lines = [{'sample_id': 'a', 'ok': False, 'error': 'x'},
                 {'sample_id': 'a', 'ok': True, 'usage': {'input_tokens': 1, 'output_tokens': 1},
                  'reading': {'sample_id': 'a', 'is_seat': 'no', 'zone': 'other', 'row': '', 'number': '',
                              'confidence': 'high', 'note': ''}}]
        (run_dir/'responses.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines), encoding='utf-8')
        write_results(run_dir, batch=False)
        result = json.loads((run_dir/'result-01.json').read_text(encoding='utf-8'))
        self.assertEqual([r['sample_id'] for r in result], ['a'])


if __name__ == '__main__':
    unittest.main()
