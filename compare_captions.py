import json
import sys
from pathlib import Path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare(path_a, path_b):
    a = load(path_a)
    b = load(path_b)

    caps_a = a["captions"]
    caps_b = b["captions"]

    ok = True

    if len(caps_a) != len(caps_b):
        print(f"  COUNT MISMATCH: {len(caps_a)} vs {len(caps_b)} captions")
        ok = False

    mismatches = []
    for i, (ca, cb) in enumerate(zip(caps_a, caps_b)):
        if ca["start"] != cb["start"] or ca["text"] != cb["text"]:
            mismatches.append((i, ca, cb))

    if mismatches:
        ok = False
        print(f"  {len(mismatches)} caption(s) with differing start/text:")
        for i, ca, cb in mismatches:
            print(f"    [{i}]")
            if ca["start"] != cb["start"]:
                print(f"      start: {ca['start']!r} vs {cb['start']!r}")
            if ca["text"] != cb["text"]:
                print(f"      text:  {ca['text']!r} vs {cb['text']!r}")

    if ok:
        print(f"  OK ({len(caps_a)} captions)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_captions.py <original_dir> <merged_dir>")
        sys.exit(1)

    original_dir = Path(sys.argv[1])
    merged_dir   = Path(sys.argv[2])

    merged_files = sorted(merged_dir.glob("*.json"))
    if not merged_files:
        print(f"No .json files found in {merged_dir}")
        sys.exit(1)

    for merged_path in merged_files:
        original_path = original_dir / merged_path.name
        if not original_path.exists():
            print(f"{merged_path.name}: no matching file in original dir, skipping")
            continue
        print(merged_path.name)
        compare(original_path, merged_path)
