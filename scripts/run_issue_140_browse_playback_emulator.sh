#!/usr/bin/env bash
set -euxo pipefail

# Keep the workflow entry point stable while the strict emulator validation lives in
# the deterministic v2 script. v2 starts the real production Dudu7 NavHost on Home
# through the app's persisted last-tab setting, then drives visible Home → Genres →
# Browse → Play UI and requires the clicked title to appear in the upper player pane.
exec bash scripts/run_issue_140_browse_playback_emulator_v2.sh
