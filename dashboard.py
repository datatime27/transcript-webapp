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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
            eastern = ZoneInfo('America/New_York')
            today = datetime.now(eastern).date()

            cur.execute(
                """SELECT ue.episode_uid, DATE(MAX(v.created_at)) AS comp_date
                   FROM user_episodes ue
                   JOIN users u ON u.uid = ue.user_uid
                   JOIN versions v
                        ON v.episode_uid = ue.episode_uid AND v.user_uid = ue.user_uid
                   WHERE ue.is_complete = 1
                     AND COALESCE(u.is_admin, 0) = 0
                     AND COALESCE(u.is_test_account, 0) = 0
                   GROUP BY ue.episode_uid, ue.user_uid"""
            )
            completions = {}
            for row in cur.fetchall():
                ep_uid, comp_date = row
                if comp_date is None:
                    continue
                if hasattr(comp_date, 'date'):
                    comp_date = comp_date.date()
                completions.setdefault(ep_uid, []).append(comp_date)

            cur.execute(
                """SELECT episode_uid, DATE(MIN(created_at)) AS merge_date
                   FROM versions WHERE is_merged = 1
                   GROUP BY episode_uid"""
            )
            merges = {}
            for row in cur.fetchall():
                ep_uid, merge_date = row
                if merge_date is None:
                    continue
                if hasattr(merge_date, 'date'):
                    merge_date = merge_date.date()
                merges[ep_uid] = merge_date

            # (21+4+6) shows * 10 episodes — must match SHOWS in dashboard.html
            GRID_TOTAL = 310
            all_ep_uids = set(completions) | set(merges)
            history = []
            for days_ago in range(27, -1, -1):
                d = today - timedelta(days=days_ago)
                earned = 0.0
                for ep_uid in all_ep_uids:
                    cc = sum(1 for cd in completions.get(ep_uid, []) if cd <= d)
                    hm = ep_uid in merges and merges[ep_uid] <= d
                    if hm or cc >= 3:
                        earned += 1.0
                    elif cc > 0:
                        earned += cc / 3.0
                history.append({'date': d.isoformat(), 'pct': round(earned / GRID_TOTAL * 100, 2)})

            body = json.dumps({"episodes": episodes, "history": history})
        finally:
            conn.close()

except Exception:
    status = "500 Internal Server Error"
    body   = json.dumps({"error": traceback.format_exc()})

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write("Content-Type: application/json\r\n\r\n")
sys.stdout.write(body)
