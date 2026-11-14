"""Score several model readers on the human-confirmed JPEG labels.

Primary score: the prediction-blind labels (blind-review-result.json).
Reference score: the queue verdicts (queue-review-result.json). Those were
given while the Opus reading was visible, so they can favor readers that agree
with Opus and are reported separately, never pooled with the blind score.
"""
from pathlib import Path
import argparse
import json

from compare_readings import load_model, matches, model_reading

BASE = Path(__file__).resolve().parent


def queue_truth(item):
    """Turn a queue verdict into a label; None when the verdict gives no answer."""
    review = item.get('review', {})
    verdict = review.get('verdict')
    if verdict in ('both', 'model'):
        return model_reading(item['model'])
    if verdict == 'ocr':
        return item['ocr']
    if verdict == 'neither' and review.get('is_seat'):
        return {k: review.get(k, '') for k in ('is_seat', 'zone', 'row', 'number')}
    return None


def score(readings, truth):
    rows = []
    for sample_id, label in sorted(truth.items()):
        reading = model_reading(readings.get(sample_id))
        rows.append({'sample_id': sample_id, 'correct': matches(reading, label), 'missing': reading is None,
                     'truth': label, 'reading': readings.get(sample_id)})
    return {'items': len(rows), 'correct': sum(r['correct'] for r in rows),
            'missing': sum(r['missing'] for r in rows), 'errors': [r for r in rows if not r['correct']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=BASE/'output/phase-abc')
    parser.add_argument('readers', nargs='+', help='name=folder pairs; folder holds result-*.json, relative to --output-dir')
    args = parser.parse_args()
    out = args.output_dir
    blind = {s['sample_id']: s['label'] for s in json.loads((out/'blind-review-result.json').read_text(encoding='utf-8'))['samples']
             if s['label'].get('is_seat')}
    queue = {x['sample_id']: queue_truth(x) for x in json.loads((out/'queue-review-result.json').read_text(encoding='utf-8'))['items']}
    queue = {k: v for k, v in queue.items() if v is not None}
    report = {}
    for pair in args.readers:
        name, folder = pair.split('=', 1)
        readings = load_model(out/folder)
        report[name] = {'blind': score(readings, blind), 'queue_reference': score(readings, queue)}
    (out/'reader-scores.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, r in report.items():
        print(f"{name}: blind {r['blind']['correct']}/{r['blind']['items']} (missing {r['blind']['missing']}), "
              f"queue reference {r['queue_reference']['correct']}/{r['queue_reference']['items']}")


if __name__ == '__main__':
    main()
