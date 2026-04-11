# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

Deploy to a CGI-capable web server. `transcripts.py`, `merge.py`, `admin.py`, and `reapply.py` must be executable. Transcript JSON files go in the `transcripts/` directory. Users are accessed via `viewer.html?user={uid}`. Admins use `merge.html?user={uid}` and `admin.html?user={uid}`.

## Architecture

Single-file frontends (`viewer.html`, `merge.html`, `admin.html`, `reapply.html`) — all HTML, CSS, and JS inline. Python CGI backends (`transcripts.py`, `merge.py`, `admin.py`, `reapply.py`). MySQL database via `db.py`.

**viewer.html flow:**
1. On load, fetches `./transcripts.py?user={uid}` → `{name, episodes: [{version_id, title, version, episode_uid}]}`. Displays username on load screen. Populates load-screen dropdown and in-app episode switcher.
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

- **Episode switcher:** dropdown in the app header; warns on unsaved changes when switching.
- **Speaker labels:** first name only, unless two speakers share a first name (then full name).
- **`applyBracketedNameOverrides()`:** on load, sets speaker from `[FirstName...]` prefix in caption text. Skips captions that are `modified=true` or already have a real speaker name.
- **Keyboard shortcuts:** Space = play/pause, ArrowUp/Down = previous/next caption. Speaker assignment keys and the "previous different speaker" key are all user-configurable via the settings popup (persisted in `localStorage` as `speakerKeys` JSON array and `prevSpeakerKey`). Defaults: `1`–`9` for speakers, `` ` `` for previous different speaker. A slow-motion toggle key is also configurable (`slowMoKey`, default `/`).
- **Clicking caption text or timecode:** seek + play. Clicking speaker button: opens dropdown + pauses.
- **Modified captions:** dark green background, green right border. Active caption: dark red background, red left border.
- **Apply-all toast:** appears bottom-left when a speaker is changed; auto-dismisses after `TOAST_DURATION_MS`; replaces old blocking overlay.
- **Panel splitter:** draggable 5px divider between video and transcript panels; drag shield overlays iframe to prevent event capture; constrained 20–80%.
- **Settings popup:** ⚙ button in header. Three sections: (1) **Scroll delay** — range slider for `SCROLL_DELAY_MS` (persisted in `localStorage`). (2) **Slow motion** — key input (`slowMoKey`, default `/`) and rate slider (`slowMoRate`, default `0.5`, range 0.05–0.95, persisted in `localStorage`); toggling slow motion shows a `{rate}x` badge in the header. (3) **Speaker colors & keys** — each of the 9 speaker slots has a color picker and a key input; there are also key inputs for "Prev. different speaker" (`prevSpeakerKey`) and a single **Reset** button restores all speaker colors and keys to defaults.
- **Speaker colours:** 9 distinct classes (`.speaker-0`–`.speaker-8`); colors driven by CSS custom properties `--sp-color-0` through `--sp-color-8` set by JS on load; `DEFAULT_SPEAKER_COLORS` array holds the fallback values. `.speaker-unknown` and `.speaker-multiple` are fixed grey/italic. `SPEAKERS = [...names, 'Other', 'MULTIPLE']`. The color/key rows are rendered from `SPEAKERS` directly (not derived from `speakerMap`).
- **`renderedSpeakerClasses`:** snapshot object populated during `renderTranscript` mapping speaker name → CSS class. Used by `showSpeakerDropdown` to ensure dropdown item colors exactly match the rendered speaker buttons. Reset in `buildSpeakerMap()`.
- **Animation constants:** all timing literals (`POLL_INTERVAL_MS`, `SCROLL_DELAY_MS`, `SCROLL_DURATION_SLOW`, etc.) are named constants at the top of the script.

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

## admin.html / admin.py

Admin-only tool at `admin.html?user={uid}`. Sections:
- **Recent Versions** — latest version per user per episode in the last 7 days; timestamps stored as Eastern Time in MySQL, sent as ISO with `America/New_York` offset via `zoneinfo`, formatted in the browser via `new Date(...).toLocaleString()`.
- **Episodes** — all episodes with user version tags, grouped by season with `<div class="season-separator">` headings. Started tags link to `reapply.html`; unstarted tags link to `viewer.html?user=...&episode=...`. Admin users and test users are hidden from unstarted tags (only appear once they've saved a version).
- **Users** — scrollable table; per-row "Add Episode" button opens an inline panel; user name links to `viewer.html?user={uid}`. Use `escHtml(JSON.stringify(...))` for inline `onclick` attributes to safely handle special characters.
- **Create User / Populate Transcript** — form panels for admin operations.
- **Season Speakers** — set `speaker_associations` for a show+season via `set_season_speakers` DB function.

`admin.py` GET actions: default (no `action` param) returns `{users, episodes, recent_versions, episodes_with_user_versions}`; `action=scan_transcripts` scans the `transcripts/` directory for `.json` files not yet in the DB (excludes user-version files matching `_[a-z0-9]{8}_\d{14}.json`), reads each file's title (HTML-unescaped), parses show/season/episode via regex, and returns `[{filepath, filename, title, show_name, season_number, episode_number}]`.

`admin.py` POST actions: `delete_test_accounts`, `create_user`, `populate_transcript`, `add_episode_to_user`, `set_season_speakers`. Each action is a module-level function returning `(status, body)`; dispatched via `POST_ACTIONS` dict.

Title parsing in `scan_transcripts`: "Taskmaster Australia..." → show `"Taskmaster AU"`; "Taskmaster [UK] Season N..." → `"Taskmaster UK"`; "Series N, Episode M..." → `"Taskmaster UK"`. Titles from JSON contain HTML entities — always `html.unescape()` before display or regex.

The `ae-episode` select uses `<optgroup>` elements to group episodes by show+season.

## Database

Boolean-like flags use `TINYINT(1) DEFAULT NULL` (not `BOOLEAN`, not `DEFAULT FALSE`). All tables use 8-char alphanumeric UIDs. `versions.uq_version` is `(episode_uid, user_uid, version_number)` — per-user versioning; MySQL allows multiple NULLs so original import versions are not DB-enforced. `speaker_associations` has `order_index INT NOT NULL DEFAULT 0` for custom speaker sort order. Key functions in `db.py`:

- `get_db_connection()` — reads `db.ini` and returns a MySQLdb connection.
- `is_admin(user_uid)` — returns bool; NULL/0 → False. Used by `merge.py` and `admin.py` to gate access.
- `_get_speakers(cur, episode_uid)` / `get_speakers_for_episode(episode_uid)` — returns speaker name list ordered by `order_index, name`.
- `set_season_speakers(show_name, season_number, speakers)` — replaces all speaker_associations for a season (DELETE + INSERT in one connection).
- `populate_transcript()` — registers a JSON file into the DB (get-or-creates show/season/episode, inserts version); stores path relative to `db.py` location.
- `create_user(email, name, is_test_account=None)` — creates a user, prints uid and name (not email).
- `delete_test_accounts()` — deletes versions, user_episodes, then users where `is_test_account=1`; returns count.
- `get_all_users()` / `get_all_episodes()` — return full lists for the admin UI.
- `get_recent_versions()` — latest version per user per episode from the last 7 days; timestamps use `zoneinfo` `America/New_York`.
- `get_episodes_with_user_versions()` — all episodes with `users` list per episode; each user entry includes `is_admin` and `is_test_account`; sorted unstarted-first within each episode.
- `get_user_name(user_uid)` — returns display name or None.
- `add_episode_to_user(email, youtube_id)` — assigns an episode to a user by natural keys.
- `get_episodes_for_user(user_uid)` — returns `[{version_id, title, version, episode_uid}]`, user's own latest version (COALESCE fallback to original), ordered by show/season/episode. Uses alias `s` for `shows` (`show` is a MySQL reserved word).
- `get_version(version_uid)` — returns `(filepath, speakers)` for a version; speakers injected into JSON by `transcripts.py`.
- `get_reapply_data(version_uid)` — returns 7-tuple: `(original_filepath, version_filepath, episode_title, user_name, youtube_id, user_uid, episode_uid)`.
- `get_mergeable_episodes()` — returns `[{episode_uid, title}]` for episodes with ≥2 distinct user versions.
- `get_user_versions_for_episode(episode_uid)` — returns each user's latest version: `[{user_name, user_uid, version_uid, version_number, filepath}]`; excludes null user (original import).
- `insert_version(youtube_id, filepath, user_uid, is_merged=None)` — saves a new version; per-user version numbering via `<=>` null-safe comparison; uses derived table subquery to avoid MySQL error 1093.
