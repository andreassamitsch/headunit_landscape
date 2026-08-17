#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point. The deterministic v2 test starts the real production
# Dudu7 NavHost on Home through the app's persisted last-tab setting, then drives the
# visible Home → Stimmungen & Genres → Browse → Play path and requires the exact
# clicked title to appear in the upper player pane.
exec bash scripts/run_issue_140_browse_playback_emulator_v2.sh
