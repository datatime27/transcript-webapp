#!/usr/bin/env python3
"""
CGI script — merge tool for transcript versions (admin only).

  GET  /merge.py?user=xxx             → list of {episode_uid, title} with >= 2 user versions
  GET  /merge.py?episode=xxx&user=xxx → combined JSON of all user versions for the episode
  POST /merge.py?user=xxx             → save a merged transcript version
"""

import json
import os
import sys
import traceback

method = os.environ.get("REQUEST_METHOD", "GET").upper()

status = "200 OK"
body   = ""

try:
    from datetime import datetime, timezone
    from pathlib import Path
    from urllib.parse import parse_qs
    from db import is_admin, get_mergeable_episodes, get_user_versions_for_episode, get_speakers_for_episode, insert_version


    def valid_id(uid):
        return uid and all(c.isalnum() or c in "-_" for c in uid)


    params   = parse_qs(os.environ.get("QUERY_STRING", ""))
    user_uid = params.get("user", [""])[0]

    if not valid_id(user_uid) or not is_admin(user_uid):
        status = "403 Forbidden"
        body   = json.dumps({"error": "Admin access required"})

    else:
        def handle_get():
            global status, body
            episode_uid = params.get("episode", [""])[0]

            # No episode param — return list of episodes eligible for merging
            if not episode_uid:
                body = json.dumps(get_mergeable_episodes())
                return

            if not valid_id(episode_uid):
                status = "400 Bad Request"
                body   = json.dumps({"error": "Invalid episode id"})
                return

            user_versions = get_user_versions_for_episode(episode_uid)
            if not user_versions:
                status = "404 Not Found"
                body   = json.dumps({"error": "No user versions found for this episode"})
                return

            speakers     = get_speakers_for_episode(episode_uid)
            versions_out = []
            episode_title = None
            youtube_id    = None

            for uv in user_versions:
                path = Path(uv["filepath"])
                if not path.exists():
                    status = "404 Not Found"
                    body   = json.dumps({"error": f"File not found: {uv['filepath']}"})
                    return
                data = json.loads(path.read_text(encoding="utf-8"))
                if episode_title is None:
                    episode_title = data.get("title")
                    youtube_id    = data.get("id")
                versions_out.append({
                    "user_name":      uv["user_name"],
                    "user_uid":       uv["user_uid"],
                    "version_uid":    uv["version_uid"],
                    "version_number": uv["version_number"],
                    "captions":       data.get("captions", []),
                })

            body = json.dumps({
                "episode_uid": episode_uid,
                "title":       episode_title,
                "youtube_id":  youtube_id,
                "speakers":    speakers,
                "versions":    versions_out,
            }, ensure_ascii=False)


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

            youtube_id = str(data.get("youtube_id", "") or "").strip()
            title      = str(data.get("title",      "") or "").strip()
            captions   = data.get("captions")

            if not valid_id(youtube_id):
                status = "400 Bad Request"
                body   = json.dumps({"error": "Invalid or missing youtube_id"})
                return
            if not isinstance(captions, list):
                status = "400 Bad Request"
                body   = json.dumps({"error": "Missing captions"})
                return

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            stem      = f"{youtube_id}_{user_uid}_merge_{timestamp}"
            rel_path  = f"transcripts/{stem}.json"

            Path(rel_path).write_text(
                json.dumps({"id": youtube_id, "title": title, "captions": captions}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            try:
                new_version = insert_version(youtube_id, rel_path, user_uid, is_merged=True)
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
