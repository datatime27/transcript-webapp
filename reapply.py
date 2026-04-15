#!/usr/bin/env python3
"""
CGI script — reapply annotations tool (admin only).

  GET /reapply.py?user={admin_uid}&version={version_uid}
    → runs apply_annotations(user_version, new_base)
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
                new_base = json.load(f)
            with open(os.path.join(base, version_filepath), encoding='utf-8') as f:
                user_version = json.load(f)

            result          = apply_annotations(copy.deepcopy(user_version), new_base)
            result_captions = result['captions']
            user_captions   = user_version['captions']

            # Map each result caption back to its user caption index (by start time).
            # ALTERED_CC captions get null — they render as result-only rows, while
            # the displaced user caption at the same start becomes a user-only row.
            user_start_to_idx = {to_float(c['start']): i for i, c in enumerate(user_captions)}
            row_matches = [
                None if c.get('speaker') == 'ALTERED_CC' else user_start_to_idx.get(to_float(c['start']))
                for c in result_captions
            ]

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
