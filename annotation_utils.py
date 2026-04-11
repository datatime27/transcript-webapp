import argparse
import json
import re


def apply_annotations(source, annotations, tolerance, use_altered_cc=True):
    """Apply speaker/modified annotations from a previously annotated JSON object
    onto a source JSON object. Captions are matched by text and start time (within
    tolerance seconds).

    If use_altered_cc is True (default), unmatched captions are marked with
    speaker='ALTERED_CC'. If False, unmatched captions take the speaker (and
    modified flag) from the nearest annotation by start time.

    Returns the annotated source JSON object (modified in place)."""
    def to_float(v):
        try:
            return float(str(v).strip().rstrip('s'))
        except (ValueError, TypeError):
            return 0.0

    annotation_lookup = {}
    for c in annotations['captions']:
        entry = {k: c[k] for k in ('speaker', 'modified') if k in c}
        annotation_lookup.setdefault(re.sub(r'\s+', ' ', c['text']), []).append((c['start'], entry))

    if not use_altered_cc:
        ann_by_time = sorted(
            [{**{k: c[k] for k in ('speaker', 'modified') if k in c}, 'start': to_float(c['start'])}
             for c in annotations['captions']],
            key=lambda a: a['start'],
        )

    for c in source['captions']:
        candidates = annotation_lookup.get(c['text'], [])
        match = next((entry for start, entry in candidates if abs(start - c['start']) <= tolerance), None)
        if match:
            c.update(match)
        elif use_altered_cc:
            c['speaker'] = 'ALTERED_CC'
        else:
            nearest = min(ann_by_time, key=lambda a: abs(a['start'] - to_float(c['start'])), default=None)
            if nearest:
                c.update({k: nearest[k] for k in ('speaker', 'modified') if k in nearest})

    return source


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reapply annotations from a previously annotated file.")
    parser.add_argument('original',    help="Original (unannotated) input JSON")
    parser.add_argument('annotations', help="Annotated JSON to read speaker/modified from")
    parser.add_argument('output',      help="Output JSON file")
    parser.add_argument('--tolerance', type=float, default=5.0,
                        help="Max start time difference in seconds to still count as a match (default: 5.0)")
    parser.add_argument('--no-altered-cc', action='store_true',
                        help="Use nearest annotation's speaker instead of ALTERED_CC for unmatched captions")
    args = parser.parse_args()

    with open(args.original, encoding='utf-8') as f:
        source = json.load(f)

    with open(args.annotations, encoding='utf-8') as f:
        annotations = json.load(f)

    result = apply_annotations(source, annotations, args.tolerance, use_altered_cc=not args.no_altered_cc)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4)

    captions   = result['captions']
    matched    = sum(1 for c in captions if c.get('speaker') != 'ALTERED_CC')
    altered_cc = sum(1 for c in captions if c.get('speaker') == 'ALTERED_CC')
    print(f"Total captions: {len(captions)}")
    print(f"Matched from annotations: {matched}")
    if args.no_altered_cc:
        print(f"Unmatched (used nearest speaker): {len(captions) - matched}")
    else:
        print(f"Marked ALTERED_CC: {altered_cc}")
    print(f"Written to {args.output}")
