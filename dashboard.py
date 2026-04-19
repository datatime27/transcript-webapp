#!/usr/bin/env python3
"""
CGI script — public episode-progress dashboard.

  GET /dashboard.py → anonymised episode progress (no auth required)
    Response: { episodes: [{show_name, season_number, episode_number,
                             has_merged, season_complete,
                             user_count, started_count, complete_count}] }
"""

import json
import os
import sys
import traceback

from db import get_db_connection

status = "200 OK"
body   = ""

try:
    if os.environ.get("REQUEST_METHOD", "GET").upper() != "GET":
        status = "405 Method Not Allowed"
        body   = json.dumps({"error": "GET required"})
    else:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT e.uid, s.name, season.number, e.number,
                          MAX(v_merged.is_merged), season.is_complete,
                          COUNT(DISTINCT ue.user_uid),
                          COUNT(DISTINCT CASE WHEN v.version_number IS NOT NULL THEN ue.user_uid END),
                          COUNT(DISTINCT CASE WHEN ue.is_complete = 1 THEN ue.user_uid END)
                   FROM episodes e
                   JOIN seasons season ON season.uid = e.season_uid
                   JOIN shows s ON s.uid = season.show_uid
                   LEFT JOIN (
                       SELECT ue.* FROM user_episodes ue
                       JOIN users u ON u.uid = ue.user_uid
                       WHERE COALESCE(u.is_admin, 0) = 0 AND COALESCE(u.is_test_account, 0) = 0
                   ) ue ON ue.episode_uid = e.uid
                   LEFT JOIN versions v ON v.episode_uid = e.uid AND v.user_uid = ue.user_uid
                   LEFT JOIN versions v_merged ON v_merged.episode_uid = e.uid AND v_merged.is_merged = 1
                   GROUP BY e.uid, s.name, season.number, e.number, season.is_complete
                   ORDER BY s.name, season.number, e.number"""
            )
            episodes = []
            for row in cur.fetchall():
                episodes.append({
                    "show_name":       row[1],
                    "season_number":   row[2],
                    "episode_number":  row[3],
                    "has_merged":      bool(row[4]),
                    "season_complete": bool(row[5]),
                    "user_count":      row[6],
                    "started_count":   row[7],
                    "complete_count":  row[8],
                })
            body = json.dumps({"episodes": episodes})
        finally:
            conn.close()

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
