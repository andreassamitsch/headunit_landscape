#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point for Issue #140. The v2 script explicitly selects
# Home, drives Home → Stimmungen & Genres → Browse, identifies a rendered
# PlaylistItem by its real Compose bounds, performs an actual `adb input tap`,
# and requires NavController to reach OnlinePlaylistScreen. Any failure blocks
# the updater release workflow.
exec bash scripts/run_issue_140_browse_playback_emulator_v2.sh
