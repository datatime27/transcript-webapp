import argparse
import json
from caption_utils import split_multi_speaker_captions, split_into_sentences

parser = argparse.ArgumentParser(description="Split captions and reapply annotations from a previously annotated file.")
parser.add_argument('original',    help="Original (unannotated) input JSON")
parser.add_argument('annotations', help="Annotated JSON to read speaker/modified from")
parser.add_argument('output',      help="Output JSON file")
args = parser.parse_args()


# Load original and run all splits
with open(args.original, encoding='utf-8') as f:
    data = json.load(f)

captions = split_multi_speaker_captions(data['captions'])
captions = split_into_sentences(captions)

# Build lookup from (text, start) → {speaker, modified} from annotations
with open(args.annotations, encoding='utf-8') as f:
    annotations = json.load(f)

annotation_lookup = {}
for c in annotations['captions']:
    key = (c['text'], c['start'])
    annotation_lookup[key] = {k: c[k] for k in ('speaker', 'modified') if k in c}

# Apply annotations; mark anything unmatched as SPLIT_CC
for c in captions:
    key = (c['text'], c['start'])
    if key in annotation_lookup:
        c.update(annotation_lookup[key])
    else:
        c['speaker'] = 'SPLIT_CC'

data['captions'] = captions

with open(args.output, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

matched  = sum(1 for c in captions if c.get('speaker') != 'SPLIT_CC')
split_cc = sum(1 for c in captions if c.get('speaker') == 'SPLIT_CC')
print(f"Total captions: {len(captions)}")
print(f"Matched from annotations: {matched}")
print(f"Marked SPLIT_CC: {split_cc}")
print(f"Written to {args.output}")
