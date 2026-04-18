import argparse
import json

# Global speaker name corrections applied at the end of apply_annotations.
# Add entries here whenever a name needs to be normalised across all captions.
SPEAKER_RENAMES = {
    "Babátu?nde? Aléshé": "Babátúndé Aléshé"
}

def to_float(v):
    try:
        return float(str(v).strip().rstrip('s'))
    except (ValueError, TypeError):
        return 0.0

def apply_annotations(user_version, new_base, compare_text=False):
    """Merge captions from new_base into user_version:
    - Same start + duration (+ text if compare_text) → keep user_version caption unchanged
    - Same start, different duration or text → replace with new_base caption, set speaker='ALTERED_CC'
    - Start not in user_version → insert new_base caption in start-time order, set speaker='ALTERED_CC'

    Returns user_version modified in place."""

    user_by_start = {to_float(c['start']): i for i, c in enumerate(user_version['captions'])}

    inserts = []

    for nb_cap in new_base['captions']:
        nb_start = to_float(nb_cap['start'])

        if nb_start in user_by_start:
            idx = user_by_start[nb_start]
            uv_cap = user_version['captions'][idx]
            duration_changed = uv_cap.get('duration') != nb_cap.get('duration')
            text_changed = compare_text and uv_cap.get('text') != nb_cap.get('text')
            if duration_changed or text_changed:
                new_cap = dict(nb_cap)
                new_cap['speaker'] = 'ALTERED_CC'
                user_version['captions'][idx] = new_cap
            # else: exact match — leave unchanged
        else:
            new_cap = dict(nb_cap)
            new_cap['speaker'] = 'ALTERED_CC'
            inserts.append(new_cap)

    if inserts:
        user_version['captions'] = sorted(
            user_version['captions'] + inserts,
            key=lambda c: to_float(c['start']),
        )

    for c in user_version['captions']:
        if c.get('speaker') in SPEAKER_RENAMES:
            c['speaker'] = SPEAKER_RENAMES[c['speaker']]

    return user_version


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Merge new_base captions into a user-annotated version.")
    parser.add_argument('user_version', help="User-annotated JSON (base to preserve)")
    parser.add_argument('new_base',     help="New base transcript JSON to merge in")
    parser.add_argument('output',       help="Output JSON file")
    args = parser.parse_args()

    with open(args.user_version, encoding='utf-8') as f:
        user_version = json.load(f)

    with open(args.new_base, encoding='utf-8') as f:
        new_base = json.load(f)

    result = apply_annotations(user_version, new_base)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4)

    captions   = result['captions']
    altered_cc = sum(1 for c in captions if c.get('speaker') == 'ALTERED_CC')
    print(f"Total captions: {len(captions)}")
    print(f"Unchanged: {len(captions) - altered_cc}")
    print(f"Marked ALTERED_CC: {altered_cc}")
    print(f"Written to {args.output}")
