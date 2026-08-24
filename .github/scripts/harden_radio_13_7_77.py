from pathlib import Path

path = Path('app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt')
text = path.read_text()

old = '''                        rtrRepository?.alternativesForProgram(\n                            stableId = stationId,\n                            currentFrequency = before.frequency,\n                            location = currentPoint,\n                        ).orEmpty()'''
new = '''                        withTimeoutOrNull(6_000) {\n                            rtrRepository?.alternativesForProgram(\n                                stableId = stationId,\n                                currentFrequency = before.frequency,\n                                location = currentPoint,\n                            ).orEmpty()\n                        }.orEmpty()'''
if text.count(old) != 1:
    raise SystemExit(f'alternatives block count={text.count(old)}')
text = text.replace(old, new, 1)

old = '''                    if (selected != null) {\n                        runCatching { fm.tune(selected.frequency) }\n                        delay(220)'''
new = '''                    if (selected != null) {\n                        val tunedSelected = runCatching { fm.tune(selected.frequency) }.getOrDefault(false)\n                        if (!tunedSelected) {\n                            error("AF-Zielfrequenz ${formatFrequency(selected.frequency)} MHz konnte nicht eingestellt werden")\n                        }\n                        delay(220)'''
if text.count(old) != 1:
    raise SystemExit(f'selected tune block count={text.count(old)}')
text = text.replace(old, new, 1)

path.write_text(text)
print('hardened AF timeout and selected tune validation')
