# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

Deploy to a CGI-capable web server. `transcripts.py`, `merge.py`, `admin.py`, `reapply.py`, and `signup.py` must be executable. Transcript JSON files go in the `transcripts/` directory. Users are accessed via `viewer.html?user={uid}`. Admins use `merge.html?user={uid}` and `admin.html?user={uid}`. New users register via `signup.html`.

## Architecture

Single-file frontends (`viewer.html`, `merge.html`, `admin.html`, `reapply.html`, `signup.html`) — all HTML, CSS, and JS inline. Python CGI backends (`transcripts.py`, `merge.py`, `admin.py`, `reapply.py`, `signup.py`). MySQL database via `db.py`. Email via `mail.py`.

**viewer.html flow:**
1. On load, fetches `./transcripts.py?user={uid}` → `{name, episodes: [{version_id, title, version, episode_uid, is_complete}]}`. Displays username on load screen. Populates load-screen dropdown and in-app episode switcher.
2. If `?episode={episode_uid}` is in the URL, skips the load screen and auto-loads that episode.
3. User selects an episode and clicks Open. Fetches `./transcripts.py?version={version_id}` for the full JSON.
4. `loadTranscript()` is called: runs `applyBracketedNameOverrides()`, renders the transcript, initialises the YouTube player, and seeks to the last `modified=true` caption without auto-playing.
5. A `setInterval` (interval = `POLL_INTERVAL_MS`) polls `ytPlayer.getCurrentTime()`, binary-searches `captions` to find the active line, highlights it, and auto-scrolls to it.
6. Users can reassign speakers via dropdowns on each caption or group header, or via number keys `1`–`9`. `modified=true` is set on captions whose speaker was changed from a named speaker (not from `SPEAKER_*`).
7. Save POSTs the full JSON to `transcripts.py`, which writes `transcripts/{youtube_id}_{user_uid}_{timestamp}.json` and calls `insert_version()`.

**merge.html flow (admin only):**
1. On load, fetches `./merge.py?user={uid}` (no episode param) → list of `{episode_uid, title}` for episodes with ≥2 user versions.
2. If `?episode={episode_uid}` is in the URL, skips the load screen and auto-compares that episode.
3. On episode select, makes a single fetch to `./merge.py?episode={episode_uid}&user={uid}` — returns all user versions + speakers in one payload.
4. Diff table shows one row per caption (union across all versions, keyed by rounded start-time second). Agreed rows are greyed; disagreed rows are highlighted with per-user clickable speaker cells and `M` badges for `modified=true`. Missing captions show "—"; text conflicts get a "T" badge.
5. User column headers have an `on`/`off` toggle button to exclude a column from conflict detection (column stays visible but dimmed). Conflict/agreement is recomputed live across enabled columns only.
6. Active conflict row highlighted with dark red background + red left border. Prev/Next conflict buttons navigate via `conflictIndices` array. Clicking a speaker cell also activates that row.
7. Default selection: majority vote; ties left unresolved (force a pick). Save button disabled until all conflicts resolved.
8. Save POSTs merged captions to `merge.py`; stored with `is_merged=1` in the DB.

## Key behaviours

- **Episode switcher:** dropdown in the app header; warns on unsaved changes when switching. On every episode load, `loadTranscript` resets the **I'm Done!** button — shows green "Done ✓" (disabled) if `is_complete`, otherwise restores default state.
- **Speaker labels:** first name only, unless two speakers share a first name (then full name).
- **`applyBracketedNameOverrides()`:** on load, sets speaker from `[FirstName...]` prefix in caption text. Skips captions that are `modified=true` or already have a real speaker name.
- **Keyboard shortcuts:** Space = play/pause, ArrowUp/Down = previous/next caption (seeks preserving current play/pause state). Speaker assignment keys and the "previous different speaker" key are all user-configurable via the settings popup (persisted in `localStorage` as `speakerKeys` JSON array and `prevSpeakerKey`). Defaults: `1`–`9` for speakers, `` ` `` for previous different speaker. A slow-motion toggle key is also configurable (`slowMoKey`, default `/`).
- **Clicking caption text or timecode:** seek + play. Double-clicking caption text: enters inline edit mode (pauses video, sets `contentEditable`; Enter or blur commits, Escape reverts). Clicking speaker button: opens dropdown + pauses.
- **Modified captions:** dark green background, green right border. Active caption: dark red background, red left border.
- **Apply-all toast:** appears bottom-left when a speaker is changed; auto-dismisses after `TOAST_DURATION_MS`; replaces old blocking overlay.
- **Panel splitter:** draggable 5px divider between video and transcript panels; drag shield overlays iframe to prevent event capture; constrained 20–80%.
- **Settings popup:** ⚙ button in header. A **Reset all** button at the top resets every setting to its default. Sections: (1) **Scroll/poll sliders** — `SCROLL_DELAY_MS` (default 200), `POLL_INTERVAL_MS` (default 150), `SCROLL_DURATION_NEAR` (default 800, for distances below cutoff), `SCROLL_DURATION_FAR` (default 300, for distances above cutoff), `SCROLL_DISTANCE_CUTOFF` (default 300px); all persisted in `localStorage`; time sliders range 0–3000ms step 50. (2) **Slow motion** — key input (`slowMoKey`, default `/`) and rate slider (`slowMoRate`, default `0.5`, range 0.05–0.95, persisted in `localStorage`); toggling slow motion shows a `{rate}x` badge in the header. (3) **Speaker colors & keys** — each of the 9 speaker slots has a color picker and a key input; key inputs for "Prev. different speaker" (`prevSpeakerKey`).
- **Speaker colours:** 9 distinct classes (`.speaker-0`–`.speaker-8`); colors driven by CSS custom properties `--sp-color-0` through `--sp-color-8` set by JS on load; `DEFAULT_SPEAKER_COLORS` array holds the fallback values. `.speaker-unknown` and `.speaker-multiple` are fixed grey/italic. `SPEAKERS = [...names, 'Other', 'MULTIPLE']`. The color/key rows are rendered from `SPEAKERS` directly (not derived from `speakerMap`).
- **`renderedSpeakerClasses`:** snapshot object populated during `renderTranscript` mapping speaker name → CSS class. Used by `showSpeakerDropdown` to ensure dropdown item colors exactly match the rendered speaker buttons. Reset in `buildSpeakerMap()`.
- **Animation constants:** all timing literals are `let` variables at the top of the script, read from `localStorage` on load (falling back to defaults): `POLL_INTERVAL_MS`, `SCROLL_DELAY_MS`, `SCROLL_DURATION_NEAR`, `SCROLL_DURATION_FAR`, `SCROLL_DISTANCE_CUTOFF`.

## Transcript JSON format

```json
{
  "id": "rwKYWuVluJc",
  "title": "...",
  "captions": [
    { "text": "...", "start": "    0.00s", "duration": 1.335, "speaker": "Alex Horne", "modified": true }
  ]
}
```

- `start` may be a string like `"    0.00s"` or a bare number — always coerce with `String(start)` before calling `.trim()`.
- `speaker` is a full name from the `SPEAKERS` array, a raw `SPEAKER_*` label, or `UNKNOWN`.
- `modified: true` marks captions manually reassigned from a named speaker.

## signup.html / signup.py

Public sign-up page at `signup.html`. Fields: Email (required), Name (required), Country (optional), Remain anonymous checkbox (sets `is_anonymous` flag — the name is always stored but won't be used in credits).

`signup.py` POST: accepts `{email, name, location, is_anonymous}`, calls `create_user()`, then sends an admin notification email via `mail.py`. Returns `{ok: true}` on success or `{error}` on failure. No admin check — publicly accessible.

## annotation_utils.py

`apply_annotations(user_version, new_base)` merges a new base transcript into a user-annotated version. For each caption in `new_base`: exact start+duration match → leave unchanged; start match but different duration → replace with new_base caption and set `speaker='ALTERED_CC'`; start not present → insert in start-time order with `speaker='ALTERED_CC'`. Used by `reapply.py`.

**`SPEAKER_RENAMES` dict** (top of file): maps old speaker name strings to corrected ones. Applied globally to all captions at the end of `apply_annotations`. Add entries here to fix misspelled or variant speaker names across all processed transcripts.

## mail.py

Gmail SMTP helper. Credentials read from `[mail]` section of `db.ini` (`host`, `port`, `user`, `password`, `name`). `send_email(to, subject, body)` sends a `multipart/alternative` email with plain-text and HTML parts; always Bccs the admin email. The HTML part is generated by a simple markdown converter supporting `**bold**`, auto-linked URLs, and paragraph breaks. `get_admin_email()` returns the admin address from `db.ini`.

## admin.html / admin.py

Admin-only tool at `admin.html?user={uid}`. Sections:
- **Recent Versions** — latest version per user per episode in the last 7 days; timestamps stored as Eastern Time in MySQL, sent as ISO with `America/New_York` offset via `zoneinfo`, formatted in the browser via `new Date(...).toLocaleString()`.
- **Episodes** — all episodes with user version tags, grouped by season with `<div class="season-separator">` headings. Started tags link to `reapply.html`; unstarted tags link to `viewer.html?user=...&episode=...`. Admin users and test users are hidden from unstarted tags (only appear once they've saved a version).
- **Users** — scrollable table with a total user count next to the heading and a **Copy TSV** button that copies all user data to the clipboard (Name, Email, Location, Episodes Assigned, Episodes Started, Wants More, Joined, UID). Per-row "Add Episode" button opens an inline panel; user name links to `viewer.html?user={uid}`. Use `escHtml(JSON.stringify(...))` for inline `onclick` attributes to safely handle special characters. Columns: Name, Email, **Location** (double-click to edit inline; POSTs `update_user_location`), **Episodes Assigned** (count of `user_episodes` rows), **Episodes Started** (count of distinct episodes with a saved version), Ready for Next Episode, **Joined** (`created_at` formatted via `toLocaleDateString()`), Link. The **Ready for Next** column shows a suggested episode button for users with `wants_more=1`; clicking it calls `add_episode_to_user` and emails the user.
- **Locations** — table of location→season mappings; each row has a season select that auto-saves on change.
- **Season Speakers** — set `speaker_associations` for a show+season via `set_season_speakers` DB function.
- **Create User / Populate Transcript** — form panels for admin operations.

`admin.py` GET actions: default (no `action` param) returns `{users, episodes, recent_versions, episodes_with_user_versions, locations, seasons, wants_more_suggestions}`; `action=scan_transcripts` scans the `transcripts/` directory for `.json` files not yet in the DB (excludes user-version files matching `_[a-z0-9]{8}_\d{14}.json`), reads each file's title (HTML-unescaped), parses show/season/episode via regex, and returns `[{filepath, filename, title, show_name, season_number, episode_number}]` sorted by show/season/episode.

`admin.py` POST actions: `delete_test_accounts`, `create_user`, `populate_transcript`, `add_episode_to_user`, `set_season_speakers`, `set_location_season`, `update_user_location`. Each action is a module-level function returning `(status, body)`; dispatched via `POST_ACTIONS` dict.

`add_episode_to_user` POST action: accepts `{user_uid, episode_uid}`. After assigning, emails the user — welcome email (with uppercased name) if it's their first episode, otherwise a "new episode ready" email with a direct link. The welcome email uses `viewer.html?user={uid}` (no episode param); subsequent emails use `viewer.html?user={uid}&episode={episode_uid}`.

Title parsing in `scan_transcripts`: "Taskmaster Australia Series/Season N, Episode M..." → show `"Taskmaster AU"` (matches either "Series" or "Season"); "Taskmaster [UK] Season N..." → `"Taskmaster UK"`; "Series N, Episode M..." → `"Taskmaster UK"`. If no pattern matches, the file is still returned with `show_name`, `season_number`, `episode_number` as `null`. Titles from JSON contain HTML entities — always `html.unescape()` before display or regex.

The `ae-episode` select uses `<optgroup>` elements to group episodes by show+season; option values are `episode.uid`.

## viewer.html load screen

The load screen has an **Open** button and an **"I'm ready for a new episode"** button. Clicking the latter POSTs `{action: "wants_more", user_uid}` to `transcripts.py`, which sets `wants_more=1` on the user and emails the admin. On success the button is replaced with "You will receive an email when your new episode is ready".

## locations table

Maps a location string to a season. Schema: `location VARCHAR(255) PRIMARY KEY`, `season_uid VARCHAR(8) FK → seasons`. Used by `get_wants_more_suggestions()` to determine which season to suggest episodes from for each user. Falls back to `location='US'` if the user's location has no entry.

## Database

Boolean-like flags use `TINYINT(1) DEFAULT NULL` (not `BOOLEAN`, not `DEFAULT FALSE`). All tables use 8-char alphanumeric UIDs. `versions.uq_version` is `(episode_uid, user_uid, version_number)` — per-user versioning; MySQL allows multiple NULLs so original import versions are not DB-enforced. `speaker_associations` has `order_index INT NOT NULL DEFAULT 0` for custom speaker sort order. `users.name` is NOT NULL; `users.created_at` defaults to `CURRENT_TIMESTAMP`; `users.is_anonymous` is a separate flag from the name; `users.wants_more` is set to `1` on `create_user` and cleared when an episode is assigned; `users.active` is `TINYINT(1) NOT NULL DEFAULT 1` (exception to the nullable flag convention). Key functions in `db.py`:

- `get_db_connection()` — reads `[mysql]` section of `db.ini` and returns a MySQLdb connection.
- `is_admin(user_uid)` — returns bool; NULL/0 → False. Used by `merge.py` and `admin.py` to gate access.
- `_get_speakers(cur, episode_uid)` / `get_speakers_for_episode(episode_uid)` — returns speaker name list ordered by `order_index, name`.
- `set_season_speakers(show_name, season_number, speakers)` — replaces all speaker_associations for a season (DELETE + INSERT in one connection).
- `populate_transcript()` — registers a JSON file into the DB (get-or-creates show/season/episode, inserts version); stores path relative to `db.py` location.
- `create_user(email, name, is_test_account=None, location=None, is_anonymous=None)` — creates a user with `wants_more=1` and returns uid. `name` is required (NOT NULL). `is_anonymous` stored separately from name.
- `delete_test_accounts()` — deletes versions, user_episodes, then users where `is_test_account=1`; returns count.
- `get_all_users()` — returns full user list including `wants_more`, `active`, `episodes_assigned` (COUNT DISTINCT from `user_episodes`), `episodes_started` (COUNT DISTINCT episode_uid from `versions`), and `created_at` (ISO string with `America/New_York` offset) via a single query with two LEFT JOINs.
- `get_all_episodes()` — returns full episode list including `uid` field.
- `get_recent_versions()` — latest version per user per episode from the last 7 days; timestamps use `zoneinfo` `America/New_York`.
- `get_episodes_with_user_versions()` — all episodes with `users` list per episode; each user entry includes `is_admin` and `is_test_account`; sorted unstarted-first within each episode.
- `get_user_name(user_uid)` — returns display name or None.
- `get_user_info(user_uid)` — returns `{name, email, location}` or None.
- `get_episode_info(episode_uid)` — returns `{show_name, season_number, episode_number, youtube_id}` or None.
- `get_user_episode_count(user_uid)` — returns number of episodes assigned to a user.
- `add_episode_to_user(user_uid, episode_uid)` — inserts into `user_episodes` and clears `wants_more`.
- `get_all_locations()` — returns `[{location, show_name, season_number}]` joined with seasons/shows.
- `get_all_seasons()` — returns `[{uid, show_name, season_number}]`.
- `set_location_season(location, season_uid)` — updates the season for a location row.
- `get_wants_more_suggestions()` — for each user with `wants_more=1`, returns the best unassigned episode from their season (via locations table, US fallback). Excludes episodes assigned to admin/test users from the count. Returns `{user_uid: {episode_uid, show_name, season_number, episode_number} | None}`. Uses 4 queries total regardless of user count.
- `update_user_location(user_uid, location)` — sets `location` on a user (pass `None` to clear).
- `set_wants_more(user_uid, value)` — sets `wants_more=1` or `NULL`.
- `get_episodes_for_user(user_uid)` — returns `[{version_id, title, version, episode_uid, is_complete}]`, user's own latest version (COALESCE fallback to original), ordered by show/season/episode. Uses alias `s` for `shows` (`show` is a MySQL reserved word).
- `get_version(version_uid)` — returns `(filepath, speakers)` for a version; speakers injected into JSON by `transcripts.py`.
- `get_reapply_data(version_uid)` — returns 7-tuple: `(original_filepath, version_filepath, episode_title, user_name, youtube_id, user_uid, episode_uid)`.
- `get_mergeable_episodes()` — returns `[{episode_uid, title}]` for episodes with ≥2 distinct user versions.
- `get_user_versions_for_episode(episode_uid)` — returns each user's latest version: `[{user_name, user_uid, version_uid, version_number, filepath}]`; excludes null user (original import).
- `insert_version(youtube_id, filepath, user_uid, is_merged=None)` — saves a new version; per-user version numbering via `<=>` null-safe comparison; uses derived table subquery to avoid MySQL error 1093.
