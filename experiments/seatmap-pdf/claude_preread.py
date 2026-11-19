"""Read JPEG review items with the Claude API, one request per item.

Modes:
  plan     build every request without an API key; print the item count and a cost estimate
  run      send the requests one at a time (resumable; finished items are skipped)
  submit   send the requests as Message Batches (half price, usually done within an hour);
           a large item list is split into several batches under the request-size limit
  collect  fetch the finished batches

Each run lives in <output-dir>/<name>/: run.json (model, effort, prompt hash and
SDK version, fixed when the run is planned), responses.jsonl (one line per API
answer, with token usage) and result-01.json (readings in the format
score_readers.py and compare_readings.py read).

The prompt is prompts/seat-reader-api.md. Images and readings never leave the
Git-ignored output folder.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import base64
import hashlib
import json
import math
import re
import struct
import threading
from concurrent.futures import ThreadPoolExecutor

BASE = Path(__file__).resolve().parent
PROMPT_FILE = BASE/'prompts/seat-reader-api.md'
MODELS = {'opus': 'claude-opus-5-5', 'sonnet': 'claude-sonnet-5-5', 'haiku': 'claude-haiku-5-5'}
# USD per million input/output tokens, list prices checked 2026-11-15; batch is half.
# Haiku's price applies to prompts of 100K tokens or fewer, which every request here is.
PRICES = {'claude-opus-5-5': (4.0, 20.0), 'claude-sonnet-5-5': (2.0, 10.0), 'claude-haiku-5-5': (0.10, 0.50)}
ZONES = ['main', 'BOX-1', 'BOX-2', 'OP', 'other', 'unknown']
SCHEMA = {
    'type': 'object',
    'properties': {
        'is_seat': {'type': 'string', 'enum': ['yes', 'no', 'unsure']},
        'zone': {'type': 'string', 'enum': ZONES},
        'row': {'type': 'string'},
        'number': {'type': 'string'},
        'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
        'note': {'type': 'string'},
    },
    'required': ['is_seat', 'zone', 'row', 'number', 'confidence', 'note'],
    'additionalProperties': False,
}
BATCH_LIMIT_BYTES = 200 * 1024 * 1024  # the API allows 256 MB; keep a margin for JSON overhead
FIELDS = ['sample_id', 'is_seat', 'zone', 'row', 'number', 'confidence', 'note']


def load_prompt(path=PROMPT_FILE):
    match = re.search(r'```text\n(.*?)\n```', path.read_text(encoding='utf-8'), re.S)
    if not match:
        raise ValueError(f'No ```text block in {path}')
    return match.group(1)


def read_ids(path):
    if path.suffix == '.json':
        return [s['sample_id'] for s in json.loads(path.read_text(encoding='utf-8'))['samples']]
    return path.read_text(encoding='utf-8').split()


def select_items(review, output_dir, ids_paths=None):
    """Return [{sample_id, context, crop}] for the JPEG samples, optionally limited to listed IDs."""
    samples = {s['sample_id']: s for s in review['samples'] if s['unit'] == 'px'}
    if isinstance(ids_paths, Path):
        ids_paths = [ids_paths]
    ids = [i for path in ids_paths for i in read_ids(path)] if ids_paths else sorted(samples)
    missing = [i for i in ids if i not in samples]
    if missing:
        raise ValueError(f'IDs not among the JPEG samples: {missing[:5]}')
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample IDs in the ID list')
    return [{'sample_id': i, 'context': output_dir/'review-contexts'/f'{i}.png',
             'crop': output_dir/samples[i]['crop']} for i in ids]


def cell_items(output_dir, path):
    """Return [{sample_id, context, crop}] from an item list written by make_cell_items.py."""
    samples = json.loads(path.read_text(encoding='utf-8'))['samples']
    ids = [s['sample_id'] for s in samples]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate sample IDs in the item list')
    items = [{'sample_id': s['sample_id'], 'context': output_dir/s['context'], 'crop': output_dir/s['crop']}
             for s in samples]
    missing = [str(p) for it in items for p in (it['context'], it['crop']) if not p.exists()]
    if missing:
        raise ValueError(f'Missing images: {missing[:5]}')
    return items


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'Not a PNG: {path}')
    return struct.unpack('>II', head[16:24])


def _image(path):
    data = base64.standard_b64encode(Path(path).read_bytes()).decode('ascii')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': data}}


def build_params(item, prompt, model, effort, max_tokens):
    return {
        'model': model,
        'max_tokens': max_tokens,
        'thinking': {'type': 'adaptive'},
        'output_config': {'effort': effort, 'format': {'type': 'json_schema', 'schema': SCHEMA}},
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'text', 'text': 'context_image:'}, _image(item['context']),
            {'type': 'text', 'text': 'crop_image:'}, _image(item['crop']),
        ]}],
    }


def image_tokens(width, height, long_edge=2576, max_tokens=4784):
    """Visual tokens after the documented downscaling (28x28-px patches, high-resolution tier).

    Every model this script uses is a Claude 4.7-or-later model, so the
    high-resolution limits apply. The aspect-preserving shrink loop
    approximates the published resize rule.
    """
    scale = min(1.0, long_edge / max(width, height))
    while True:
        tokens = math.ceil(width * scale / 28) * math.ceil(height * scale / 28)
        if tokens <= max_tokens:
            return tokens
        scale *= 0.995


def estimate(items, prompt, model, output_tokens, batch):
    """Upper-bound cost; prompt text is counted at about three characters per token."""
    images = sum(image_tokens(*png_size(it['context'])) + image_tokens(*png_size(it['crop'])) for it in items)
    input_tokens = images + len(items) * (len(prompt) / 3 + 50)
    price_in, price_out = PRICES[model]
    cost = (input_tokens * price_in + len(items) * output_tokens * price_out) / 1e6
    return {'items': len(items), 'input_tokens_upper': round(input_tokens),
            'assumed_output_tokens_per_item': output_tokens, 'usd_upper': round(cost * (0.5 if batch else 1), 2)}


def parse_message(sample_id, message):
    """Turn an API message into a responses.jsonl entry."""
    usage = message.usage
    entry = {'sample_id': sample_id, 'ok': False, 'model': message.model, 'message_id': message.id,
             'stop_reason': message.stop_reason,
             'usage': {'input_tokens': usage.input_tokens, 'output_tokens': usage.output_tokens}}
    if message.stop_reason != 'end_turn':
        entry['error'] = f'stop_reason {message.stop_reason}'
        return entry
    text = next((b.text for b in message.content if b.type == 'text'), None)
    try:
        reading = json.loads(text)
    except (TypeError, json.JSONDecodeError) as err:
        entry['error'] = f'unparseable output: {err}'
        return entry
    entry.update(ok=True, reading={'sample_id': sample_id, **reading})
    return entry


def read_responses(run_dir):
    path = run_dir/'responses.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_results(run_dir, batch):
    """Write result-01.json from the latest answer per item and print usage and cost."""
    latest = {}
    for entry in read_responses(run_dir):
        latest[entry['sample_id']] = entry
    readings = [{k: e['reading'].get(k, '') for k in FIELDS} for _, e in sorted(latest.items()) if e['ok']]
    (run_dir/'result-01.json').write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding='utf-8')
    entries = read_responses(run_dir)
    tokens_in = sum(e.get('usage', {}).get('input_tokens', 0) for e in entries)
    tokens_out = sum(e.get('usage', {}).get('output_tokens', 0) for e in entries)
    model = json.loads((run_dir/'run.json').read_text(encoding='utf-8'))['model']
    price_in, price_out = PRICES[model]
    cost = (tokens_in * price_in + tokens_out * price_out) / 1e6 * (0.5 if batch else 1)
    failed = sorted(k for k, e in latest.items() if not e['ok'])
    print(f'{len(readings)} readings written, {len(failed)} failed; '
          f'{tokens_in} input + {tokens_out} output tokens, about ${cost:.2f} at '
          f'{"batch" if batch else "standard"} price')
    if failed:
        print('Failed:', ', '.join(failed[:10]))


def fix_run(run_dir, settings):
    """Create run.json, or refuse to mix settings into an existing run."""
    path = run_dir/'run.json'
    if path.exists():
        saved = json.loads(path.read_text(encoding='utf-8'))
        changed = {k: (saved.get(k), v) for k, v in settings.items() if saved.get(k) != v}
        if changed:
            raise SystemExit(f'{run_dir.name} was planned with other settings {changed}; use a new --name')
        return saved
    run_dir.mkdir(parents=True, exist_ok=True)
    saved = {**settings, 'planned_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
    return saved


def update_run(run_dir, **fields):
    path = run_dir/'run.json'
    saved = json.loads(path.read_text(encoding='utf-8'))
    saved.update(fields)
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
    return saved


def preview(params):
    """Copy of the request with image data replaced by its size, for inspection."""
    shown = json.loads(json.dumps(params))
    for block in shown['messages'][0]['content']:
        if block['type'] == 'image':
            block['source']['data'] = f"<{len(block['source']['data'])} base64 chars>"
    return shown


def run_sync(client, run_dir, items, prompt, args, model):
    import anthropic
    done = {e['sample_id'] for e in read_responses(run_dir) if e['ok']}
    todo = [it for it in items if it['sample_id'] not in done]
    print(f'{len(done)} already done, sending {len(todo)}')
    lock = threading.Lock()
    fatal = (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError)

    def one(item):
        try:
            message = client.messages.create(**build_params(item, prompt, model, args.effort, args.max_tokens))
            entry = parse_message(item['sample_id'], message)
        except fatal:
            raise
        except anthropic.APIError as err:
            entry = {'sample_id': item['sample_id'], 'ok': False, 'error': f'{type(err).__name__}: {err}'}
        with lock, open(run_dir/'responses.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    with ThreadPoolExecutor(args.workers) as pool:
        for future in [pool.submit(one, it) for it in todo]:
            future.result()


def request_chunks(items, make_params, limit=BATCH_LIMIT_BYTES):
    """Yield lists of batch requests whose JSON size stays under limit (one batch each)."""
    chunk, size = [], 0
    for it in items:
        request = {'custom_id': it['sample_id'], 'params': make_params(it)}
        request_size = len(json.dumps(request))
        if request_size > limit:
            raise SystemExit(f'{it["sample_id"]} alone is {request_size / 2**20:.0f} MB, over the batch limit')
        if chunk and size + request_size > limit:
            yield chunk
            chunk, size = [], 0
        chunk.append(request)
        size += request_size
    if chunk:
        yield chunk


def batch_ids(saved):
    """Batch IDs of a run; runs from before batch splitting stored a single batch_id."""
    return saved.get('batch_ids') or ([saved['batch_id']] if saved.get('batch_id') else [])


def submit_batch(client, run_dir, items, prompt, args, model):
    """Send the requests as one or more batches; each ID is saved as soon as its batch exists."""
    ids = []
    for chunk in request_chunks(items, lambda it: build_params(it, prompt, model, args.effort, args.max_tokens)):
        batch = client.messages.batches.create(requests=chunk)
        ids.append(batch.id)
        update_run(run_dir, batch_ids=ids, submitted_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        print(f'Submitted batch {batch.id} with {len(chunk)} requests')
    print(f'{len(ids)} batch(es) for {len(items)} items; run "collect" later')


def collect_batch(client, run_dir):
    saved = json.loads((run_dir/'run.json').read_text(encoding='utf-8'))
    batches = [client.messages.batches.retrieve(i) for i in batch_ids(saved)]
    pending = [b for b in batches if b.processing_status != 'ended']
    for batch in pending:
        counts = batch.request_counts
        print(f'Batch {batch.id} is {batch.processing_status}: {counts.processing} processing, '
              f'{counts.succeeded} succeeded, {counts.errored} errored')
    if pending:
        return False
    with open(run_dir/'responses.jsonl', 'w', encoding='utf-8') as f:
        for batch in batches:
            for result in client.messages.batches.results(batch.id):
                if result.result.type == 'succeeded':
                    entry = parse_message(result.custom_id, result.result.message)
                elif result.result.type == 'errored':
                    entry = {'sample_id': result.custom_id, 'ok': False, 'error': str(result.result.error)}
                else:
                    entry = {'sample_id': result.custom_id, 'ok': False, 'error': result.result.type}
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    update_run(run_dir, collected_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=['plan', 'run', 'submit', 'collect'])
    parser.add_argument('--name', required=True, help='Run folder under --output-dir, e.g. api-opus-high')
    parser.add_argument('--model', choices=sorted(MODELS), default='opus')
    parser.add_argument('--effort', choices=['low', 'medium', 'high', 'xhigh', 'max'], default='high')
    parser.add_argument('--ids', type=Path, action='append',
                        help='ID list (.txt, one per line) or a *-review-samples.json; repeatable; '
                             'default: every JPEG sample')
    parser.add_argument('--cells', type=Path,
                        help='Item list from make_cell_items.py (e.g. output/phase-abc/cell-items.json) '
                             'instead of the review samples; cannot be combined with --ids')
    parser.add_argument('--prompt', type=Path, default=PROMPT_FILE,
                        help='Prompt file with a ```text block (default: prompts/seat-reader-api.md)')
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--max-tokens', type=int, default=16000, help='Includes thinking tokens')
    parser.add_argument('--workers', type=int, default=4, help='Parallel requests in "run" mode')
    parser.add_argument('--assume-output-tokens', type=int, default=4000,
                        help='Output tokens per item for the cost estimate (thinking included)')
    parser.add_argument('--max-cost', type=float, default=10.0,
                        help='Refuse to send when the upper cost estimate in USD is above this')
    args = parser.parse_args()

    out = args.output_dir
    run_dir = out/args.name
    model = MODELS[args.model]
    prompt_file = args.prompt.resolve()
    prompt = load_prompt(prompt_file)
    batch = args.mode in ('submit', 'collect')

    if args.mode == 'collect':
        import anthropic
        if collect_batch(anthropic.Anthropic(), run_dir):
            write_results(run_dir, batch=True)
        return

    if args.cells and args.ids:
        raise SystemExit('Use either --cells or --ids')
    if args.cells:
        items = cell_items(out, args.cells)
        source = args.cells.name
    else:
        review = json.loads((out/'review-template.json').read_text(encoding='utf-8'))
        items = select_items(review, out, args.ids)
        source = [p.name for p in args.ids] if args.ids else 'all JPEG samples'
    import anthropic  # imported late so "plan" also documents the SDK version it would use
    settings = {'model': model, 'effort': args.effort, 'max_tokens': args.max_tokens, 'thinking': 'adaptive',
                'prompt_file': prompt_file.relative_to(BASE).as_posix(),
                'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
                'sdk': f'anthropic-python {anthropic.__version__}',
                'ids': source, 'items': len(items)}
    fix_run(run_dir, settings)
    cost = estimate(items, prompt, model, args.assume_output_tokens, batch or args.mode == 'plan')
    print(json.dumps(cost, indent=2))

    if args.mode == 'plan':
        (run_dir/'request-preview.json').write_text(
            json.dumps(preview(build_params(items[0], prompt, model, args.effort, args.max_tokens)), indent=2),
            encoding='utf-8')
        print(f'Planned {run_dir}; the estimate above assumes the batch price. Nothing was sent.')
        return
    if cost['usd_upper'] > args.max_cost:
        raise SystemExit(f"Upper estimate ${cost['usd_upper']} exceeds --max-cost {args.max_cost}")
    client = anthropic.Anthropic(max_retries=4)
    if args.mode == 'run':
        run_sync(client, run_dir, items, prompt, args, model)
        write_results(run_dir, batch=False)
    else:
        if batch_ids(json.loads((run_dir/'run.json').read_text(encoding='utf-8'))):
            raise SystemExit(f'{run_dir.name} already has a batch; run "collect" or use a new --name')
        submit_batch(client, run_dir, items, prompt, args, model)


if __name__ == '__main__':
    main()
