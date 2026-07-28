#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt")
text = path.read_text()
old = '''        item {
            RadioSettingRow(
                title = "AF – Alternative Frequenzen",
        item {
            RadioSettingRow(
                title = "GPS-Sendererkennung (RTR)",'''
new = '''        item {
            RadioSettingRow(
                title = "GPS-Sendererkennung (RTR)",'''
if text.count(old) != 1:
    raise SystemExit(f"Expected duplicated AF prefix exactly once, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
print("Corrected PhysicalRadioSettingsPanel item nesting")
