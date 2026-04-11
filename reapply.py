#!/usr/bin/env python3
"""
CGI script — reapply annotations tool (admin only).

  GET /reapply.py?user={admin_uid}&version={version_uid}
    → runs apply_annotations(original_v1, version, tolerance=5)
    → returns { episode_title, user_name, youtube_id,
                total, matched, altered_cc,
                user_captions:   [{text, start, speaker}, ...]
                result_captions: [{text, start, speaker}, ...]
                row_matches:     [int|null, ...]  ← index into user_captions per result row
              }
"""

import copy
import json
import os
import re
import sys
import traceback

status = "200 OK"
body   = ""

try:
    from urllib.parse import parse_qs
    from db import is_admin, get_reapply_data
    from annotation_utils import apply_annotations

    def valid_id(uid):
        return uid and all(c.isalnum() or c in "-_" for c in uid)

    def to_float(v):
        try:
            return float(str(v).strip().rstrip('s'))
        except (ValueError, TypeError):
            return 0.0

    params         = parse_qs(os.environ.get("QUERY_STRING", ""))
    user_uid       = params.get("user",       [""])[0]
    version_uid    = params.get("version",    [""])[0]
    use_altered_cc = params.get("altered_cc", ["1"])[0] != "0"

    if not valid_id(user_uid) or not is_admin(user_uid):
        status = "403 Forbidden"
        body   = json.dumps({"error": "Admin access required"})

    elif not valid_id(version_uid):
        status = "400 Bad Request"
        body   = json.dumps({"error": "version parameter is required"})

    else:
        original_filepath, version_filepath, episode_title, user_name, youtube_id, user_uid, episode_uid = get_reapply_data(version_uid)

        if not version_filepath:
            status = "404 Not Found"
            body   = json.dumps({"error": f"Version not found: {version_uid}"})
        elif not original_filepath:
            status = "404 Not Found"
            body   = json.dumps({"error": "No original (null-user) version found for this episode"})
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, original_filepath), encoding='utf-8') as f:
                source = json.load(f)
            with open(os.path.join(base, version_filepath), encoding='utf-8') as f:
                annotations = json.load(f)

            result          = apply_annotations(copy.deepcopy(source), annotations, tolerance=5, use_altered_cc=use_altered_cc)
            result_captions = result['captions']
            user_captions   = annotations['captions']

            # Compute which user caption each result caption matched (same logic as apply_annotations)
            annotation_lookup_idx = {}
            for idx, c in enumerate(user_captions):
                key = re.sub(r'\s+', ' ', c['text'])
                annotation_lookup_idx.setdefault(key, []).append((to_float(c['start']), idx))

            row_matches = []
            for c in source['captions']:
                candidates = annotation_lookup_idx.get(c['text'], [])
                c_start    = to_float(c['start'])
                match_idx  = next(
                    (idx for start, idx in candidates if abs(start - c_start) <= 5),
                    None
                )
                row_matches.append(match_idx)

            altered_cc          = sum(1 for c in result_captions if c.get('speaker') == 'ALTERED_CC')
            matched             = len(result_captions) - altered_cc
            matched_user_idxs   = set(idx for idx in row_matches if idx is not None)
            removed             = len(user_captions) - len(matched_user_idxs)

            body = json.dumps({
                "episode_title":   episode_title,
                "user_name":       user_name,
                "youtube_id":      youtube_id,
                "user_uid":        user_uid,
                "episode_uid":     episode_uid,
                "total":           len(result_captions),
                "matched":         matched,
                "altered_cc":      altered_cc,
                "removed":         removed,
                "user_captions":   [
                    {"text": c.get("text", ""), "start": c.get("start", 0), "speaker": c.get("speaker", "")}
                    for c in user_captions
                ],
                "result_captions": [
                    {
                        "text":     c.get("text", ""),
                        "start":    c.get("start", 0),
                        "duration": c.get("duration", 0),
                        "speaker":  c.get("speaker", ""),
                    }
                    for c in result_captions
                ],
                "row_matches": row_matches,
            }, ensure_ascii=False)

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
