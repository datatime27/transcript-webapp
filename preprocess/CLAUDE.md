# Taskmaster Transcript Processor

This project takes Taskmaster episode audio and a manually-uploaded YouTube JSON transcript, runs speaker diarization, and produces an annotated transcript with speaker labels and corrected timecodes.

## Project Structure

```
audio/                         # Input audio files
  rwKYWuVluJc.mp3

C:\Peter\Software\data-time-repos\word-tracker\transcripts\taskmaster\
  rwKYWuVluJc.json             # Input: YouTube manual transcript JSON

tmp-outputs/                   # Intermediate/debug outputs
  rwKYWuVluJc-diarize.txt      # Raw diarization segments (speaker + timestamps)
  rwKYWuVluJc-aligned.txt      # Human-readable aligned transcript

rwKYWuVluJc.json               # Final output: annotated transcript JSON
check_diarize_gpu.py           # GPU diagnostic script
process-transcript.py          # Main script
```

## Running the Script

```bash
# Basic usage
python process-transcript.py <video_id>

# With drift correction (if JSON timecodes drift by ~2s over the episode)
python process-transcript.py <video_id> --drift 2
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `video_id` | required | YouTube video ID, used to derive all filenames |
| `--drift` | `0.0` | Seconds the JSON timecodes have drifted by end of file. Applies a linear multiplier: `(final_time - drift) / final_time` |

## Pipeline

### Step 1 — Load and prepare JSON captions
- Loads the manual YouTube transcript JSON (`data['captions']`)
- Splits multi-speaker captions separated by `\n-` into two separate captions, each with half the original duration
- Applies drift correction if `--drift` is specified
- Converts captions to the WhisperX segment format expected by `assign_word_speakers`

### Step 2 — Diarize
- Loads audio with `whisperx.load_audio()`
- Runs `DiarizationPipeline` (pyannote) on the audio to detect who is speaking when
- Writes raw diarization segments to `tmp-outputs/{video_id}-diarize.txt`

### Step 3 — Assign speakers
- Calls `whisperx.assign_word_speakers(diarize_segments, transcript_result)` to match diarization speaker labels to JSON caption segments
- Pure sound effect captions (entirely in brackets e.g. `[laughter]`) are labelled `Other` regardless of diarization output

### Step 4 — Write output
- Writes human-readable `tmp-outputs/{video_id}-aligned.txt`
- Writes annotated `{video_id}.json` with `speaker` and updated `start` fields added to each caption

## Output Format

### Aligned TXT
```
[GREG]        34.40s  Hello, thank you.
[ALEX]       130.22s  Well, my guy, today you asked them...
[Other]       44.14s  [laughter]
[UNKNOWN]     67.75s  And next to me
```

### Annotated JSON
Each caption in `data['captions']` gains two new fields:
```json
{
  "text": "Hello, thank you.",
  "start": 34.40,
  "duration": 1.57,
  "speaker": "GREG"
}
```

## caption_utils.py

Preprocessing utilities used by the pipeline. `preprocess_captions(captions)` runs the full pipeline:

1. `strip_music_markers` — removes `#` characters from caption text.
2. `split_multi_speaker_captions` — splits captions containing `\n-` (two speakers on one caption) into separate captions with proportional durations.
3. `split_into_sentences` — splits captions containing multiple sentences into one caption per sentence, with durations proportional to text length. Uses `SENTENCE_SPLIT_RE` (three branches):
   - **No-space boundary** `(?<=\w[.?!])(?=[A-Z][a-zA-Z'])`: fires when `.`, `?`, or `!` is preceded by a word character and immediately followed by a capital letter then any letter or apostrophe. Handles mixed-case (`Yeah`), all-caps (`OK`), and contractions (`I'm`). The two-character lookahead prevents splitting on lone initials (`A.`).
   - **Whitespace boundary** `(?<=[.?!])\s+`: splits on whitespace after sentence-ending punctuation.
   - **Closing-quote boundary** `(?<=[.?!]["'])\s+`: splits on whitespace after sentence-ending punctuation followed by a closing quote or apostrophe (e.g. `"Under doormat." Thank you.` → `["Under doormat."`, `"Thank you."]`).
4. `normalize_soundeffect_captions` — brackets all-caps sound-effect prefixes (e.g. `TINNY VOICE: Hello` → `[TINNY VOICE]: Hello`) and wraps standalone all-caps captions in `[...]`. Leaves `OK`/`OKAY` and already-bracketed captions unchanged.

Unit tests: `test_caption_utils.py` (run with `python -m pytest test_caption_utils.py`).

## Configuration (in script)

| Variable | Value | Description |
|----------|-------|-------------|
| `DEVICE` | `"cuda"` | `"cpu"` if no GPU available |
| `LANGUAGE` | `"en"` | Audio language |
| `MIN_SPEAKERS` | `7` | Taskmaster always has 7 speakers (5 contestants + Greg + Alex) |
| `MAX_SPEAKERS` | `9` | Upper bound in case of guest voices |

## Known Issues

### Diarization running on CPU
The pyannote embedding model uses `onnxruntime` for speaker embeddings. If `onnxruntime` (CPU) and `onnxruntime-gpu` conflict, pyannote silently falls back to CPU. Diagnosis:

```bash
python check_diarize_gpu.py
```

Fix:
```bash
pip uninstall onnxruntime
pip install --force-reinstall onnxruntime-gpu
```

### JSON timecode drift
The manual YouTube transcript timecodes can drift by 1-2 seconds over a 45-minute episode. Use `--drift` to apply a linear correction. To measure drift, compare the timecode of the final caption in the JSON against where it actually occurs in the audio.

## Dependencies

- `whisperx` — diarization pipeline and speaker assignment
- `pyannote.audio` — underlying speaker diarization model (via whisperx)
- `torch` — GPU support
- `onnxruntime-gpu` — GPU inference for pyannote embeddings (must not conflict with CPU onnxruntime)
- `rapidfuzz` — no longer used, can be uninstalled
