#!/usr/bin/env python3
"""
CGI script — merge tool for transcript versions.

  GET  /merge.py?user=xxx             → list of {episode_uid, title} with >= 2 user versions
  GET  /merge.py?episode=xxx&user=xxx → combined JSON of all user versions for the episode
  POST /merge.py?user=xxx             → save a merged transcript version
"""

import json
import os
import sys
import traceback
import unicodedata

method = os.environ.get("REQUEST_METHOD", "GET").upper()

status = "200 OK"
body   = ""

try:
    from datetime import datetime, timezone
    from pathlib import Path
    from urllib.parse import parse_qs
    from db import (get_mergeable_episodes, get_user_versions_for_episode, get_speakers_for_episode,
                    insert_version, get_user_info, get_episode_info,
                    is_admin, get_merge_assignment_episode_uids)
    from mail import get_admin_email, send_email


    _INVISIBLE = dict.fromkeys(range(0x200B, 0x200E), None)  # zero-width chars
    _INVISIBLE[0xFEFF] = None  # BOM
    _INVISIBLE[0x00AD] = None  # soft hyphen

    def _norm_speaker(s):
        if not s:
            return s
        return unicodedata.normalize('NFC', s).translate(_INVISIBLE).strip()

    def valid_id(uid):
        return uid and all(c.isalnum() or c in "-_" for c in uid)


    params   = parse_qs(os.environ.get("QUERY_STRING", ""))
    user_uid = params.get("user", [""])[0]

    if not valid_id(user_uid):
        status = "403 Forbidden"
        body   = json.dumps({"error": "Valid user required"})

    else:
        _is_admin          = is_admin(user_uid)
        _assigned_episodes = None if _is_admin else get_merge_assignment_episode_uids(user_uid)

        if not _is_admin and not _assigned_episodes:
            status = "403 Forbidden"
            body   = json.dumps({"error": "Access denied"})

        else:
            def handle_get():
                global status, body
                episode_uid = params.get("episode", [""])[0]

                # No episode param — return list of episodes eligible for merging
                if not episode_uid:
                    episodes = get_mergeable_episodes()
                    if _assigned_episodes is not None:
                        episodes = [e for e in episodes if e["episode_uid"] in _assigned_episodes]
                    body = json.dumps(episodes)
                    return

                if not valid_id(episode_uid):
                    status = "400 Bad Request"
                    body   = json.dumps({"error": "Invalid episode id"})
                    return

                if _assigned_episodes is not None and episode_uid not in _assigned_episodes:
                    status = "403 Forbidden"
                    body   = json.dumps({"error": "Access denied"})
                    return

                user_versions = get_user_versions_for_episode(episode_uid)
                if not user_versions:
                    status = "404 Not Found"
                    body   = json.dumps({"error": "No user versions found for this episode"})
                    return

                speakers     = [_norm_speaker(s) for s in get_speakers_for_episode(episode_uid)]
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
                    captions = data.get("captions", [])
                    for cap in captions:
                        if cap.get("speaker"):
                            cap["speaker"] = _norm_speaker(cap["speaker"])
                    versions_out.append({
                        "user_name":      uv["user_name"],
                        "user_uid":       uv["user_uid"],
                        "version_uid":    uv["version_uid"],
                        "version_number": uv["version_number"],
                        "captions":       captions,
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

                caption_count = len(captions)
                modified_caps = [c for c in captions if c.get("modified")]
                modified_count = len(modified_caps)
                if modified_caps:
                    last = modified_caps[-1]
                    secs = int(float(str(last["start"]).strip().rstrip("s")))
                    h, rem = divmod(secs, 3600)
                    m, s = divmod(rem, 60)
                    latest_modification = f"{h}:{m:02d}:{s:02d}"
                else:
                    latest_modification = None

                try:
                    new_version = insert_version(youtube_id, rel_path, user_uid, is_merged=True,
                                                 caption_count=caption_count, modified_count=modified_count,
                                                 latest_modification=latest_modification)
                except ValueError as e:
                    status = "404 Not Found"
                    body   = json.dumps({"error": str(e)})
                    return

                try:
                    user_info    = get_user_info(user_uid) or {}
                    user_name    = user_info.get("name") or user_uid
                    ep_info      = get_episode_info(data.get("episode_uid", "")) or {}
                    ep_desc      = f"{ep_info.get('show_name', '')} S{ep_info.get('season_number', '?')}E{ep_info.get('episode_number', '?')}" if ep_info else title
                    send_email(
                        to      = get_admin_email(),
                        subject = f"Merge saved: {title}",
                        body    = f"**{user_name}** saved a merged transcript for **{ep_desc}**.\n\n**Title:** {title}\n**Version:** {new_version}",
                    )
                except Exception:
                    pass

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
