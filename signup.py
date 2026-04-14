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
from mail import get_admin_email, send_email


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
                    send_email(
                        to      = get_admin_email(),
                        subject = f"New sign-up: {name}",
                        body    = f"**{name}** has signed up.\n\n**Email:** {email}\n**Location:** {location or 'not provided'}",
                    )
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
