#!/usr/bin/env python3
from pathlib import Path

path = Path('app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt')
text = path.read_text(encoding='utf-8')
old = 'controller.isActive.distinctUntilChanged().collect { active ->'
new = 'controller.isActive.collect { active ->'
if old in text:
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
elif new not in text:
    raise SystemExit('Expected physical FM StateFlow collector not found')
print('Applied StateFlow collector compile fix')
