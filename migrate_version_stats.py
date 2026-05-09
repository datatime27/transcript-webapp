#!/usr/bin/env python3
"""
CGI script — backfill caption_count, modified_count, latest_modification (admin only).

  GET /migrate_version_stats.py?user={admin_uid}               → form page (no DB changes)
  GET /migrate_version_stats.py?user={admin_uid}&run=1         → run (last 5)
  GET /migrate_version_stats.py?user={admin_uid}&run=1&limit=N → run (last N)
  GET /migrate_version_stats.py?user={admin_uid}&run=1&all=1   → run all
"""

import html
import json
import os
import sys
import traceback

status  = "200 OK"
content = "text/html; charset=utf-8"
body    = ""

try:
    from urllib.parse import parse_qs
    from db import get_db_connection, is_admin

    def valid_id(uid):
        return uid and all(c.isalnum() or c in "-_" for c in uid)

    def compute_stats(filepath):
        base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, filepath), encoding="utf-8") as f:
            data = json.load(f)
        captions = data.get("captions", [])
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
        return caption_count, modified_count, latest_modification

    def page(title, inner):
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
  body {{ font-family: monospace; background: #1a1a1a; color: #ddd; padding: 2em; }}
  h2 {{ color: #fff; }} h3 {{ color: #ccc; }}
  p.summary {{ color: #8f8; font-size: 1.1em; }}
  a {{ color: #88f; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
  th, td {{ border: 1px solid #444; padding: 6px 10px; text-align: left; }}
  th {{ background: #2a2a2a; color: #aaa; }}
  tr:nth-child(even) {{ background: #222; }}
</style>
</head><body><h2>{html.escape(title)}</h2>{inner}</body></html>"""

    params      = parse_qs(os.environ.get("QUERY_STRING", ""))
    user_uid    = params.get("user",  [""])[0]
    run         = params.get("run",   ["0"])[0] == "1"
    process_all = params.get("all",   ["0"])[0] == "1"
    try:
        limit = int(params.get("limit", ["5"])[0])
    except ValueError:
        limit = 5

    if not valid_id(user_uid) or not is_admin(user_uid):
        status = "403 Forbidden"
        body   = page("403 Forbidden", "<p>Admin access required.</p>")

    elif not run:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM versions WHERE caption_count IS NULL AND user_uid IS NOT NULL")
            pending = cur.fetchone()[0]
        finally:
            conn.close()

        u = html.escape(user_uid)
        body = page("Version Stats Migration", f"""
        <p>{pending} version(s) have NULL stats and are eligible for backfill.</p>
        <ul>
          <li><a href="migrate_version_stats.py?user={u}&run=1&limit=5">Run — last 5</a></li>
          <li><a href="migrate_version_stats.py?user={u}&run=1&limit=20">Run — last 20</a></li>
          <li><a href="migrate_version_stats.py?user={u}&run=1&all=1">Run — all ({pending})</a></li>
        </ul>""")

    else:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            query = """SELECT uid, filepath FROM versions
                       WHERE caption_count IS NULL AND user_uid IS NOT NULL
                       ORDER BY created_at DESC"""
            if not process_all:
                query += f" LIMIT {limit}"
            cur.execute(query)
            rows = cur.fetchall()

            results = []
            errors  = []
            for version_uid, filepath in rows:
                try:
                    caption_count, modified_count, latest_modification = compute_stats(filepath)
                    cur.execute(
                        """UPDATE versions SET caption_count = %s, modified_count = %s, latest_modification = %s
                           WHERE uid = %s""",
                        (caption_count, modified_count, latest_modification, version_uid),
                    )
                    pct = round(100 * modified_count / caption_count) if caption_count else 0
                    results.append((version_uid, filepath, caption_count, modified_count, pct, latest_modification))
                except Exception as e:
                    errors.append((version_uid, filepath, str(e)))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        rows_html = "".join(
            f"<tr><td>{html.escape(uid)}</td>"
            f"<td style='font-size:0.85em;color:#aaa'>{html.escape(fp)}</td>"
            f"<td style='text-align:right'>{cc}</td>"
            f"<td style='text-align:right'>{mc}</td>"
            f"<td style='text-align:right'>{pct}%</td>"
            f"<td style='text-align:right'>{html.escape(lm or '—')}</td></tr>"
            for uid, fp, cc, mc, pct, lm in results
        )
        error_html = ""
        if errors:
            error_rows = "".join(
                f"<tr><td>{html.escape(u)}</td><td>{html.escape(fp)}</td>"
                f"<td style='color:#f88'>{html.escape(e)}</td></tr>"
                for u, fp, e in errors
            )
            error_html = (f"<h3 style='color:#f88'>Errors ({len(errors)})</h3>"
                          f"<table><thead><tr><th>UID</th><th>Filepath</th><th>Error</th></tr></thead>"
                          f"<tbody>{error_rows}</tbody></table>")

        summary = (f"Processed {len(rows)}, updated {len(results)}, errors {len(errors)}."
                   if rows else "No versions with NULL stats found — nothing to do.")
        table_html = (f"<table><thead><tr><th>UID</th><th>Filepath</th><th>Captions</th>"
                      f"<th>Modified</th><th>%</th><th>Last Modified At</th></tr></thead>"
                      f"<tbody>{rows_html}</tbody></table>") if results else ""
        back = f"<p><a href='migrate_version_stats.py?user={html.escape(user_uid)}'>← Back</a></p>"

        body = page("Version Stats Migration",
                    f"<p class='summary'>{html.escape(summary)}</p>{table_html}{error_html}{back}")

except Exception:
    status = "500 Internal Server Error"
    body   = f"<pre>{html.escape(traceback.format_exc())}</pre>"

sys.stdout.write(f"Status: {status}\r\n")
sys.stdout.write(f"Content-Type: {content}\r\n\r\n")
sys.stdout.write(body)
