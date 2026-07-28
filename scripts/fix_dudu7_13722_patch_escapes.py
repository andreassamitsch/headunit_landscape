#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/apply_dudu7_13722_rtr_gps.py")
text = path.read_text()
old = '''    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{relative}: expected one occurrence, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))'''
new = '''    count = text.count(old)
    if count == 0:
        escaped_old = old.replace("\\t", "\\\\t").replace("\\n", "\\\\n")
        if text.count(escaped_old) == 1:
            old = escaped_old
            new = new.replace("\\t", "\\\\t").replace("\\n", "\\\\n")
            count = 1
    if count != 1:
        raise SystemExit(f"{relative}: expected one occurrence, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))'''
if text.count(old) != 1:
    raise SystemExit("replace_once implementation not found exactly once")
path.write_text(text.replace(old, new, 1))
