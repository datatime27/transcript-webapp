import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
import whisperx
from whisperx.diarize import DiarizationPipeline
import torch
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

import argparse
import os
import json
import re
from caption_utils import (
    format_caption_text,
    preprocess_captions,
    captions_to_whisperx_segments,
    write_txt,
)

parser = argparse.ArgumentParser(description="Process and align a Taskmaster transcript.")
parser.add_argument(
    '--drift',
    type=float,
    default=0.0,
    help="Number of seconds the JSON transcript has drifted by the end of the file. "
         "The multiplier (final_time - drift) / final_time is applied to all "
         "JSON timecodes. 0 = no correction (default)."
)
parser.add_argument(
    '--trim',
    type=str,
    default='60:00',
    help="Discard captions with start time >= this value. Format: MM:SS or HH:MM:SS (default: 60:00)."
)
parser.add_argument(
    'video_id',
    help="YouTube video ID (e.g. rwKYWuVluJc). Used to derive all input and output filenames."
)
args = parser.parse_args()

parts = args.trim.split(':')
if len(parts) == 2:
    trim_seconds = int(parts[0]) * 60 + float(parts[1])
elif len(parts) == 3:
    trim_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
else:
    parser.error("--trim must be in MM:SS or HH:MM:SS format")


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
VIDEO_ID          = args.video_id
AUDIO_FILE        = f"audio/{VIDEO_ID}.mp3"
JSON_FILE         = f"C:\\Peter\\Software\\data-time-repos\\word-tracker\\transcripts\\taskmaster\\{VIDEO_ID}.json"

# Validate input files exist before doing any heavy work
if not os.path.exists(JSON_FILE):
    parser.error(f"JSON transcript not found: {JSON_FILE}")
if not os.path.exists(AUDIO_FILE):
    parser.error(f"Audio file not found: {AUDIO_FILE}")

# Derived output filenames
os.makedirs("tmp-outputs", exist_ok=True)
OUTPUT_DIARIZE    = f"tmp-outputs/{VIDEO_ID}-diarize.txt"
OUTPUT_ALIGNED    = f"tmp-outputs/{VIDEO_ID}-aligned.txt"
OUTPUT_JSON       = f"{VIDEO_ID}.json"

DEVICE            = "cuda"    # "cpu" if no GPU
LANGUAGE          = "en"
MIN_SPEAKERS      = 7         # Taskmaster always has 7 speakers
MAX_SPEAKERS      = 9         # In case of extra voices



# ─────────────────────────────────────────────
# STEP 1 — LOAD AND PREPARE JSON CAPTIONS
# ─────────────────────────────────────────────
print("Loading JSON transcript...")
with open(JSON_FILE, encoding='utf-8') as f:
    data = json.load(f)

raw_captions = data['captions']
captions     = preprocess_captions(raw_captions)
print(f"  Captions after splitting: {len(captions)} (was {len(raw_captions)})")

before   = len(captions)
captions = [c for c in captions if c['start'] < trim_seconds]
print(f"  Trimmed to {len(captions)} captions (removed {before - len(captions)} after {args.trim})")

# Apply drift correction multiplier if drift is specified
if args.drift != 0.0:
    final_json_time  = max(c['start'] for c in captions)
    drift_multiplier = (final_json_time - args.drift) / final_json_time
    print(f"  Drift correction: final={final_json_time:.2f}s, drift={args.drift}s, multiplier={drift_multiplier:.6f}")
    for c in captions:
        c['start'] = round(c['start'] * drift_multiplier, 2)
else:
    print("  No drift correction applied")

# Convert captions to WhisperX segment format
wx_segments = captions_to_whisperx_segments(captions)
print(f"  Converted to {len(wx_segments)} WhisperX segments")


# ─────────────────────────────────────────────
# STEP 2 — DIARIZE
# ─────────────────────────────────────────────
print("\nLoading audio...")
audio = whisperx.load_audio(AUDIO_FILE)

print("Loading diarization model...")
diarize_model = DiarizationPipeline(device=torch.device(DEVICE))

print("Diarizing...")
diarize_segments = diarize_model(
    audio,
    min_speakers=MIN_SPEAKERS,
    max_speakers=MAX_SPEAKERS
)

# Write raw diarization segments to file
with open(OUTPUT_DIARIZE, 'w', encoding='utf-8') as f:
    f.write(f"{'SPEAKER':<15} {'START':>8}  {'END':>8}\n")
    f.write("-" * 36 + "\n")
    for _, row in diarize_segments.iterrows():
        f.write(f"{row['speaker']:<15} {row['start']:>8.2f}s {row['end']:>8.2f}s\n")
print(f"  Written to {OUTPUT_DIARIZE}")


# ─────────────────────────────────────────────
# STEP 3 — ASSIGN SPEAKERS
# ─────────────────────────────────────────────
print("\nAssigning speakers...")
transcript_result = {'segments': wx_segments}
result = whisperx.assign_word_speakers(diarize_segments, transcript_result)

# Map speaker labels back onto captions
caption_iter = iter([c for c in captions if format_caption_text(c['text'])])
for seg in result['segments']:
    cap = next(caption_iter, None)
    if cap:
        speaker = seg.get('speaker', 'UNKNOWN')
        # Override with 'Other' for pure sound effect captions
        if re.fullmatch(r'\[.*\]', format_caption_text(cap['text']).strip()):
            speaker = 'Other'
        cap['speaker'] = speaker


# ─────────────────────────────────────────────
# STEP 4 — WRITE OUTPUT
# ─────────────────────────────────────────────
print("\nWriting output...")

# Write the processed captions back into data for JSON output
data['captions'] = captions

write_txt(captions, OUTPUT_ALIGNED)

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)
print(f"  Written to {OUTPUT_JSON}")

matched   = sum(1 for c in captions if c.get('speaker') not in ('UNKNOWN', 'Other', None))
other     = sum(1 for c in captions if c.get('speaker') == 'Other')
unmatched = sum(1 for c in captions if c.get('speaker') in ('UNKNOWN', None))

print(f"\nDone!")
print(f"  Total captions:          {len(captions)}")
print(f"  Matched (speaker known): {matched}")
print(f"  Other (sound effects):   {other}")
print(f"  Unmatched [UNKNOWN]:     {unmatched}")