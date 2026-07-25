#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected block not found in {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[1]
web_radio = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
old_play_saved = '''    fun playSaved(station: RadioStation) {
        favoriteRequestId += 1L
        val requestId = favoriteRequestId
        favoritePlayJob?.cancel()
        favoritePlayJob =
            scope.launch {
                val now = System.currentTimeMillis()
                val cached = refreshedFavoriteCache[station.uuid]?.takeIf { now - it.first < 5 * 60_000L }?.second
                val looksLikeRadioBrowserEntry =
                    station.country.isNotBlank() ||
                        station.language.isNotBlank() ||
                        station.tags.isNotBlank() ||
                        station.codec.isNotBlank() ||
                        station.bitrate > 0
                val refreshed =
                    cached ?: if (looksLikeRadioBrowserEntry) {
                        withTimeoutOrNull(4_500L) {
                            RadioBrowserClient.refreshStation(station).getOrNull()
                        }
                    } else {
                        null
                    }
                if (requestId != favoriteRequestId) return@launch

                val candidate = refreshed ?: station
                val resolvedUrl =
                    withTimeoutOrNull(4_500L) {
                        RadioBrowserClient.resolveStreamUrl(candidate.streamUrl).getOrNull()
                    } ?: candidate.streamUrl
                if (requestId != favoriteRequestId) return@launch

                val playable = candidate.copy(streamUrl = resolvedUrl)
                refreshedFavoriteCache[station.uuid] = now to playable
                if (playable != station) store.addOrUpdate(playable)

                val orderedSnapshot = orderedSavedStations.toList().ifEmpty { savedStations }
                val effectiveStations = replaceFavoriteStation(orderedSnapshot, playable)
                val startIndex = effectiveStations.indexOfFirst { it.uuid == playable.uuid }.coerceAtLeast(0)
                playerConnection.playQueue(
                    queue =
                        ListQueue(
                            title = "WebRadio",
                            items = effectiveStations.map { it.toMediaItem() },
                            startIndex = startIndex,
                        ),
                    notifyUserSelection = false,
                )
            }
    }
'''
new_play_saved = '''    fun playSaved(station: RadioStation) {
        favoriteRequestId += 1L
        val requestId = favoriteRequestId
        favoritePlayJob?.cancel()

        fun startFavorite(playable: RadioStation) {
            val orderedSnapshot = orderedSavedStations.toList().ifEmpty { savedStations }
            val effectiveStations = replaceFavoriteStation(orderedSnapshot, playable)
            val startIndex = effectiveStations.indexOfFirst { it.uuid == playable.uuid }.coerceAtLeast(0)
            playerConnection.playQueue(
                queue =
                    ListQueue(
                        title = "WebRadio",
                        items = effectiveStations.map { it.toMediaItem() },
                        startIndex = startIndex,
                    ),
                notifyUserSelection = false,
            )
        }

        // A favorite tap is a playback command, not a network-refresh command.
        // Start immediately with the saved URL so rapid taps cannot cancel every
        // request before playQueue() is reached. A cached fresh URL may be used,
        // but the background refresh below never blocks the initial start.
        val now = System.currentTimeMillis()
        val cached = refreshedFavoriteCache[station.uuid]?.takeIf { now - it.first < 5 * 60_000L }?.second
        val initialPlayable = cached ?: station
        startFavorite(initialPlayable)

        favoritePlayJob =
            scope.launch {
                val looksLikeRadioBrowserEntry =
                    station.country.isNotBlank() ||
                        station.language.isNotBlank() ||
                        station.tags.isNotBlank() ||
                        station.codec.isNotBlank() ||
                        station.bitrate > 0
                val refreshed =
                    cached ?: if (looksLikeRadioBrowserEntry) {
                        withTimeoutOrNull(4_500L) {
                            RadioBrowserClient.refreshStation(station).getOrNull()
                        }
                    } else {
                        null
                    }
                if (requestId != favoriteRequestId) return@launch

                val candidate = refreshed ?: station
                val resolvedUrl =
                    withTimeoutOrNull(4_500L) {
                        RadioBrowserClient.resolveStreamUrl(candidate.streamUrl).getOrNull()
                    } ?: candidate.streamUrl
                if (requestId != favoriteRequestId) return@launch

                val playable = candidate.copy(streamUrl = resolvedUrl)
                refreshedFavoriteCache[station.uuid] = System.currentTimeMillis() to playable
                if (playable != station) store.addOrUpdate(playable)

                // Do not interrupt a stream that already became ready. Retry only
                // when the same selected favorite still failed or is still stuck
                // after the refresh/playlist resolution completed.
                if (playable.streamUrl != initialPlayable.streamUrl) {
                    val player = runCatching { playerConnection.player }.getOrNull()
                    val sameStation = player?.currentMediaItem?.mediaId == station.mediaId
                    val needsRetry =
                        sameStation &&
                            (player.playerError != null || player.playbackState != Player.STATE_READY)
                    if (requestId == favoriteRequestId && needsRetry) {
                        startFavorite(playable)
                    }
                }
            }
    }
'''
replace_once(web_radio, old_play_saved, new_play_saved)

smoke = root / "scripts/dudu7_round3_reliability_smoke.sh"
replace_once(
    smoke,
    ' {"uuid":"slow-one","name":"Slow Old Radio","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Rock","codec":"MP3","bitrate":96}\n',
    ' {"uuid":"slow-one","name":"Slow Old Radio","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Rock","codec":"MP3","bitrate":96}\n',
)
old_race = '''# The first UUID refresh intentionally blocks for six seconds. A newer favorite
# selection must win and must still be active after the old request returns.
tap_text "slow old favorite" 1 "=Slow Old Radio"
sleep 1
tap_text "newer favorite two" 1 "=Test Radio Two" "=Stale Radio Two"
sleep 10
assert_text "newer selection survives delayed old request" 0 "=Test Track Two"
assert_station_active "Test Radio Two"
echo "PASS: latest favorite selection wins delayed refresh race"
'''
new_race = '''# The UUID refresh for Slow Old Radio intentionally blocks for six seconds, but
# its already saved stream URL is valid. Playback must start immediately instead
# of waiting for refreshStation()/resolveStreamUrl(). This reproduces the device
# problem where repeated favorite taps cancelled every pending network job.
tap_text "slow favorite starts immediately" 1 "=Slow Old Radio"
sleep 2
assert_text "favorite playback does not wait for refresh" 0 "=Never Gonna Give You Up"
assert_station_active "Slow Old Radio"

# A newer favorite selection must also start immediately and remain selected when
# the old six-second refresh eventually returns.
tap_text "newer favorite two" 1 "=Test Radio Two" "=Stale Radio Two"
sleep 2
assert_text "rapid newer favorite starts immediately" 0 "=Test Track Two"
assert_station_active "Test Radio Two"
sleep 8
assert_text "newer selection survives delayed old refresh" 0 "=Test Track Two"
assert_station_active "Test Radio Two"
echo "PASS: favorite starts immediately and latest selection wins delayed refresh"
'''
replace_once(smoke, old_race, new_race)

print("Applied immediate WebRadio favorite playback fix and deterministic regression")
