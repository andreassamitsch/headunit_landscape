from pathlib import Path

path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
text = path.read_text(encoding="utf-8")

launch_start = text.find("    private fun launchAlternativeFrequencyCheck(manual: Boolean) {")
launch_end = text.find("    private suspend fun measureAlternativeFrequency(", launch_start)
if launch_start < 0 or launch_end < 0:
    raise SystemExit("local AF launch block not found")

block = text[launch_start:launch_end]
anchor = """                    return@launch
                }

                Dudu7SyuRadioIpc.resetFrequencyAnchor(
"""
resolved = """                    return@launch
                }
                val activePreset = preset ?: return@launch
                val activeRegionKey = regionKey ?: return@launch

                Dudu7SyuRadioIpc.resetFrequencyAnchor(
"""
if "val activePreset = preset ?: return@launch" not in block:
    if block.count(anchor) != 1:
        raise SystemExit(f"nullable AF context anchor expected once, got {block.count(anchor)}")
    block = block.replace(anchor, resolved, 1)

prefix, marker, tail = block.partition("                val activePreset = preset ?: return@launch")
if not marker:
    raise SystemExit("resolved AF context marker missing")
tail = tail.replace("preset.id", "activePreset.id")
tail = tail.replace("regionKey = regionKey", "regionKey = activeRegionKey")
tail = tail.replace("region=$regionKey", "region=$activeRegionKey")
block = prefix + marker + tail
text = text[:launch_start] + block + text[launch_end:]

native_start = text.find("    private suspend fun tryNativeAfFallback(")
native_end = text.find("    private fun commitAlternativeFrequencySwitch(", native_start)
if native_start >= 0:
    if native_end < 0:
        raise SystemExit("native AF fallback end marker missing")
    text = text[:native_start] + text[native_end:]

path.write_text(text, encoding="utf-8")
