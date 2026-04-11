#!/usr/bin/env python3
"""
CGI script — admin tool (admin only).

  GET  /admin.py?user=xxx → {users, episodes} for populating the admin UI
  GET  /admin.py?user=xxx&action=scan_transcripts → scan for unregistered transcript files
  POST /admin.py?user=xxx → perform an admin action

  POST actions (JSON body must include "action" field):
    delete_test_accounts
    create_user          — email, name, is_test_account
    populate_transcript  — json_path, show_name, season_number, episode_number
    add_episode_to_user  — email, youtube_id
    set_season_speakers  — show_name, season_number, speakers
"""

import html as html_module
import json
import os
import re
import sys
import traceback
from pathlib import Path

from urllib.parse import parse_qs
from db import (
    is_admin, get_all_users, get_all_episodes, get_recent_versions,
    get_episodes_with_user_versions,
    delete_test_accounts, create_user, populate_transcript, add_episode_to_user,
    set_season_speakers,
)


def valid_id(uid):
    return uid and all(c.isalnum() or c in "-_" for c in uid)


def action_load_data():
    return "200 OK", json.dumps({
        "users":                       get_all_users(),
        "episodes":                    get_all_episodes(),
        "recent_versions":             get_recent_versions(),
        "episodes_with_user_versions": get_episodes_with_user_versions(),
    }, ensure_ascii=False)


def action_scan_transcripts():
    known_ids = {ep["youtube_id"] for ep in get_all_episodes()}
    transcripts_dir = Path(__file__).parent / "transcripts"
    user_version_re = re.compile(r"_[a-z0-9]{8}(_merge)?_\d{14}\.json$")
    results = []
    if transcripts_dir.is_dir():
        for f in sorted(transcripts_dir.iterdir()):
            if f.suffix != ".json":
                continue
            if user_version_re.search(f.name):
                continue
            if f.stem in known_ids:
                continue
            title = None
            show_name = None
            season_number = None
            episode_number = None
            try:
                fdata = json.loads(f.read_text(encoding="utf-8"))
                title = html_module.unescape(fdata.get("title") or "")
                m = re.search(r"Taskmaster\s+Australia.*?Season\s+(\d+).*?Episode\s+(\d+)", title, re.IGNORECASE)
                if m:
                    show_name, season_number, episode_number = "Taskmaster AU", int(m.group(1)), int(m.group(2))
                else:
                    m = re.search(r"Taskmaster(?:\s+UK)?[:\s]+Season\s+(\d+).*?Episode\s+(\d+)", title, re.IGNORECASE)
                    if m:
                        show_name, season_number, episode_number = "Taskmaster UK", int(m.group(1)), int(m.group(2))
                    else:
                        m = re.search(r"Series\s+(\d+).*?Episode\s+(\d+)", title, re.IGNORECASE)
                        if m:
                            show_name, season_number, episode_number = "Taskmaster UK", int(m.group(1)), int(m.group(2))
            except Exception:
                pass
            results.append({
                "filepath":       f"transcripts/{f.name}",
                "filename":       f.name,
                "title":          title,
                "show_name":      show_name,
                "season_number":  season_number,
                "episode_number": episode_number,
            })
    return "200 OK", json.dumps({"results": results})


def action_delete_test_accounts(data):
    count = delete_test_accounts()
    return "200 OK", json.dumps({"deleted": count})


def action_create_user(data):
    email           = str(data.get("email", "") or "").strip()
    name            = str(data.get("name",  "") or "").strip() or None
    location        = str(data.get("location", "") or "").strip() or None
    is_test_account = data.get("is_test_account") or None
    if not email:
        return "400 Bad Request", json.dumps({"error": "email is required"})
    try:
        uid = create_user(email, name, is_test_account, location)
        return "200 OK", json.dumps({"uid": uid})
    except Exception as e:
        return "409 Conflict", json.dumps({"error": str(e)})


def action_populate_transcript(data):
    json_path      = str(data.get("json_path",      "") or "").strip()
    show_name      = str(data.get("show_name",      "") or "").strip()
    season_number  = data.get("season_number")
    episode_number = data.get("episode_number")
    if not json_path or not show_name:
        return "400 Bad Request", json.dumps({"error": "json_path and show_name are required"})
    try:
        season_number  = int(season_number)
        episode_number = int(episode_number)
    except (TypeError, ValueError):
        return "400 Bad Request", json.dumps({"error": "season_number and episode_number must be integers"})
    try:
        version = populate_transcript(json_path, show_name, season_number, episode_number)
        return "200 OK", json.dumps({"version": version})
    except Exception as e:
        return "500 Internal Server Error", json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "cwd": os.getcwd(),
            "listdir": os.listdir(os.getcwd()),
        })


def action_add_episode_to_user(data):
    email      = str(data.get("email",      "") or "").strip()
    youtube_id = str(data.get("youtube_id", "") or "").strip()
    if not email or not youtube_id:
        return "400 Bad Request", json.dumps({"error": "email and youtube_id are required"})
    try:
        add_episode_to_user(email, youtube_id)
        return "200 OK", json.dumps({"ok": True})
    except ValueError as e:
        return "404 Not Found", json.dumps({"error": str(e)})


def action_set_season_speakers(data):
    show_name     = str(data.get("show_name",     "") or "").strip()
    season_number = data.get("season_number")
    speakers      = data.get("speakers", [])
    if not show_name or season_number is None:
        return "400 Bad Request", json.dumps({"error": "show_name and season_number are required"})
    if not isinstance(speakers, list):
        return "400 Bad Request", json.dumps({"error": "speakers must be a list"})
    try:
        season_number = int(season_number)
    except (TypeError, ValueError):
        return "400 Bad Request", json.dumps({"error": "season_number must be an integer"})
    try:
        count = set_season_speakers(show_name, season_number, speakers)
        return "200 OK", json.dumps({"count": count})
    except ValueError as e:
        return "404 Not Found", json.dumps({"error": str(e)})


POST_ACTIONS = {
    "delete_test_accounts": action_delete_test_accounts,
    "create_user":          action_create_user,
    "populate_transcript":  action_populate_transcript,
    "add_episode_to_user":  action_add_episode_to_user,
    "set_season_speakers":  action_set_season_speakers,
}

status = "200 OK"
body   = ""

try:
    params   = parse_qs(os.environ.get("QUERY_STRING", ""))
    user_uid = params.get("user", [""])[0]
    method   = os.environ.get("REQUEST_METHOD", "GET").upper()

    if not valid_id(user_uid) or not is_admin(user_uid):
        status = "403 Forbidden"
        body   = json.dumps({"error": "Admin access required"})

    elif method == "GET":
        action = params.get("action", [""])[0]
        if action == "scan_transcripts":
            status, body = action_scan_transcripts()
        else:
            status, body = action_load_data()

    elif method == "POST":
        try:
            length = int(os.environ.get("CONTENT_LENGTH", 0))
            data   = json.loads(sys.stdin.read(length))
        except Exception:
            status = "400 Bad Request"
            body   = json.dumps({"error": "Invalid JSON body"})
        else:
            action = data.get("action", "")
            if action in POST_ACTIONS:
                status, body = POST_ACTIONS[action](data)
            else:
                status = "400 Bad Request"
                body   = json.dumps({"error": f"Unknown action: {action}"})

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
