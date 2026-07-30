#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

UPSTREAM_COMMIT = "2504604637e8c6ddcc5efbf3894957d6eb2c6b04"
UPSTREAM_ROOT = f"https://raw.githubusercontent.com/MetrolistGroup/Metrolist/{UPSTREAM_COMMIT}"


def download(relative: str) -> str:
    request = Request(f"{UPSTREAM_ROOT}/{relative}", headers={"User-Agent": "Metrolist-dudu7-build"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def write_upstream(relative: str) -> None:
    Path(relative).write_text(download(relative), encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one occurrence in {path}, found {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Use the same known-good auth/player resolution code and current cipher tables as original MetroList.
for relative_path in (
    "app/src/main/assets/player_configs.json",
    "app/src/main/assets/player_dates.json",
    "app/src/main/kotlin/com/metrolist/music/ui/screens/LoginScreen.kt",
    "app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt",
):
    write_upstream(relative_path)

music_service = Path("app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt")
text = music_service.read_text(encoding="utf-8")

custom_error_block = '''        if (error.errorCode == PlaybackException.ERROR_CODE_IO_UNSPECIFIED &&
            currentStreamClient.value == "WEB_REMIX"
        ) {
            Timber.tag(TAG).d("WEB_REMIX IO_UNSPECIFIED detected; forcing another stream client")
            handleAuthenticatedStreamFailure(mediaId)
            return
        }

'''
if text.count(custom_error_block) != 1:
    raise SystemExit("Custom authenticated IO_UNSPECIFIED block not found exactly once")
text = text.replace(custom_error_block, "", 1)

handler_start = '''    /**
     * Handles an authenticated WEB_REMIX stream that failed on the actual ExoPlayer GET with
     * IO_UNSPECIFIED. Unlike the cipher self-heal path this keeps WEB_REMIX disabled for this
     * media id so the retry is guaranteed to use a different client.
     */
    private fun handleAuthenticatedStreamFailure(mediaId: String?) {
'''
next_handler = '''    /**
     * Handles expired URL (403) errors by clearing caches and retrying.
     */
'''
start = text.find(handler_start)
end = text.find(next_handler, start)
if start < 0 or end < 0:
    raise SystemExit("Custom authenticated stream failure handler boundaries not found")
text = text[:start] + text[end:]
music_service.write_text(text, encoding="utf-8")

replace_once("app/build.gradle.kts", "versionCode = 1370041", "versionCode = 1370042")
replace_once("app/build.gradle.kts", 'versionName = "13.7.32"', 'versionName = "13.7.33"')
