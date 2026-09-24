from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
player = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
build = ROOT / "app/build.gradle.kts"
test = ROOT / "app/src/test/kotlin/com/metrolist/music/ui/player/Dudu7PlayerLayoutSelectionTest.kt"

text = player.read_text()

helper_anchor = '''private data class Dudu7FmVisualSnapshot(\n    val active: Boolean = false,\n    val identity: String = "",\n    val artworkUrl: String? = null,\n)\n'''
helper = helper_anchor + '''\ninternal fun shouldUseVehiclePlayerLayout(\n    isDudu7: Boolean,\n    isLandscape: Boolean,\n): Boolean = isDudu7 || isLandscape\n'''
if "internal fun shouldUseVehiclePlayerLayout" not in text:
    if helper_anchor not in text:
        raise SystemExit("Dudu7FmVisualSnapshot anchor not found")
    text = text.replace(helper_anchor, helper, 1)

old_selector = '''        when (LocalConfiguration.current.orientation) {\n            Configuration.ORIENTATION_LANDSCAPE -> {\n'''
new_selector = '''        when {\n            shouldUseVehiclePlayerLayout(\n                isDudu7 = VehicleVariantConfig.isDudu7,\n                isLandscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE,\n            ) -> {\n'''
if old_selector in text:
    text = text.replace(old_selector, new_selector, 1)
elif new_selector not in text:
    raise SystemExit("Player layout selector anchor not found")

player.write_text(text)

build_text = build.read_text()
build_text = build_text.replace("versionCode = 1370074", "versionCode = 1370075", 1)
build_text = build_text.replace('versionName = "13.7.65"', 'versionName = "13.7.66"', 1)
build.write_text(build_text)

test.parent.mkdir(parents=True, exist_ok=True)
test.write_text('''package com.metrolist.music.ui.player\n\nimport org.junit.Assert.assertFalse\nimport org.junit.Assert.assertTrue\nimport org.junit.Test\n\nclass Dudu7PlayerLayoutSelectionTest {\n    @Test\n    fun dudu7AlwaysUsesVehiclePlayerInPortraitAndLandscape() {\n        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = true, isLandscape = false))\n        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = true, isLandscape = true))\n    }\n\n    @Test\n    fun standardVariantKeepsExistingOrientationSelection() {\n        assertFalse(shouldUseVehiclePlayerLayout(isDudu7 = false, isLandscape = false))\n        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = false, isLandscape = true))\n    }\n}\n''')

print("Issue 128 portrait Dudu7 player patch applied")
