from pathlib import Path

path = Path('app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt')
text = path.read_text(encoding='utf-8')
old = '''        val allFrequencies = normalizeFrequencyList(
            presetFrequencies(current) +
                if (rdsCompatible) snapshot.alternativeFrequencies else emptyList() +
                if (rtrCompatible) snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency) else emptyList() +
                if (exactIndex >= 0) listOf(snapshot.frequency) else emptyList(),
        )'''
new = '''        val allFrequencies = normalizeFrequencyList(
            presetFrequencies(current) +
                (if (rdsCompatible) snapshot.alternativeFrequencies else emptyList()) +
                (if (rtrCompatible) snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency) else emptyList()) +
                (if (exactIndex >= 0) listOf(snapshot.frequency) else emptyList()),
        )'''
if text.count(old) != 1:
    raise SystemExit(f'expected one frequency precedence block, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Fixed Kotlin list precedence')
