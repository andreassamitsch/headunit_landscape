#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point for Issue #140. Keep the large v2 driver as the
# baseline, but make its live-data genre selection deterministic and require
# proof that the physical genre tap traverses the Dudu7 parent touch bridge.
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
anchor = "sleep 15\n\ndump_ui /sdcard/browse.xml \"$ARTIFACTS/browse-page.xml\""
replacement = """sleep 15

# A physical genre tap must have been consumed by the Dudu7 right-pane bridge
# and must have executed the normal youtube_browse navigation callback. This
# catches the real-device failure mode where the child Compose clickable ate the
# touch and the right pane stayed on mood_and_genres.
adb logcat -d -v brief > \"$ARTIFACTS/genre-after-tap-logcat.txt\"
grep -q 'Dudu7MoodGenreTap.*Bridged MoodAndGenres tap' \"$ARTIFACTS/genre-after-tap-logcat.txt\"
grep -q 'Dudu7MoodGenreNavigate.*navigate title=' \"$ARTIFACTS/genre-after-tap-logcat.txt\"

dump_ui /sdcard/browse.xml \"$ARTIFACTS/browse-page.xml\""""
if anchor not in s:
    raise SystemExit('Issue 140 post-genre assertion anchor missing')
s = s.replace(anchor, replacement, 1)
if s == p.read_text():
    raise SystemExit('Issue 140 genre chooser/bridge patch did not apply')
p.write_text(s)
PY
exec bash /tmp/run_issue_140.sh
