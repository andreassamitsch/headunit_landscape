from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Missing expected text in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


vehicle = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(
    vehicle,
    '''import java.util.Locale
import kotlin.math.max
''',
    '''import java.util.Locale
import timber.log.Timber
import kotlin.math.max
''',
)
replace_once(
    vehicle,
    '''                val route =
                    bestMatch?.id?.let { "artist/$it" }
                        ?: SearchRoutes.resultRoute(artistName)
                paneNavController.navigate(route) {
''',
    '''                val route =
                    bestMatch?.id?.let { "artist/$it" }
                        ?: SearchRoutes.resultRoute(artistName)
                Timber.tag("Dudu7RadioArtist").d(
                    "Resolved radio artist navigation: %s -> %s (%s)",
                    artistName,
                    bestMatch?.title ?: "search results",
                    bestMatch?.id ?: "no exact artist",
                )
                paneNavController.navigate(route) {
''',
)

test = "scripts/dudu7_webradio_reliability_smoke.sh"
replace_once(
    test,
    '''tap_text "radio artist link" 0 "=Rick Astley"
sleep 12
assert_text "radio artist opened inside right pane" 1 "=Rick Astley"
capture "radio-artist-right-pane"
tap_tab "WebRadio" "=WebRadio"
''',
    '''tap_text "radio artist link" 0 "=Rick Astley"
sleep 12
assert_text "radio artist page loaded inside right pane" 1 "Play All" "Alle wiedergeben"
adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
grep -E 'Resolved radio artist navigation: Rick Astley -> Rick Astley' "$RESULTS_DIR/radio-artist-navigation-log.txt"
echo "PASS: radio artist resolved to Rick Astley and opened inside the right pane"
capture "radio-artist-right-pane"
tap_tab "WebRadio" "=WebRadio"
''',
)

print("WebRadio 13.6.6 artist validation fix applied")
