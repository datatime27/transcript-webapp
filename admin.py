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

import copy
import html as html_module
import json
import os
import re
import sys
import traceback
from pathlib import Path

from urllib.parse import parse_qs
from db import (
    is_admin, get_active_users, get_all_episodes, get_recent_versions,
    get_episodes_with_user_versions, get_all_locations, get_all_seasons,
    get_wants_more_suggestions,
    delete_test_accounts, create_user, populate_transcript, add_episode_to_user,
    get_user_info, get_episode_info, get_user_episode_count,
    set_season_speakers, set_season_complete, set_location_season, update_user_location,
    get_reapply_data, get_user_latency,
)
from annotation_utils import apply_annotations
from mail import send_email


_WELCOME_BODY = """\
Hi {name}!
Thank you so much for volunteering to help out with the Taskmaster transcripts. I have created a web app online for you to use.

**Intro**
My webpage loads the YouTube episode alongside the transcript. I'm already running a process over the transcript to estimate who is speaking. However the process is wrong as often as it is right. That's where you come in.

**Where to begin**
The process I used to estimate speakers doesn't know speaker names, so you'll just see SPEAKER_00, SPEAKER_01, etc.
The first time you change a SPEAKER_ to a real name the tool will ask you if you'd like to swap all other instances of that speaker as well. Be warned sometimes the tool gets the speaker wrong (especially during the intro theme), so check that a given speaker seems correct before switching all of them. In practice I found it's best to start with the prize task. Then each of the 7 speakers gets a turn at speaking, which will give you a better idea of who is who.
There is also the "Other" speaker which is for anything that can't be attributed to one of the 7 speakers: (e.g.: applause, noises, guest speaker)

**Caveats**
My process that annotated the speakers seems to have trouble with people speaking quickly back and forth, so quick banter or the live studio task will require more fixes from you.
Also any transition from one speaker to another will sometimes be off by one caption.
The timecode is MOSTLY in sync with the video, but there are some spots where the timecode information might be off a bit.

**YOUR TASK**
This is your personal link to the tool. Please don't share this with anyone else. I'm creating a different link for each person otherwise this would be impossible to track. Further instructions on how to use the app can be found on the link. Please let me know if you have any issues, comments, improvements for the tool.

**YOUR LINK:** {link}

Your time starts now!
-Peter
"Data Time"
"""


def valid_id(uid):
    return uid and all(c.isalnum() or c in "-_" for c in uid)


def _file_stats(filepath):
    """Return (latest_modification, percent_modified) for a transcript file."""
    if not filepath:
        return None, None
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, filepath), encoding="utf-8") as f:
            data = json.load(f)
        captions = data.get("captions", [])
        total = len(captions)
        last = None
        modified_count = 0
        for c in captions:
            if c.get("modified"):
                last = c
                modified_count += 1
        if last is None:
            latest_mod = None
        else:
            secs = float(str(last["start"]).strip().rstrip("s"))
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            s = int(secs % 60)
            latest_mod = f"{h}:{m:02d}:{s:02d}"
        pct = round(100 * modified_count / total) if total else None
        return latest_mod, pct
    except Exception:
        return None, None


def action_load_data():
    latency = get_user_latency()
    for row in latency[:10]:
        row["latest_modification"], row["percent_modified"] = _file_stats(row.get("latest_filepath"))
    return "200 OK", json.dumps({
        "users":                       get_active_users(),
        "episodes":                    get_all_episodes(),
        "recent_versions":             get_recent_versions(),
        "episodes_with_user_versions": get_episodes_with_user_versions(),
        "locations":                   get_all_locations(),
        "seasons":                     get_all_seasons(),
        "wants_more_suggestions":      get_wants_more_suggestions(),
        "user_latency":                latency,
    }, ensure_ascii=False)


def action_check_altered_cc(compare_text=False):
    episodes = get_episodes_with_user_versions()
    base = os.path.dirname(os.path.abspath(__file__))
    original_cache = {}
    results = {}

    for ep in episodes:
        if ep.get("season_complete"):
            continue
        for u in ep.get("users", []):
            version_uid = u.get("version_uid")
            if not version_uid:
                continue
            original_filepath, version_filepath, *_ = get_reapply_data(version_uid)
            if not original_filepath or not version_filepath:
                continue
            if original_filepath not in original_cache:
                with open(os.path.join(base, original_filepath), encoding="utf-8") as f:
                    original_cache[original_filepath] = json.load(f)
            with open(os.path.join(base, version_filepath), encoding="utf-8") as f:
                user_version = json.load(f)
            result = apply_annotations(copy.deepcopy(user_version), original_cache[original_filepath], compare_text=compare_text)
            altered_cc = sum(1 for c in result["captions"] if c.get("speaker") == "ALTERED_CC")
            if altered_cc > 0:
                results[version_uid] = altered_cc

    return "200 OK", json.dumps(results)


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
                m = re.search(r"Taskmaster\s+Australia.*?(?:Season|Series)\s+(\d+).*?Episode\s+(\d+)", title, re.IGNORECASE)
                if m:
                    show_name, season_number, episode_number = "Taskmaster AU", int(m.group(1)), int(m.group(2))
                else:
                    m = re.search(r"Taskmaster\s+(?:NZ|New\s+Zealand).*?(?:Season|Series)\s+(\d+).*?Episode\s+(\d+)", title, re.IGNORECASE)
                    if m:
                        show_name, season_number, episode_number = "Taskmaster NZ", int(m.group(1)), int(m.group(2))
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
    results.sort(key=lambda r: (r["show_name"] or "", r["season_number"] or 0, r["episode_number"] or 0))
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
    user_uid    = str(data.get("user_uid",    "") or "").strip()
    episode_uid = str(data.get("episode_uid", "") or "").strip()
    if not user_uid or not episode_uid:
        return "400 Bad Request", json.dumps({"error": "user_uid and episode_uid are required"})
    try:
        add_episode_to_user(user_uid, episode_uid)
        user          = get_user_info(user_uid)
        episode       = get_episode_info(episode_uid)
        episode_count = get_user_episode_count(user_uid)
        if user and episode:
            label    = f"{episode['show_name']} S{episode['season_number']}E{episode['episode_number']}"
            base_url = f"https://itsdatatime.com/transcript-webapp/viewer.html?user={user_uid}"
            if episode_count == 1:
                viewer_url = base_url
                send_email(
                    to        = user["email"],
                    subject   = "Taskmaster Transcription Volunteering",
                    body      = _WELCOME_BODY.format(name=user["name"], link=viewer_url),
                    bcc_owner = True,
                )
            else:
                viewer_url = f"{base_url}&episode={episode_uid}"
                send_email(
                    to        = user["email"],
                    subject   = f"Your new episode is ready: {label}",
                    body      = f"Hi {user['name']}!\n\nYour new episode is ready: **{label}**\n\n{viewer_url}",
                    bcc_owner = False,
                )
        return "200 OK", json.dumps({"ok": True})
    except Exception as e:
        return "500 Internal Server Error", json.dumps({"error": str(e)})


def action_set_season_complete(data):
    season_uid  = str(data.get("season_uid",  "") or "").strip()
    is_complete = bool(data.get("is_complete", False))
    if not season_uid:
        return "400 Bad Request", json.dumps({"error": "season_uid is required"})
    try:
        set_season_complete(season_uid, is_complete)
        return "200 OK", json.dumps({"ok": True})
    except ValueError as e:
        return "404 Not Found", json.dumps({"error": str(e)})


def action_set_location_season(data):
    location   = str(data.get("location",   "") or "").strip()
    season_uid = str(data.get("season_uid", "") or "").strip()
    if not location or not season_uid:
        return "400 Bad Request", json.dumps({"error": "location and season_uid are required"})
    try:
        set_location_season(location, season_uid)
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


def action_update_user_location(data):
    user_uid = str(data.get("user_uid", "") or "").strip()
    location = str(data.get("location", "") or "").strip() or None
    if not user_uid:
        return "400 Bad Request", json.dumps({"error": "user_uid is required"})
    try:
        update_user_location(user_uid, location)
        return "200 OK", json.dumps({"ok": True})
    except Exception as e:
        return "500 Internal Server Error", json.dumps({"error": str(e)})


POST_ACTIONS = {
    "delete_test_accounts":   action_delete_test_accounts,
    "create_user":            action_create_user,
    "populate_transcript":    action_populate_transcript,
    "add_episode_to_user":    action_add_episode_to_user,
    "set_season_speakers":    action_set_season_speakers,
    "set_season_complete":    action_set_season_complete,
    "set_location_season":    action_set_location_season,
    "update_user_location":   action_update_user_location,
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
        elif action == "check_altered_cc":
            compare_text = params.get("compare_text", ["0"])[0] == "1"
            status, body = action_check_altered_cc(compare_text=compare_text)
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
