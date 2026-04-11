#!/usr/bin/env python3
"""
CGI script — serves and saves transcript data.

  GET  /transcripts.py?version=xxx → full transcript JSON for that version uid, with speakers injected
  GET  /transcripts.py?user=xxx    → list of {version_id, title, version, episode_uid} for episodes assigned to the user
  POST /transcripts.py             → save a new version of the transcript (body: full JSON)
"""

import json
import os
import sys
import traceback

method = os.environ.get("REQUEST_METHOD", "GET").upper()

# Buffer the response so we can set Status: before Content-Type
status = "200 OK"
body   = ""

try:
    from datetime import datetime, timezone
    from pathlib import Path
    from urllib.parse import parse_qs
    from db import get_episodes_for_user, get_user_name, get_version, insert_version, set_episode_complete, set_wants_more


    def valid_id(uid):
        return uid and all(c.isalnum() or c in "-_" for c in uid)

    def handle_get():
        global status, body
        params      = parse_qs(os.environ.get("QUERY_STRING", ""))
        version_uid = params.get("version", [""])[0]
        user_uid    = params.get("user",    [""])[0]

        # Fetch a specific transcript version by uid, with speakers injected
        if version_uid:
            if not valid_id(version_uid):
                status = "400 Bad Request"
                body   = json.dumps({"error": "Invalid version id"})
                return
            try:
                filepath, speakers = get_version(version_uid)
            except ValueError as e:
                status = "404 Not Found"
                body   = json.dumps({"error": str(e)})
                return
            path = Path(filepath)
            if not path.exists():
                status = "404 Not Found"
                body   = json.dumps({"error": "Transcript file not found on disk"})
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            data["speakers"] = speakers
            body = json.dumps(data, ensure_ascii=False)

        # Fetch the list of episodes assigned to a user
        elif user_uid:
            if not valid_id(user_uid):
                status = "400 Bad Request"
                body   = json.dumps({"error": "Invalid user id"})
                return
            body = json.dumps({
                "name":     get_user_name(user_uid),
                "episodes": get_episodes_for_user(user_uid),
            })

        else:
            status = "400 Bad Request"
            body   = json.dumps({"error": "Missing required parameter: version or user"})


    def handle_post():
        global status, body
        try:
            length = int(os.environ.get("CONTENT_LENGTH", 0))
            raw    = sys.stdin.read(length)
            data   = json.loads(raw)
        except Exception:
            status = "400 Bad Request"
            body   = json.dumps({"error": "Invalid JSON body"})
            return

        video_id    = str(data.get("id",          "") or "").strip()
        user_uid    = str(data.pop("user_uid",    "") or "").strip() or None
        is_complete = bool(data.pop("is_complete", False))
        wants_more  = bool(data.pop("wants_more",  False))
        data.pop("speakers", None)

        if not valid_id(video_id):
            status = "400 Bad Request"
            body   = json.dumps({"error": "Invalid or missing id"})
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        stem      = f"{video_id}_{user_uid}_{timestamp}" if user_uid else f"{video_id}_{timestamp}"
        rel_path  = f"transcripts/{stem}.json"

        Path(rel_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        try:
            new_version = insert_version(video_id, rel_path, user_uid)
            if is_complete and user_uid:
                set_episode_complete(video_id, user_uid)
            if wants_more and user_uid:
                set_wants_more(user_uid, True)
        except ValueError as e:
            status = "404 Not Found"
            body   = json.dumps({"error": str(e)})
            return

        body = json.dumps({"saved": f"{stem}.json", "version": new_version})

    if method == "POST":
        handle_post()
    else:
        handle_get()

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
