"""Score explicitly reviewed samples only; never convert counts to accuracy."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path


def evaluate(review, include_documents=True):
    if review.get('schema_version') != 1:
        raise ValueError('Unsupported review schema')
    samples = review['samples']
    ids = [s['sample_id'] for s in samples]
    if len(ids)!=len(set(ids)):
        raise ValueError('Duplicate sample IDs')
    measurements = defaultdict(list)
    positions = defaultdict(list)
    reviewed = 0
    corrections = []
    unmatched = 0
    for sample in samples:
        result = sample['review']
        if result['status'] not in ['pending','reviewed','uncertain']:
            raise ValueError('Invalid review status')
        if result['status'] != 'reviewed':
            continue
        reviewed += 1
        predicted = sample['prediction']
        for field in ['shape_correct','text_correct','identity_correct']:
            value = result.get(field)
            if value is not None and not isinstance(value,bool):
                raise ValueError(f'{field} must be boolean or null')
            if value is not None:
                if field == 'shape_correct' and not sample['shape_detection_attempted']:
                    raise ValueError('Shape detection was not attempted for this sample')
                measurements[field].append(value)
        if predicted.get('seat_id') is not None and result.get('identity_correct') is not None:
            measurements['wrong_auto_match'].append(not result['identity_correct'])
        if predicted.get('seat_id') is None:
            unmatched += 1
        center = result.get('expected_center')
        if center is not None:
            if sample['unit'] not in ['px','pt'] or len(center)!=2 or not all(isinstance(n,(float,int)) and math.isfinite(n) for n in center):
                raise ValueError('Expected finite coordinates in original px or pt')
            positions[sample['unit']].append(math.dist(center,predicted['center']))
        if result.get('correction') or any(result.get(f) is False for f in ['shape_correct','text_correct','identity_correct']):
            corrections.append(sample['sample_id'])
    metrics = {}
    for field in ['shape_correct','text_correct','identity_correct','wrong_auto_match']:
        values = measurements[field]
        metrics[field] = {'evaluated':len(values),'positive':sum(values),
                          'rate':sum(values)/len(values) if values else None}
    report = {'sample_count':len(samples),'reviewed':reviewed,
            'pending':sum(s['review']['status']=='pending' for s in samples),
            'uncertain':sum(s['review']['status']=='uncertain' for s in samples),
            'metrics':metrics,'reviewed_unmatched':unmatched,'correction_sample_ids':corrections,
            'position_error':{unit:{'count':len(values),'mean':sum(values)/len(values),'max':max(values)}
                              for unit,values in positions.items()},
            'manually_recorded_missed_objects':review.get('missed_objects',[]),
            'population_accuracy':None,'detection_recall':None,
            'limits':['Purposive review samples are not an unbiased population estimate.',
                      'Recall requires an independently completed region inventory, not candidate-only samples.',
                      'PDF position anchor is text center; JPEG anchor is shape center. Units never mixed.']}
    if include_documents:
        documents = sorted({s.get('document','unspecified') for s in samples})
        report['per_document'] = {name:evaluate({'schema_version':1,
            'samples':[s for s in samples if s.get('document','unspecified')==name],
            'missed_objects':[m for m in review.get('missed_objects',[]) if m.get('document')==name]},False)
            for name in documents}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review',type=Path); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(args.review.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'reviewed':report['reviewed'],'sample_count':report['sample_count'],'population_accuracy':None}))
