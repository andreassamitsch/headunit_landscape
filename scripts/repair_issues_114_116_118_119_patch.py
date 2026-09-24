from pathlib import Path

path = Path(__file__).with_name("apply_issues_114_116_118_119.py")
text = path.read_text()

helper = '''\ndef replace_range(path, start_marker, end_marker, new):\n    text = path.read_text()\n    start = text.find(start_marker)\n    if start < 0:\n        raise RuntimeError(f'{path}: start marker not found: {start_marker[:120]!r}')\n    end = text.find(end_marker, start)\n    if end < 0:\n        raise RuntimeError(f'{path}: end marker not found: {end_marker[:120]!r}')\n    path.write_text(text[:start] + new + text[end:])\n'''

if "def replace_range(" not in text:
    marker = "    path.write_text(text.replace(old, new, 1))\n"
    if marker not in text:
        raise RuntimeError("replace_once helper marker missing")
    text = text.replace(marker, marker + helper, 1)

old_call = "replace_once(fm, old, new)\n"
new_call = '''replace_range(\n    fm,\n    """                if (orderedPresets.isEmpty()) {""",\n    """            }\n\n            PhysicalRadioSection.SCAN ->""",\n    new,\n)\n'''
if old_call in text:
    text = text.replace(old_call, new_call, 1)
elif new_call not in text:
    raise RuntimeError("FM favourites replacement call marker missing")

path.write_text(text)
print("implementation patch repaired for current FM source")
