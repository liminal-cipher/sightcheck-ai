"""Score OCR and model readings against blind human labels and build a review queue.

Inputs (all under the review output folder):
- review-template.json: samples with the OCR/CV prediction
- blind-review-result.json: prediction-blind human labels for a seeded subset
- a folder of model readings (result-*.json arrays) keyed by sample_id

Accuracy is reported only on human-labeled items. Items outside the blind subset
are never scored; they are only routed to the review queue.
"""
from pathlib import Path
import argparse
import json
import random
import re

BASE = Path(__file__).resolve().parent


def numbers(text):
    return re.findall(r'\d+', text or '')


def norm_row(text):
    return (text or '').strip().upper()


def ocr_reading(prediction):
    """Map the OCR/CV prediction onto the shared label fields; None means unresolved."""
    if prediction.get('kind') == 'accessibility_or_blue_region':
        return {'is_seat': 'no', 'zone': None, 'row': '', 'number': ''}
    if not prediction.get('seat_id'):
        return None
    block = prediction.get('block')
    return {'is_seat': 'yes', 'zone': block, 'row': norm_row(prediction.get('row')),
            'number': str(prediction.get('number') or '')}


def model_reading(reading):
    if reading is None:
        return None
    return {'is_seat': reading.get('is_seat'), 'zone': reading.get('zone'),
            'row': norm_row(reading.get('row')), 'number': reading.get('number', '')}


def matches(reading, truth):
    """Seat cells need zone, row and number; non-seat regions need only the non-seat call."""
    if reading is None:
        return False
    if truth['is_seat'] != 'yes':
        return reading['is_seat'] == truth['is_seat']
    return (reading['is_seat'] == 'yes' and reading['zone'] == truth['zone']
            and reading['row'] == norm_row(truth.get('row')) and numbers(reading['number']) == numbers(truth.get('number')))


def agree(a, b):
    if a is None or b is None:
        return False
    if a['is_seat'] != 'yes' or b['is_seat'] != 'yes':
        return a['is_seat'] == b['is_seat']
    return a['zone'] == b['zone'] and a['row'] == b['row'] and numbers(a['number']) == numbers(b['number'])


def load_model(folder):
    readings = {}
    for path in sorted(folder.glob('result-*.json')):
        for item in json.loads(path.read_text(encoding='utf-8')):
            if item['sample_id'] in readings:
                raise ValueError(f"Duplicate model reading: {item['sample_id']}")
            readings[item['sample_id']] = item
    return readings


def compare(review, blind, model, spot_checks, seed):
    samples = {s['sample_id']: s for s in review['samples'] if s['unit'] == 'px'}
    truth = {s['sample_id']: s['label'] for s in blind['samples'] if s['label'].get('is_seat')}
    scored = []
    for sample_id, label in sorted(truth.items()):
        ocr, claude = ocr_reading(samples[sample_id]['prediction']), model_reading(model.get(sample_id))
        scored.append({'sample_id': sample_id, 'stratum': samples[sample_id]['stratum'], 'human': label,
                       'ocr_correct': matches(ocr, label), 'ocr_unresolved': ocr is None,
                       'model_correct': matches(claude, label), 'model_missing': claude is None})
    queue, agreed = [], []
    for sample_id in sorted(set(samples) - set(truth)):
        ocr, claude = ocr_reading(samples[sample_id]['prediction']), model_reading(model.get(sample_id))
        entry = {'sample_id': sample_id, 'stratum': samples[sample_id]['stratum'], 'ocr': ocr,
                 'model': model.get(sample_id)}
        (agreed if agree(ocr, claude) else queue).append(entry)
    spot = random.Random(seed).sample(agreed, min(spot_checks, len(agreed)))
    total = len(scored)
    summary = {
        'scored_items': total,
        'ocr_correct': sum(x['ocr_correct'] for x in scored),
        'ocr_unresolved': sum(x['ocr_unresolved'] for x in scored),
        'model_correct': sum(x['model_correct'] for x in scored),
        'model_missing': sum(x['model_missing'] for x in scored),
        'unscored_items': len(samples) - total,
        'disagreements_to_review': len(queue),
        'agreements': len(agreed),
        'agreement_spot_checks': len(spot),
        'limits': ['Blind subset is a random draw from purposive (hard-case-heavy) samples, not the whole plan.',
                   'Model readings came from Claude Code subagents (Opus 5.5, effort high from the '
                   'Claude Code default), not direct API calls; see prompts/seat-reader.md.'],
    }
    return {'summary': summary, 'scored': scored, 'review_queue': queue, 'spot_checks': spot}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('--model-dir', type=Path, default=None, help='Defaults to <output-dir>/subagent-preread')
    parser.add_argument('--spot-checks', type=int, default=10)
    parser.add_argument('--seed', type=int, default=20261114)
    args = parser.parse_args()
    out = args.output_dir
    review = json.loads((out/'review-template.json').read_text(encoding='utf-8'))
    blind = json.loads((out/'blind-review-result.json').read_text(encoding='utf-8'))
    model = load_model(args.model_dir or out/'subagent-preread')
    result = compare(review, blind, model, args.spot_checks, args.seed)
    (out/'reading-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
