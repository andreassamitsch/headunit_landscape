#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point for Issue #140. Keep the large v2 driver as the
# baseline, but patch its genre chooser deterministically before running it:
# full-width section headers such as "Moods & moments" are not genre cards.
# Prefer the real visible "Chill" card so the test enters BrowseScreen and can
# exercise an actual PlaylistItem touch.
cp scripts/run_issue_140_browse_playback_emulator_v2.sh /tmp/run_issue_140.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/run_issue_140.sh')
s = p.read_text()
s = s.replace(
    "ignored={'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}",
    "ignored={'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf','Mood and Genres','Moods & moments','Genres'}",
    1,
)
s = s.replace(
    "if w < 140 or h < 45 or ya < 1100:\n        continue",
    "if w < 140 or w > 800 or h < 45 or ya < 1100:\n        continue",
    1,
)
s = s.replace(
    "candidates.sort(); ya,xa,xb,yb,text=candidates[0]",
    "candidates.sort(); preferred=next((c for c in candidates if c[4] == 'Chill'), None); ya,xa,xb,yb,text=preferred or candidates[0]",
    1,
)
if s == p.read_text():
    raise SystemExit('Issue 140 genre chooser patch did not apply')
p.write_text(s)
PY
exec bash /tmp/run_issue_140.sh
