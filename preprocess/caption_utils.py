import re

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def format_caption_text(text):
    """Clean up caption text for output — preserve sound effects,
    collapse newlines, strip leading dashes."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'^\s*-', '', text, flags=re.MULTILINE)
    return re.sub(r'\s+', ' ', text).strip()


def _clean_html_split_part(text):
    """Remove orphaned HTML tags at the boundaries of a split caption part.
    - Trailing opening tags (e.g. "<i>" cut off at split point)
    - Leading closing tags (e.g. "</i>" whose opener is in the other part)
    - Trailing closing tags with no matching opener in this part
    """
    # Remove trailing opening tags
    text = re.sub(r'(\s*<[^/>][^>]*>)+\s*$', '', text)
    # Remove leading closing tags
    text = re.sub(r'^(\s*</[^>]+>)+\s*', '', text)
    # Remove trailing closing tags with no matching opener
    m = re.search(r'\s*</(\w+)>\s*$', text)
    if m and f'<{m.group(1)}' not in text[:m.start()]:
        text = text[:m.start()]
    return text.strip()


def strip_music_markers(captions):
    """Remove # music notation markers from caption text.
    Surrounding whitespace is left for the downstream whitespace normaliser."""
    result = []
    for c in captions:
        text = c['text'].replace('#', '')
        if text != c['text']:
            c = {**c, 'text': text}
        result.append(c)
    return result


def split_multi_speaker_captions(captions):
    """Split captions containing two or more speakers separated by a newline-dash.
    Uses stripped text for split detection and duration calculation.
    HTML tags are preserved in the output with orphaned boundary tags cleaned up.
    Normalises literal \\n before looking for the split point."""
    result = []
    for c in captions:
        text     = c['text'].replace('\\n', '\n')
        stripped = re.sub(r'<[^>]+>', '', text)
        if re.search(r'\n\s*-', stripped):
            parts_stripped = re.split(r'\n\s*-', stripped)
            parts_html     = re.split(r'\n\s*-', text)
            lengths = [
                len((p.lstrip('-') if i == 0 else p).strip())
                for i, p in enumerate(parts_stripped)
            ]
            total = sum(lengths)
            start = c['start']
            for i, (ph, length) in enumerate(zip(parts_html, lengths)):
                dur  = c['duration'] * length / total
                part = _clean_html_split_part(ph)
                part = part.lstrip('-').strip() if i == 0 else part.strip()
                result.append({**c, 'text': part, 'start': start, 'duration': dur})
                start += dur
        else:
            result.append({**c, 'text': c['text']})
    return result


# Split on whitespace that follows sentence-ending punctuation.
# (?<=[.?!]) — positive lookbehind: must follow a sentence-ending punctuation mark
#              including the final '.' in an ellipsis like '...'
# \s+        — one or more whitespace characters (including newlines)
#
# Example splits:
#   "Hello. World"     -> ["Hello.", "World"]
#   "Hello... World"   -> ["Hello...", "World"]
#   "Hello... world"   -> ["Hello...", "world"]
#   "Dr. Smith"        -> ["Dr.", "Smith"]
#
# Example non-splits:
#   "I'm 2.5 km away"  -> ["I'm 2.5 km away"]
#   "U.S.A."           -> ["U.S.A."]   # no whitespace after punctuation
SENTENCE_SPLIT_RE = re.compile(r'(?<=[.?!])\s+')

def split_into_sentences(captions):
    """Split captions containing multiple sentences into one caption per sentence.
    Normalises internal whitespace/newlines first. Duration proportional to text length."""
    result = []
    for c in captions:
        text  = re.sub(r'\s+', ' ', c['text']).strip()
        parts = SENTENCE_SPLIT_RE.split(text)
        if len(parts) == 1:
            result.append({**c, 'text': text})
            continue
        total = sum(len(p) for p in parts)
        start = c['start']
        for part in parts:
            dur = c['duration'] * len(part) / total
            result.append({**c, 'text': part, 'start': start, 'duration': dur})
            start += dur
    return result


# Matches an all-caps prefix (one or more capitalised words) followed by a
# colon or space separator, then any remaining text.  Examples:
#   'TINNY VOICE: Hello, Greggy.'  →  prefix='TINNY VOICE', sep=': ', rest='Hello, Greggy.'
#   'GREG Oh, interesting.'        →  prefix='GREG',        sep=' ',  rest='Oh, interesting.'
#   'WHISTLE BLOWS Not bad.'       →  prefix='WHISTLE BLOWS', sep=' ', rest='Not bad.'
#   'ROSIE: OK.'                   →  prefix='ROSIE',       sep=': ', rest='OK.'
_CAPS_PREFIX_RE = re.compile(r'^([A-Z]{2,}(?:-[A-Z]+)*(?:\s+[A-Z]+(?:-[A-Z]+)*)*)(:\s*|\s+)(.+)$', re.DOTALL)

# All-caps words that are spoken responses, not sound effects.
_SPOKEN_ALL_CAPS_RE = re.compile(r'^(?:OK(?:AY)?[.!?,]*\s*)+$')

def preprocess_captions(captions):
    """Full preprocessing pipeline: strip music markers, split multi-speaker
    captions, split into sentences, and normalise sound-effect formatting."""
    captions = strip_music_markers(captions)
    captions = split_multi_speaker_captions(captions)
    captions = split_into_sentences(captions)
    captions = normalize_soundeffect_captions(captions)
    return captions


def normalize_soundeffect_captions(captions):
    """Normalise sound-effect and stage-direction captions:
    - All-caps prefix followed by mixed-case speech (or OK/OKAY) gets the prefix bracketed:
        'TINNY VOICE: Hello, Greggy.' → '[TINNY VOICE]: Hello, Greggy.'
        'GREG Oh, interesting.'       → '[GREG] Oh, interesting.'
        'WHISTLE BLOWS Not bad.'      → '[WHISTLE BLOWS] Not bad.'
        'ROSIE: OK.'                  → '[ROSIE]: OK.'
    - All-caps captions not already bracketed are fully wrapped:
        'LAUGHTER CHEERING AND APPLAUSE' → '[LAUGHTER CHEERING AND APPLAUSE]'
    Captions already wrapped in [...] are left unchanged."""
    result = []
    for c in captions:
        text = c['text'].strip()
        if not (text.startswith('[') and text.endswith(']')):
            m = _CAPS_PREFIX_RE.match(text)
            rest = m.group(3).strip() if m else None
            if m and (not rest.isupper() or _SPOKEN_ALL_CAPS_RE.match(rest)) \
                    and not _SPOKEN_ALL_CAPS_RE.match(m.group(1)):
                sep = ': ' if ':' in m.group(2) else ' '
                c = {**c, 'text': f'[{m.group(1)}]{sep}{rest}'}
            elif text.isupper() and not _SPOKEN_ALL_CAPS_RE.match(text) \
                    and re.search(r'[A-Z]{2,}', text):
                c = {**c, 'text': f'[{text}]'}
        result.append(c)
    return result


def captions_to_whisperx_segments(captions):
    """Convert JSON captions to the segment format expected by
    whisperx.assign_word_speakers:
      [{'start': float, 'end': float, 'text': str, 'words': [...]}]
    Each caption becomes one segment. Words list contains a single entry
    spanning the whole segment so speaker assignment works correctly."""
    segments = []
    for c in captions:
        text = format_caption_text(c['text'])
        if not text:
            continue
        start = c['start']
        end   = start + c.get('duration', 1.0)
        segments.append({
            'start': start,
            'end':   end,
            'text':  text,
            'words': [{'word': text, 'start': start, 'end': end, 'score': 1.0}]
        })
    return segments


def write_txt(captions, path):
    """Write aligned captions to a txt file."""
    lines = []
    for c in captions:
        text = format_caption_text(c['text'])
        if not text:
            continue
        speaker = c.get('speaker', 'UNKNOWN')
        start   = c.get('start', 0)
        lines.append(f"[{speaker+']':10} {start:8.2f}s  {text}")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  Written to {path}")
