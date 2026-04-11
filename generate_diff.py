import json
import html

with open('transcripts/rwKYWuVluJc.json', encoding='utf-8') as f:
    old = json.load(f)
with open('transcripts/rwKYWuVluJc-new.json', encoding='utf-8') as f:
    new = json.load(f)

old_caps = old['captions']
new_caps = new['captions']

# Find captions with differing speakers only
diffs = []
for i, (o, n) in enumerate(zip(old_caps, new_caps)):
    if o.get('speaker') != n.get('speaker'):
        diffs.append((i, o, n))

def cell(val, changed):
    h = html.escape(str(val)) if val is not None else ''
    if changed:
        return f'<span class="changed">{h}</span>'
    return h

rows = []
for idx, o, n in diffs:
    text = html.escape(o.get('text', ''))
    old_spk = cell(o.get('speaker', ''), True)
    new_spk = cell(n.get('speaker', ''), True)

    rows.append(f'''
    <tr>
      <td class="idx">{idx}</td>
      <td class="text">{text}</td>
      <td class="spk">{old_spk}</td>
      <td class="spk col-divider">{new_spk}</td>
    </tr>''')

rows_html = ''.join(rows)

html_out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Transcript Diff: rwKYWuVluJc</title>
<style>
  body {{ font-family: monospace; font-size: 13px; background: #1a1a1a; color: #ccc; margin: 0; padding: 16px; }}
  h1 {{ font-size: 15px; color: #eee; margin-bottom: 12px; }}
  .meta {{ color: #888; margin-bottom: 16px; font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
  col.idx {{ width: 50px; }}
  col.text {{ width: 50%; }}
  col.spk {{ width: 20%; }}
  th {{ background: #2a2a2a; color: #aaa; padding: 6px 8px; text-align: left; border-bottom: 2px solid #444; position: sticky; top: 0; z-index: 1; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #2a2a2a; vertical-align: top; }}
  tr:hover td {{ background: #222; }}
  .idx {{ color: #555; text-align: right; }}
  .text {{ color: #bbb; word-break: break-word; }}
  .changed {{ background: #3a2a00; color: #ffcc44; border-radius: 3px; padding: 1px 3px; }}
  .col-divider {{ border-left: 2px solid #444 !important; }}
  .section-old {{ background: #1e1a1a; }}
  .section-new {{ background: #1a1e1a; }}
  th.old {{ color: #f99; }}
  th.new {{ color: #9f9; }}
  .summary {{ color: #888; margin-bottom: 14px; font-size: 12px; }}
</style>
</head>
<body>
<h1>Diff: rwKYWuVluJc.json vs rwKYWuVluJc-new.json</h1>
<p class="summary">{len(diffs)} captions changed out of {len(old_caps)} total</p>
<table>
  <colgroup>
    <col class="idx">
    <col class="text">
    <col class="spk">
    <col class="spk">
  </colgroup>
  <thead>
    <tr>
      <th>#</th>
      <th>Caption text</th>
      <th class="old">speaker (old)</th>
      <th class="new col-divider">speaker (new)</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</body>
</html>
'''

with open('transcript_diff.html', 'w', encoding='utf-8') as f:
    f.write(html_out)

print(f"Written transcript_diff.html ({len(diffs)} diffs)")
