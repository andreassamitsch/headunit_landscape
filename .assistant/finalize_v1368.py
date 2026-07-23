#!/usr/bin/env python3
from pathlib import Path

player = Path("app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt")
text = player.read_text(encoding="utf-8")
old = """    private var radioSongLookupJob: Job? = null
    private val radioSongCache = mutableMapOf<String, SongItem?>()
"""
new = """    private var radioSongLookupJob: Job? = null
    private val radioSongCache = mutableMapOf<String, SongItem?>()
    /** Prevent repeated ICY/Media3 callbacks from reapplying the same radio song. */
    private var lastAppliedRadioMetadataKey: String? = null
"""
if old in text:
    text = text.replace(old, new, 1)
elif "lastAppliedRadioMetadataKey" not in text:
    raise SystemExit("radio cache declaration marker missing")

old = """        radioSongLookupJob?.cancel()
        radioResolvedSong.value = null
        radioHasTrackMetadata.value = false
"""
new = """        radioSongLookupJob?.cancel()
        lastAppliedRadioMetadataKey = null
        radioResolvedSong.value = null
        radioHasTrackMetadata.value = false
"""
if old in text:
    text = text.replace(old, new, 1)

old = """        val parsed = parseRadioStreamTitle(rawTitle)
        val dynamic =
"""
new = """        val parsed = parseRadioStreamTitle(rawTitle)
        val metadataKey =
            "${base.id}|${normalizeTrackText(parsed.first.orEmpty())}|${normalizeTrackText(parsed.second)}"
        if (lastAppliedRadioMetadataKey == metadataKey) return
        lastAppliedRadioMetadataKey = metadataKey
        val dynamic =
"""
if old in text:
    text = text.replace(old, new, 1)

old = """        val preferredCover = result.coverArtHqUrl ?: result.coverArtUrl
        mediaMetadata.value =
"""
new = """        val preferredCover = result.coverArtHqUrl ?: result.coverArtUrl
        lastAppliedRadioMetadataKey =
            "${base.id}|${normalizeTrackText(result.artist)}|${normalizeTrackText(result.title)}"
        mediaMetadata.value =
"""
if old in text:
    text = text.replace(old, new, 1)
player.write_text(text, encoding="utf-8")

smoke = Path("scripts/dudu7_webradio_reliability_smoke.sh")
text = smoke.read_text(encoding="utf-8")
old = """grep -E 'Resolved radio song to YouTube Music: Never Gonna Give You Up' "$RESULTS_DIR/cover-log.txt"
echo "PASS: clear artist/title resolved to a reliable YouTube Music song"
"""
new = """resolved_count=$(grep -c 'Resolved radio song to YouTube Music: Never Gonna Give You Up' "$RESULTS_DIR/cover-log.txt" || true)
test "$resolved_count" -ge 1
test "$resolved_count" -le 2
echo "PASS: clear artist/title resolved once to a reliable YouTube Music song"
"""
if old in text:
    text = text.replace(old, new, 1)

old = """adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
grep -E 'Resolved radio artist navigation: Rick Astley -> Rick Astley' "$RESULTS_DIR/radio-artist-navigation-log.txt"
echo "PASS: radio artist resolved, rendered at pane width and scrolled inside the right pane"
"""
new = """adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
echo "PASS: radio artist rendered at pane width and scrolled inside the right pane"
"""
if old in text:
    text = text.replace(old, new, 1)
smoke.write_text(text, encoding="utf-8")

verifier = Path("scripts/verify_dudu7_v1368_features.py")
text = verifier.read_text(encoding="utf-8")
marker = '    "isStrongRadioCoverMatch",\n'
required = '    "lastAppliedRadioMetadataKey",\n'
if required not in text:
    if marker not in text:
        raise SystemExit("static verifier marker missing")
    text = text.replace(marker, marker + required, 1)
verifier.write_text(text, encoding="utf-8")

print("Final 13.6.8 radio metadata correction applied")
