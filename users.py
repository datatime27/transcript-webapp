#!/usr/bin/env python3
"""
CGI script — populates DB.
"""

import cgitb
cgitb.enable()
from db import getDBConnection
import MySQLdb
print("Content-Type: text/html\r\n")

conn = getDBConnection()
try:
    cur = conn.cursor()
    cur.execute("SELECT uid, email, name FROM users ORDER BY name")
    rows = cur.fetchall()
finally:
    conn.close()

with open("users.txt", "w", encoding="utf-8") as f:
    for uid, email, name in rows:
        f.write(f"{uid}\t{email}\t{name}\n")

print(f"Written {len(rows)} users to users.txt")
