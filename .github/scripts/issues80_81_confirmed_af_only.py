from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    """                            targetPi = selected.pi,
                            knownFrequencies = listOf(before.frequency) + candidates.map(FmAfCandidate::frequency),
                            result =
""",
    """                            targetPi = selected.pi,
                            result =
""",
    "remove unconfirmed candidate argument",
)

text = replace_once(
    text,
    """        targetRssi: Int,
        targetPi: Int,
        knownFrequencies: List<Float>,
        result: String,
""",
    """        targetRssi: Int,
        targetPi: Int,
        result: String,
""",
    "remove unconfirmed candidate parameter",
)

text = replace_once(
    text,
    """                alternativeFrequencies =
                    normalizeFrequencyList(knownFrequencies + before.frequency)
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
""",
    """                // Only the source frequency is already PI-confirmed at this moment.
                // RTR proposals and rejected measurements must never appear as AF entries.
                alternativeFrequencies =
                    normalizeFrequencyList(listOf(before.frequency))
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
""",
    "commit confirmed alternatives only",
)

old_poll = """        val normalizedAf =
            if (piConfirmedNow || (_state.value.rdsConfirmed && stablePi > 0)) {
                normalizeFrequencyList(runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList()))
                    .filterNot { abs(it - _state.value.frequency) < 0.05f }
            } else {
                emptyList()
            }
        if (normalizedAf.isNotEmpty()) {
            if (normalizedAf == pendingAfFrequencies) {
                pendingAfCount += 1
            } else {
                pendingAfFrequencies = normalizedAf
                pendingAfCount = 1
            }
        }
        val stableAf = if (pendingAfCount >= 2) pendingAfFrequencies else _state.value.alternativeFrequencies

"""
new_poll = """        val identityForPaths = _state.value.currentPreset
        val regionForPaths = currentRegionKey()
        val stationForPaths =
            _state.value.rtrStableId.takeIf {
                it.isNotBlank() &&
                    abs(_state.value.rtrMatchedFrequency - _state.value.frequency) < 0.05f &&
                    _state.value.rtrMatchConfidence >= 60
            }.orEmpty().ifBlank { identityForPaths?.stationId.orEmpty() }
        val confirmedLocalAf =
            if (
                identityForPaths != null &&
                regionForPaths != null &&
                stablePi > 0 &&
                stationForPaths.isNotBlank()
            ) {
                receptionPathStore?.candidatesFor(
                    favouriteId = identityForPaths.id,
                    regionKey = regionForPaths,
                    expectedPi = stablePi,
                    stationId = stationForPaths,
                ).orEmpty()
                    .map(FmReceptionPath::frequency)
                    .filterNot { abs(it - _state.value.frequency) < 0.05f }
            } else {
                emptyList()
            }

"""
text = replace_once(text, old_poll, new_poll, "replace native AF display")
text = replace_once(
    text,
    "                alternativeFrequencies = stableAf,",
    "                alternativeFrequencies = confirmedLocalAf,",
    "use confirmed local AF display",
)

path.write_text(text, encoding="utf-8")
