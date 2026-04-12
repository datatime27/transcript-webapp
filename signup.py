#!/usr/bin/env python3
"""
CGI script — public user sign-up.

  POST /signup.py → create a new user account
    Body (JSON): { email, name, location, is_anonymous }
    Response:    { ok: true } on success, { error } on failure
"""

import json
import os
import sys
import traceback

from db import create_user
from mail import send_email

_WELCOME_SUBJECT = "Taskmaster Transcription Volunteering"

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

**YOUR LINK:** https://itsdatatime.com/transcript-webapp/viewer.html?user={user_id}

Your time starts now!
-Peter
"Data Time"

"""


status = "200 OK"
body   = ""

try:
    method = os.environ.get("REQUEST_METHOD", "GET").upper()

    if method != "POST":
        status = "405 Method Not Allowed"
        body   = json.dumps({"error": "POST required"})
    else:
        try:
            length = int(os.environ.get("CONTENT_LENGTH", 0))
            data   = json.loads(sys.stdin.read(length))
        except Exception:
            status = "400 Bad Request"
            body   = json.dumps({"error": "Invalid JSON body"})
        else:
            email        = str(data.get("email",    "") or "").strip()
            name         = str(data.get("name",     "") or "").strip()
            location     = str(data.get("location", "") or "").strip() or None
            is_anonymous = data.get("is_anonymous") or None

            if not email:
                status = "400 Bad Request"
                body   = json.dumps({"error": "Email is required"})
            elif not name:
                status = "400 Bad Request"
                body   = json.dumps({"error": "Name is required"})
            else:
                try:
                    uid = create_user(email, name, is_test_account=None, location=location, is_anonymous=is_anonymous)
                    send_email(email, _WELCOME_SUBJECT, _WELCOME_BODY.format(name=name, user_id=uid))
                    body = json.dumps({"ok": True})
                except Exception as e:
                    status = "409 Conflict"
                    body   = json.dumps({"error": str(e)})

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
