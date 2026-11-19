from pathlib import Path
from types import SimpleNamespace
import json
import struct
import tempfile
import unittest
import zlib

from claude_preread import (batch_ids, build_params, cell_items, collect_batch, estimate, fix_run, image_tokens,
                            load_prompt, parse_message, request_chunks, select_items, write_results)


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
        both = select_items(self.review, self.out, [self.out/'ids.txt', self.out/'s.json'])
        self.assertEqual([i['sample_id'] for i in both], ['b', 'a'])
        with self.assertRaises(ValueError):
            select_items(self.review, self.out, [self.out/'ids.txt', self.out/'ids.txt'])
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
        self.assertEqual(full['input_tokens_upper'], 2 * (3 + 1) + 2 * 60)
        self.assertAlmostEqual(half['usd_upper'], full['usd_upper'] / 2, places=2)

    def test_image_tokens_follow_documented_examples(self):
        self.assertEqual(image_tokens(1000, 1000), 1296)
        self.assertEqual(image_tokens(1920, 1080), 2691)
        self.assertEqual(image_tokens(3840, 2160), 4784)
        self.assertLessEqual(image_tokens(1754, 2550), 4784)

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

    def test_cell_items_read_explicit_paths_and_require_images(self):
        listing = {'samples': [{'sample_id': 't--a', 'context': 'review-contexts/a.png', 'crop': 'review-crops/a.png'}]}
        (self.out/'cells.json').write_text(json.dumps(listing), encoding='utf-8')
        items = cell_items(self.out, self.out/'cells.json')
        self.assertEqual(items[0]['crop'], self.out/'review-crops/a.png')
        listing['samples'].append({'sample_id': 't--b', 'context': 'missing.png', 'crop': 'review-crops/b.png'})
        (self.out/'cells.json').write_text(json.dumps(listing), encoding='utf-8')
        with self.assertRaises(ValueError):
            cell_items(self.out, self.out/'cells.json')

    def test_requests_split_under_the_size_limit_in_order(self):
        items = [{'sample_id': str(i)} for i in range(5)]
        one = len(json.dumps({'custom_id': '0', 'params': {'x': 'y' * 50}}))
        chunks = list(request_chunks(items, lambda it: {'x': 'y' * 50}, limit=one * 2))
        self.assertEqual([[r['custom_id'] for r in c] for c in chunks], [['0', '1'], ['2', '3'], ['4']])
        with self.assertRaises(SystemExit):
            list(request_chunks(items, lambda it: {'x': 'y' * 50}, limit=one - 1))

    def test_collect_waits_for_every_batch_and_keeps_old_runs(self):
        self.assertEqual(batch_ids({'batch_id': 'old'}), ['old'])
        self.assertEqual(batch_ids({'batch_ids': ['b1', 'b2']}), ['b1', 'b2'])
        run_dir = self.out/'run'
        fix_run(run_dir, {'model': 'claude-haiku-5-5', 'batch_ids': ['b1', 'b2']})
        text = '{"is_seat":"yes","zone":"main","row":"A","number":"1","confidence":"high","note":""}'
        status = {'b1': 'ended', 'b2': 'in_progress'}
        counts = SimpleNamespace(processing=1, succeeded=0, errored=0)
        results = {'b1': [SimpleNamespace(custom_id='x', result=SimpleNamespace(type='succeeded', message=message(text)))],
                   'b2': [SimpleNamespace(custom_id='y', result=SimpleNamespace(type='expired'))]}
        batches = SimpleNamespace(retrieve=lambda i: SimpleNamespace(id=i, processing_status=status[i], request_counts=counts),
                                  results=lambda i: results[i])
        client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
        self.assertFalse(collect_batch(client, run_dir))
        self.assertFalse((run_dir/'responses.jsonl').exists())
        status['b2'] = 'ended'
        self.assertTrue(collect_batch(client, run_dir))
        lines = [json.loads(l) for l in (run_dir/'responses.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(l['sample_id'], l['ok']) for l in lines], [('x', True), ('y', False)])


if __name__ == '__main__':
    unittest.main()
