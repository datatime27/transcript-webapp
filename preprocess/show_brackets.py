import json
import sys
from collections import Counter

path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    data = json.load(f)

texts = [c['text'] for c in data['captions'] if '[' in c['text'] or ']' in c['text']]
for text, count in Counter(texts).most_common():
    print(f"{count:4}  {text}")
