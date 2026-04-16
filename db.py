import configparser
import json
import secrets
import string
from pathlib import Path
from zoneinfo import ZoneInfo

_EASTERN = ZoneInfo("America/New_York")

import MySQLdb

_config_path = Path(__file__).parent / "db.ini"

_UID_ALPHABET = string.ascii_lowercase + string.digits


def generate_uid(cur, table, length=8):
    """Generate a unique UID that doesn't already exist in the given table."""
    while True:
        uid = "".join(secrets.choice(_UID_ALPHABET) for _ in range(length))
        cur.execute(f"SELECT 1 FROM {table} WHERE uid = %s", (uid,))
        if not cur.fetchone():
            return uid


def get_db_connection():
    """Open and return a MySQLdb connection using credentials from db.ini."""
    cfg = configparser.ConfigParser()
    cfg.read(_config_path)
    c = cfg["mysql"]
    return MySQLdb.connect(
        host=c["host"],
        user=c["user"],
        passwd=c["password"],
        db=c["database"],
    )


def create_user(email, name=None, is_test_account=None, location=None, is_anonymous=None):
    """
    Create a new user and return their generated uid.

    Args:
        email           : the user's email address (must be unique)
        name            : display name (required if not anonymous)
        is_test_account : optional flag to mark as a test account
        location        : optional location string
        is_anonymous    : optional flag to mark as anonymous
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        uid = generate_uid(cur, "users")
        cur.execute(
            "INSERT INTO users (uid, email, name, is_anonymous, is_test_account, location, wants_more) VALUES (%s, %s, %s, %s, %s, %s, 1)",
            (uid, email, name, is_anonymous, is_test_account, location),
        )
        conn.commit()
        return uid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_test_accounts():
    """Delete all users marked as test accounts, along with their versions and episode assignments."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT uid FROM users WHERE is_test_account = 1")
        uids = [row[0] for row in cur.fetchall()]
        for uid in uids:
            cur.execute("DELETE FROM versions WHERE user_uid = %s", (uid,))
            cur.execute("DELETE FROM user_episodes WHERE user_uid = %s", (uid,))
        if uids:
            cur.execute("DELETE FROM users WHERE is_test_account = 1")
        conn.commit()
        return len(uids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_recent_versions():
    """Return the latest version per user per episode created in the last 24 hours, ordered by most recent first."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.name, u.uid, e.title, s.name, season.number, e.number,
                      v.version_number, v.created_at, v.uid
               FROM versions v
               JOIN users u ON u.uid = v.user_uid
               JOIN episodes e ON e.uid = v.episode_uid
               JOIN seasons season ON season.uid = e.season_uid
               JOIN shows s ON s.uid = season.show_uid
               WHERE v.created_at >= NOW() - INTERVAL 7 DAY
                 AND v.user_uid IS NOT NULL
                 AND v.version_number = (
                   SELECT MAX(v2.version_number) FROM versions v2
                   WHERE v2.episode_uid = v.episode_uid AND v2.user_uid = v.user_uid
                 )
               ORDER BY v.created_at DESC""",
        )
        return [
            {
                "user_name":      row[0],
                "user_uid":       row[1],
                "title":          row[2],
                "show":           row[3],
                "season":         row[4],
                "episode":        row[5],
                "version_number": row[6],
                "created_at":     row[7].replace(tzinfo=_EASTERN).isoformat(),
                "version_uid":    row[8],
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_episodes_with_user_versions():
    """Return all episodes ordered by show/season/episode, each with a list of allocated users.
    version_number is NULL for users who have been allocated but haven't saved their own version yet."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.uid, e.title, e.youtube_id, u.name, u.uid,
                      MAX(v.version_number),
                      SUBSTRING_INDEX(GROUP_CONCAT(v.uid ORDER BY v.version_number DESC), ',', 1),
                      s.name, season.number, e.number, u.is_admin, u.is_test_account,
                      (SELECT MAX(v2.is_merged) FROM versions v2 WHERE v2.episode_uid = e.uid),
                      season.is_complete, ue.is_complete, u.is_anonymous
               FROM episodes e
               JOIN seasons season ON season.uid = e.season_uid
               JOIN shows s ON s.uid = season.show_uid
               LEFT JOIN user_episodes ue ON ue.episode_uid = e.uid
               LEFT JOIN users u ON u.uid = ue.user_uid
               LEFT JOIN versions v ON v.episode_uid = e.uid AND v.user_uid = u.uid
               GROUP BY e.uid, u.uid
               ORDER BY s.name, season.number, e.number, u.name""",
        )
        episodes = {}
        for row in cur.fetchall():
            ep_uid = row[0]
            if ep_uid not in episodes:
                episodes[ep_uid] = {
                    "episode_uid":     ep_uid,
                    "youtube_id":      row[2],
                    "show_name":       row[7],
                    "season_number":   row[8],
                    "episode_number":  row[9],
                    "has_merged":      bool(row[12]),
                    "season_complete": bool(row[13]),
                    "users":           [],
                }
            if row[3] is not None:
                episodes[ep_uid]["users"].append({
                    "user_name":        row[3],
                    "user_uid":         row[4],
                    "version_number":   row[5],  # NULL = allocated but not started
                    "version_uid":      row[6],   # NULL if not started
                    "is_admin":         bool(row[10]),
                    "is_test_account":  bool(row[11]),
                    "is_complete":      bool(row[14]),
                    "is_anonymous":     bool(row[15]),
                })
        for ep in episodes.values():
            ep["users"].sort(key=lambda u: (u["version_uid"] is not None, u["user_name"]))
        return list(episodes.values())
    finally:
        conn.close()


def get_reapply_data(version_uid):
    """Given a version_uid, return everything needed to run apply_annotations:
      (original_filepath, version_filepath, episode_title, user_name, youtube_id, user_uid, episode_uid)
    original_filepath is the null-user (original import) version for the same episode.
    Returns None for any field if not found."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT v.filepath, v.episode_uid, u.name, e.title, e.youtube_id, v.user_uid
               FROM versions v
               JOIN episodes e ON e.uid = v.episode_uid
               LEFT JOIN users u ON u.uid = v.user_uid
               WHERE v.uid = %s""",
            (version_uid,),
        )
        row = cur.fetchone()
        if not row:
            return None, None, None, None, None, None, None
        version_filepath, episode_uid, user_name, episode_title, youtube_id, user_uid = row

        cur.execute(
            "SELECT filepath FROM versions WHERE episode_uid = %s AND user_uid IS NULL ORDER BY version_number LIMIT 1",
            (episode_uid,),
        )
        orig_row = cur.fetchone()
        original_filepath = orig_row[0] if orig_row else None

        return original_filepath, version_filepath, episode_title, user_name, youtube_id, user_uid, episode_uid
    finally:
        conn.close()


def get_user_name(user_uid):
    """Return the display name for a user, or None if not found."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE uid = %s", (user_uid,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_user_episode_count(user_uid):
    """Return the number of episodes assigned to a user."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_episodes WHERE user_uid = %s", (user_uid,))
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_episode_info(episode_uid):
    """Return {show_name, season_number, episode_number, youtube_id} for an episode, or None if not found."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT shows.name, seasons.number, episodes.number, episodes.youtube_id
            FROM episodes
              JOIN seasons ON seasons.uid = episodes.season_uid
              JOIN shows ON shows.uid = seasons.show_uid
            WHERE episodes.uid = %s
            """,
            (episode_uid,),
        )
        row = cur.fetchone()
        return {"show_name": row[0], "season_number": row[1], "episode_number": row[2], "youtube_id": row[3]} if row else None
    finally:
        conn.close()


def get_user_info(user_uid):
    """Return {name, email, location} for a user, or None if not found."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, email, location FROM users WHERE uid = %s", (user_uid,))
        row = cur.fetchone()
        return {"name": row[0], "email": row[1], "location": row[2]} if row else None
    finally:
        conn.close()


def get_all_users():
    """Return all users ordered by name."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.uid, u.email, u.name, u.is_admin, u.is_test_account, u.location,
                   u.wants_more, u.active,
                   COUNT(DISTINCT ue.episode_uid) AS episodes_assigned,
                   COUNT(DISTINCT v.episode_uid)  AS episodes_started
            FROM users u
            LEFT JOIN user_episodes ue ON ue.user_uid = u.uid
            LEFT JOIN versions v ON v.user_uid = u.uid
            GROUP BY u.uid, u.email, u.name, u.is_admin, u.is_test_account, u.location, u.wants_more, u.active
            ORDER BY u.name
            """,
        )
        return [
            {
                "uid":               row[0],
                "email":             row[1],
                "name":              row[2],
                "is_admin":          bool(row[3]),
                "is_test_account":   bool(row[4]),
                "location":          row[5],
                "wants_more":        bool(row[6]),
                "active":            bool(row[7]),
                "episodes_assigned": row[8],
                "episodes_started":  row[9],
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_all_episodes():
    """Return all episodes ordered by show/season/episode, with show and season context."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.uid, e.youtube_id, e.title, s.name, season.number, e.number,
                      season.is_complete
               FROM episodes e
               JOIN seasons season ON season.uid = e.season_uid
               JOIN shows s ON s.uid = season.show_uid
               ORDER BY s.name, season.number, e.number""",
        )
        return [
            {
                "uid":             row[0],
                "youtube_id":      row[1],
                "title":           row[2],
                "show":            row[3],
                "season":          row[4],
                "episode":         row[5],
                "season_complete": bool(row[6]),
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def add_episode_to_user(user_uid, episode_uid):
    """Assign an episode to a user by UID and clear their wants_more flag."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT IGNORE INTO user_episodes (user_uid, episode_uid) VALUES (%s, %s)",
            (user_uid, episode_uid),
        )
        cur.execute("UPDATE users SET wants_more = NULL WHERE uid = %s", (user_uid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def is_admin(user_uid):
    """Return True if the given user has admin privileges."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_admin FROM users WHERE uid = %s", (user_uid,))
        row = cur.fetchone()
        return bool(row and row[0])
    finally:
        conn.close()


def set_season_speakers(show_name, season_number, speakers):
    """Replace all speaker_associations for a season with the given ordered list."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT se.uid FROM seasons se
               JOIN shows sh ON sh.uid = se.show_uid
               WHERE sh.name = %s AND se.number = %s""",
            (show_name, season_number),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No season found: show={show_name!r}, season={season_number}")
        season_uid = row[0]
        cur.execute("DELETE FROM speaker_associations WHERE season_uid = %s", (season_uid,))
        for i, name in enumerate(speakers):
            cur.execute(
                "INSERT INTO speaker_associations (season_uid, name, order_index) VALUES (%s, %s, %s)",
                (season_uid, name, i),
            )
        conn.commit()
        return len(speakers)
    finally:
        conn.close()


def _get_speakers(cur, episode_uid):
    """Return sorted list of speaker names for the season containing the given episode."""
    cur.execute(
        """SELECT sa.name
           FROM speaker_associations sa
           JOIN episodes e ON e.season_uid = sa.season_uid
           WHERE e.uid = %s
           ORDER BY sa.order_index, sa.name""",
        (episode_uid,),
    )
    return [row[0] for row in cur.fetchall()]


def get_speakers_for_episode(episode_uid):
    """Return sorted list of speaker names for the season containing the given episode."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        return _get_speakers(cur, episode_uid)
    finally:
        conn.close()


def get_episodes_for_user(user_uid):
    """
    Return a list of {version_id, title, version, episode_uid} dicts for episodes assigned to the given user.
    'version_id' is the uid of the latest version for each episode.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.title, v.uid, v.version_number, e.uid, ue.is_complete
               FROM episodes e
               JOIN user_episodes ue ON ue.episode_uid = e.uid
               JOIN versions v ON v.uid = COALESCE(
                 (SELECT uid FROM versions WHERE episode_uid = e.uid AND user_uid = ue.user_uid ORDER BY version_number DESC LIMIT 1),
                 (SELECT uid FROM versions WHERE episode_uid = e.uid AND user_uid IS NULL    ORDER BY version_number DESC LIMIT 1)
               )
               JOIN seasons season ON season.uid = e.season_uid
               JOIN shows s ON s.uid = season.show_uid
               WHERE ue.user_uid = %s AND IFNULL(season.is_complete, 0) = 0
               ORDER BY s.name, season.number, e.number""",
            (user_uid,),
        )
        return [
            {"version_id": row[1], "title": row[0], "version": row[2], "episode_uid": row[3], "is_complete": bool(row[4])}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_version(version_uid):
    """Return (filepath, speakers) for the given version uid."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT filepath, episode_uid FROM versions WHERE uid = %s", (version_uid,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No version found with uid: {version_uid}")
        filepath, episode_uid = row
        return filepath, _get_speakers(cur, episode_uid)
    finally:
        conn.close()


def get_mergeable_episodes():
    """
    Return episodes that have at least 2 distinct user versions, ordered by show/season/episode.
    Result: list of {episode_uid, title}.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT e.uid, e.title
               FROM episodes e
               JOIN seasons season ON season.uid = e.season_uid
               JOIN shows s ON s.uid = season.show_uid
               WHERE (
                 SELECT COUNT(DISTINCT user_uid)
                 FROM versions
                 WHERE episode_uid = e.uid AND user_uid IS NOT NULL
               ) >= 2
               ORDER BY s.name, season.number, e.number""",
        )
        return [{"episode_uid": row[0], "title": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def get_user_versions_for_episode(episode_uid):
    """
    Return each user's latest version for the given episode.
    Result: list of {user_name, version_uid, version_number, filepath}, ordered by user name.
    Excludes the original (null user_uid).
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT u.name, v.uid, v.version_number, v.filepath, v.user_uid
               FROM versions v
               JOIN users u ON u.uid = v.user_uid
               JOIN (
                 SELECT user_uid, MAX(version_number) AS max_ver
                 FROM versions
                 WHERE episode_uid = %s AND user_uid IS NOT NULL
                 GROUP BY user_uid
               ) latest ON latest.user_uid = v.user_uid AND latest.max_ver = v.version_number
               WHERE v.episode_uid = %s
               ORDER BY u.name""",
            (episode_uid, episode_uid),
        )
        return [
            {"user_name": row[0], "version_uid": row[1], "version_number": row[2], "filepath": row[3], "user_uid": row[4]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def insert_version(youtube_id, filepath, user_uid, is_merged=None):
    """Insert a version record for the episode with the given YouTube ID."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT uid FROM episodes WHERE youtube_id = %s", (youtube_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No episode found with YouTube ID: {youtube_id}")
        episode_uid = row[0]
        version_uid = generate_uid(cur, "versions")
        # The derived table (AS v) is required because MySQL doesn't allow a subquery
        # to reference the same table being modified (error 1093).
        cur.execute(
            """INSERT INTO versions (uid, episode_uid, version_number, filepath, user_uid, is_merged)
               VALUES (%s, %s,
                 COALESCE((SELECT MAX(v.version_number) FROM (SELECT version_number FROM versions WHERE episode_uid = %s AND user_uid <=> %s) AS v), 0) + 1,
                 %s, %s, %s)""",
            (version_uid, episode_uid, episode_uid, user_uid, filepath, user_uid, is_merged),
        )
        cur.execute("SELECT version_number FROM versions WHERE uid = %s", (version_uid,))
        new_version = cur.fetchone()[0]
        conn.commit()
        return new_version
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_wants_more(user_uid, value):
    """Set the wants_more flag on a user."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET wants_more = %s WHERE uid = %s",
            (1 if value else None, user_uid),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_locations():
    """Return all rows from the locations table with show name and season number."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.location, sh.name, se.number
            FROM locations l
            JOIN seasons se ON se.uid = l.season_uid
            JOIN shows sh ON sh.uid = se.show_uid
            ORDER BY sh.name, se.number, l.location
            """,
        )
        return [
            {"location": row[0], "show_name": row[1], "season_number": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_all_seasons():
    """Return all seasons with their show name, ordered by show then season number."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT se.uid, sh.name, se.number
            FROM seasons se
            JOIN shows sh ON sh.uid = se.show_uid
            ORDER BY sh.name, se.number
            """,
        )
        return [
            {"uid": row[0], "show_name": row[1], "season_number": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_wants_more_suggestions():
    """For each user with wants_more=1, return the best next episode to assign.

    Returns a dict keyed by user_uid. Each value is either:
      {episode_uid, title, youtube_id, assigned_count}  — the suggested episode
      None                                               — nothing available
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("SELECT uid, location FROM users WHERE wants_more = 1")
        users = cur.fetchall()
        if not users:
            return {}

        cur.execute("SELECT location, season_uid FROM locations")
        location_map = {row[0]: row[1] for row in cur.fetchall()}
        us_season_uid = location_map.get("US")

        # Resolve each user's season_uid in Python using the in-memory map
        user_season = {}
        for user_uid, location in users:
            season_uid = (location_map.get(location) if location else None) or us_season_uid
            user_season[user_uid] = season_uid

        # Fetch episodes already assigned to each wants_more user
        user_uids = [u[0] for u in users]
        placeholders_users = ','.join(['%s'] * len(user_uids))
        cur.execute(
            f"SELECT user_uid, episode_uid FROM user_episodes WHERE user_uid IN ({placeholders_users})",
            user_uids,
        )
        assigned = {}
        for user_uid, episode_uid in cur.fetchall():
            assigned.setdefault(user_uid, set()).add(episode_uid)

        # One query for all candidates across distinct season_uids, ordered by fewest assigned
        needed = {s for s in user_season.values() if s}
        candidates_by_season = {}
        if needed:
            placeholders = ','.join(['%s'] * len(needed))
            cur.execute(
                f"""
                SELECT episodes.season_uid, episodes.uid, shows.name, seasons.number, episodes.number, COUNT(users.uid) AS cnt
                FROM episodes
                  JOIN seasons ON seasons.uid = episodes.season_uid
                  JOIN shows ON shows.uid = seasons.show_uid
                  LEFT JOIN user_episodes ue ON ue.episode_uid = episodes.uid
                  LEFT JOIN users ON users.uid = ue.user_uid
                    AND IFNULL(users.is_admin, 0) = 0
                    AND IFNULL(users.is_test_account, 0) = 0
                WHERE episodes.season_uid IN ({placeholders})
                GROUP BY episodes.season_uid, episodes.uid, shows.name, seasons.number, episodes.number
                HAVING cnt < 4
                ORDER BY episodes.season_uid, cnt ASC, episodes.number ASC
                """,
                list(needed),
            )
            for row in cur.fetchall():
                candidates_by_season.setdefault(row[0], []).append({
                    "episode_uid": row[1], "show_name": row[2],
                    "season_number": row[3], "episode_number": row[4],
                })

        result = {}
        for user_uid, season_uid in user_season.items():
            user_assigned = assigned.get(user_uid, set())
            candidates = candidates_by_season.get(season_uid, [])
            result[user_uid] = next(
                (c for c in candidates if c["episode_uid"] not in user_assigned),
                None,
            )
        return result
    finally:
        conn.close()


def set_location_season(location, season_uid):
    """Update the season_uid for a location row."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE locations SET season_uid = %s WHERE location = %s",
            (season_uid, location),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Location not found: {location!r}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_episode_complete(youtube_id, user_uid):
    """Set is_complete = 1 on the user_episodes row for this user and episode."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT uid FROM episodes WHERE youtube_id = %s", (youtube_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"No episode found with YouTube ID: {youtube_id}")
        episode_uid = row[0]
        cur.execute(
            "UPDATE user_episodes SET is_complete = 1 WHERE user_uid = %s AND episode_uid = %s",
            (user_uid, episode_uid),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def populate_transcript(json_path, show_name, season_number, episode_number, user_uid=None):
    """
    Register a transcript JSON file in the database.

    Creates the show, season, and episode rows if they don't already exist,
    then inserts a new version record pointing at the file.

    Args:
        json_path      : path to the transcript JSON file (str or Path)
        show_name      : name of the show, e.g. "Taskmaster UK"
        season_number  : integer season number
        episode_number : integer episode number within the season
        user_uid       : uid of the user saving this version (None for the original)
    """
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    youtube_id    = data.get("id")
    title         = data.get("title")
    published_at  = data.get("publishedAt")
    thumbnail_url = data.get("img")

    # Normalise ISO timestamp → MySQL DATETIME
    if published_at:
        published_at = published_at.replace("T", " ").replace("Z", "")

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # ── show ──────────────────────────────────────────────────────────────
        cur.execute("SELECT uid FROM shows WHERE name = %s", (show_name,))
        row = cur.fetchone()
        if row:
            show_uid = row[0]
        else:
            show_uid = generate_uid(cur, "shows")
            cur.execute("INSERT INTO shows (uid, name) VALUES (%s, %s)", (show_uid, show_name))

        # ── season ────────────────────────────────────────────────────────────
        cur.execute(
            "SELECT uid FROM seasons WHERE show_uid = %s AND number = %s",
            (show_uid, season_number),
        )
        row = cur.fetchone()
        if row:
            season_uid = row[0]
        else:
            season_uid = generate_uid(cur, "seasons")
            cur.execute(
                "INSERT INTO seasons (uid, show_uid, number) VALUES (%s, %s, %s)",
                (season_uid, show_uid, season_number),
            )

        # ── episode ───────────────────────────────────────────────────────────
        cur.execute(
            "SELECT uid FROM episodes WHERE season_uid = %s AND number = %s",
            (season_uid, episode_number),
        )
        row = cur.fetchone()
        if row:
            episode_uid = row[0]
        else:
            episode_uid = generate_uid(cur, "episodes")
            cur.execute(
                """INSERT INTO episodes (uid, season_uid, number, title, youtube_id, published_at, thumbnail_url)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (episode_uid, season_uid, episode_number, title, youtube_id, published_at, thumbnail_url),
            )

        # ── version ───────────────────────────────────────────────────────────
        cur.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM versions WHERE episode_uid = %s",
            (episode_uid,),
        )
        next_version = cur.fetchone()[0] + 1

        version_uid = generate_uid(cur, "versions")
        cur.execute(
            """INSERT INTO versions (uid, episode_uid, version_number, filepath, user_uid)
               VALUES (%s, %s, %s, %s, %s)""",
            (version_uid, episode_uid, next_version, str(json_path), user_uid),
        )

        conn.commit()
        return next_version

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
