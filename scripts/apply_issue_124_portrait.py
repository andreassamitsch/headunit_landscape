from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match in {path}: found {count} for {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))


layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
build = Path("app/build.gradle.kts")

replace_once(
    layout,
    "import android.content.ContextWrapper\n",
    "import android.content.ContextWrapper\nimport android.content.res.Configuration\n",
)
replace_once(
    layout,
    "import androidx.compose.ui.layout.ContentScale\n",
    "import androidx.compose.ui.layout.ContentScale\nimport androidx.compose.ui.layout.Layout\n",
)
replace_once(
    layout,
    "import androidx.compose.ui.platform.LocalContext\n",
    "import androidx.compose.ui.platform.LocalConfiguration\nimport androidx.compose.ui.platform.LocalContext\n",
)
replace_once(
    layout,
    "import androidx.compose.ui.unit.dp\n",
    "import androidx.compose.ui.unit.Constraints\nimport androidx.compose.ui.unit.dp\n",
)
replace_once(
    layout,
    "import kotlin.math.max\n",
    "import kotlin.math.max\nimport kotlin.math.roundToInt\n",
)

helper = '''
@Composable
private fun VehicleAdaptivePaneLayout(
    isPortrait: Boolean,
    playerFraction: Float,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Layout(
        content = content,
        modifier = modifier,
    ) { measurables, constraints ->
        require(measurables.size == 2) {
            "VehicleAdaptivePaneLayout expects exactly player and tab panes"
        }
        val width = constraints.maxWidth
        val height = constraints.maxHeight
        val fraction = playerFraction.coerceIn(0.35f, 0.65f)

        if (isPortrait) {
            val playerHeight = (height * fraction).roundToInt().coerceIn(0, height)
            val contentHeight = height - playerHeight
            val playerPlaceable = measurables[0].measure(Constraints.fixed(width, playerHeight))
            val contentPlaceable = measurables[1].measure(Constraints.fixed(width, contentHeight))
            layout(width, height) {
                playerPlaceable.placeRelative(0, 0)
                contentPlaceable.placeRelative(0, playerHeight)
            }
        } else {
            val playerWidth = (width * fraction).roundToInt().coerceIn(0, width)
            val contentWidth = width - playerWidth
            val playerPlaceable = measurables[0].measure(Constraints.fixed(playerWidth, height))
            val contentPlaceable = measurables[1].measure(Constraints.fixed(contentWidth, height))
            layout(width, height) {
                playerPlaceable.placeRelative(0, 0)
                contentPlaceable.placeRelative(playerWidth, 0)
            }
        }
    }
}

'''
replace_once(
    layout,
    "@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout(",
    helper + "@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout(",
)

replace_once(
    layout,
    "    val safePlayerWeight = 0.5f\n\n    val context = LocalContext.current\n",
    "    val safePlayerWeight = 0.5f\n    val isPortrait = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT\n\n    val context = LocalContext.current\n",
)

old_outer = '''        Row(
            modifier =
                Modifier
                    .windowInsetsPadding(
                        WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                    ).padding(bottom = 8.dp)
                    .fillMaxSize(),
        ) {
'''
new_outer = '''        VehicleAdaptivePaneLayout(
            isPortrait = isPortrait,
            playerFraction = safePlayerWeight,
            modifier =
                Modifier
                    .windowInsetsPadding(
                        WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                    ).padding(bottom = 8.dp)
                    .fillMaxSize(),
        ) {
'''
replace_once(layout, old_outer, new_outer)

replace_once(
    layout,
    "                Modifier\n                    .weight(safePlayerWeight)\n                    .fillMaxSize()",
    "                Modifier\n                    .fillMaxSize()",
)
replace_once(
    layout,
    "                    Modifier\n                        .weight(1f - safePlayerWeight)\n                        .fillMaxSize()",
    "                    Modifier\n                        .fillMaxSize()",
)

replace_once(build, '        versionCode = 1370072\n        versionName = "13.7.63"', '        versionCode = 1370073\n        versionName = "13.7.64"')

print("Issue #124 portrait layout patch applied")
