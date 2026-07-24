#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/dudu7_v1371_regression_smoke.sh")
text = path.read_text(encoding="utf-8")

marker = '''capture "launch"

# Normal playback establishes the left player and a queue for shuffle testing.
'''
block = '''capture "launch"

if [[ "${ARTIST_SCROLL_ONLY:-0}" == "1" ]]; then
    # Deterministic scroll validation: use the local ICY test station instead of
    # depending on a YouTube deep link and external network timing.
    tap_tab "WebRadio" "=WebRadio"
    assert_text "saved section" 1 "=Gespeichert"
    assert_text "station one" 1 "=Test Radio One"
    tap_text "play station one" 1 "=Test Radio One"
    sleep 14
    assert_text "radio title" 0 "=Never Gonna Give You Up"
    assert_text "radio artist" 0 "=Rick Astley"
    tap_text "open artist" 0 "=Rick Astley"
    sleep 15
    assert_text "artist page title" 1 "=Rick Astley"

    adb logcat -c || true
    dump_ui "$RESULTS_DIR/artist-before-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*30/100)) 700
    sleep 4
    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    adb logcat -d -v threadtime > "$RESULTS_DIR/right-pane-scroll-log.txt" || true
    grep -q "Dudu7RightPaneScroll" "$RESULTS_DIR/right-pane-scroll-log.txt"
    capture "artist-after-real-scroll"

    if ! tap_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
        sleep 3
        tap_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
    sleep 10
    assert_text "artist songs detail content" 1 "=Never Gonna Give You Up" "=Together Forever"
    capture "artist-songs-detail"

    adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
    python3 - "$RESULTS_DIR/logcat.txt" "$PACKAGE_NAME" <<'PY'
import re, sys
text=open(sys.argv[1],encoding='utf-8',errors='ignore').read(); package=sys.argv[2]
hits=[line for line in text.splitlines() if 'FATAL EXCEPTION' in line or re.search(r'ANR in '+re.escape(package),line)]
if hits:
    print('\\n'.join(hits)); raise SystemExit(1)
print('PASS: no crash or ANR detected')
PY

    cat > "$RESULTS_DIR/summary.md" <<'EOF'
## Metrolist Dudu7 13.7.1 artist scroll regression

- PASS: local WebRadio station started
- PASS: radio artist page opened in the right pane
- PASS: right-pane bridge received the vertical drag
- PASS: artist content visibly moved after the swipe
- PASS: Top Songs detail navigation opened
- PASS: no crash or ANR detected
EOF
    echo "Dudu7 artist scroll regression passed."
    exit 0
fi

# Normal playback establishes the left player and a queue for shuffle testing.
'''

if "Dudu7 artist scroll regression passed." not in text:
    if marker not in text:
        raise SystemExit("Launch marker for deterministic scroll mode missing")
    text = text.replace(marker, block, 1)

path.write_text(text, encoding="utf-8")
print("Added deterministic artist scroll test mode")
