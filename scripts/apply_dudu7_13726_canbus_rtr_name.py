#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]

build = root / "app/build.gradle.kts"
text = build.read_text(encoding="utf-8")
text = text.replace("versionCode = 1370034", "versionCode = 1370035", 1)
text = text.replace('versionName = "13.7.25"', 'versionName = "13.7.26"', 1)
if "versionCode = 1370035" not in text or 'versionName = "13.7.26"' not in text:
    raise SystemExit("Version markers not updated")
build.write_text(text, encoding="utf-8")

catalog = root / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmCatalog.kt"
text = catalog.read_text(encoding="utf-8")
old = '''                val program = row.string("rtr_programm").trim()
                if (program.isBlank()) return@mapNotNull null
'''
new = '''                val rawProgram = row.string("rtr_programm").trim()
                if (rawProgram.isBlank()) return@mapNotNull null
                val program = RtrPublicProgramName.resolve(
                    rawProgram = rawProgram,
                    broadcaster = row.string("rtr_veranstalter_name"),
                    coverageName = row.string("rtr_gebiet_name"),
                )
'''
if old not in text:
    raise SystemExit("RTR parser marker not found")
text = text.replace(old, new, 1)
catalog.write_text(text, encoding="utf-8")

repo = root / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"
text = repo.read_text(encoding="utf-8")
text = text.replace('setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.25")', 'setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.26")', 1)
repo.write_text(text, encoding="utf-8")

print("Applied 13.7.26 CAN/FM and RTR public-name integration")
