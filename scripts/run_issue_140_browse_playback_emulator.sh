#!/usr/bin/env bash
set -euxo pipefail

# The head unit has no Android gesture/navigation bar covering the Dudu7 lower pane.
# The stock Pixel emulator does; at the end of Home it placed the original
# "Mood and Genres" navigation title at y=1857..1920 underneath that bar. Run the
# validation in immersive fullscreen so its usable geometry matches the head unit.
adb shell settings put global policy_control immersive.full='*' || true

# In immersive mode the last usable pixel is 1920 rather than the old conservative
# 1880 cutoff in v2. Keep product code untouched and adapt only the emulator harness.
sed -i 's/1880/1920/g' scripts/run_issue_140_browse_playback_emulator_v2.sh

# v2 starts the real production Dudu7 NavHost on Home via the persisted last-tab
# preference, then drives visible Home → Mood and Genres → Browse → Play and requires
# the exact clicked title to appear in the upper Dudu7 player pane.
exec bash scripts/run_issue_140_browse_playback_emulator_v2.sh
