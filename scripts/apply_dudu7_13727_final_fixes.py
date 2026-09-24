#!/usr/bin/env python3
from pathlib import Path
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Metrolist-dudu7-updater/13.7.27"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


# 1) Pull the current official Metrolist player signature/config database verbatim.
for filename in ("player_configs.json", "player_dates.json"):
    url = f"https://raw.githubusercontent.com/MetrolistGroup/Metrolist/main/app/src/main/assets/{filename}"
    payload = download(url)
    json.loads(payload)
    write(f"app/src/main/assets/{filename}", payload)

# 2) Version bump.
gradle = read("app/build.gradle.kts")
gradle = replace_once(gradle, "versionCode = 1370035", "versionCode = 1370036", "versionCode")
gradle = replace_once(gradle, 'versionName = "13.7.26"', 'versionName = "13.7.27"', "versionName")
write("app/build.gradle.kts", gradle)

# 3) Persist and restore the last selected Dudu7 right-pane tab.
layout_path = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
layout = read(layout_path)
layout = replace_once(
    layout,
    "private const val VEHICLE_PHYSICAL_RADIO_ROUTE = \"vehicle_physical_radio\"\n",
    "private const val VEHICLE_PHYSICAL_RADIO_ROUTE = \"vehicle_physical_radio\"\n"
    "private const val VEHICLE_PANE_PREFS = \"dudu7_vehicle_pane\"\n"
    "private const val VEHICLE_LAST_TAB_ROUTE = \"last_main_tab_route\"\n",
    "tab preference constants",
)
layout = replace_once(
    layout,
    "    val paneNavController = rememberNavController()\n"
    "    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()\n"
    "    val currentPaneRoute = paneBackStackEntry?.destination?.route\n"
    "    var selectedTab by rememberSaveable { mutableStateOf(VehicleRightPaneTab.QUEUE) }\n"
    "    val context = LocalContext.current\n",
    "    val context = LocalContext.current\n"
    "    val initialTab =\n"
    "        remember(context) {\n"
    "            val storedRoute =\n"
    "                context.getSharedPreferences(VEHICLE_PANE_PREFS, Context.MODE_PRIVATE)\n"
    "                    .getString(VEHICLE_LAST_TAB_ROUTE, null)\n"
    "            VehicleRightPaneTab.entries.firstOrNull { it.route == storedRoute } ?: VehicleRightPaneTab.QUEUE\n"
    "        }\n"
    "    val paneNavController = rememberNavController()\n"
    "    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()\n"
    "    val currentPaneRoute = paneBackStackEntry?.destination?.route\n"
    "    var selectedTab by rememberSaveable { mutableStateOf(initialTab) }\n",
    "initial tab restore",
)
layout = replace_once(
    layout,
    "    LaunchedEffect(selectedTab, orderedTabs.toList()) {\n"
    "        val index = orderedTabs.indexOf(selectedTab)\n"
    "        if (index >= 0) {\n"
    "            tabListState.animateScrollToItem(index)\n"
    "        }\n"
    "    }\n",
    "    LaunchedEffect(selectedTab, orderedTabs.toList()) {\n"
    "        context.getSharedPreferences(VEHICLE_PANE_PREFS, Context.MODE_PRIVATE)\n"
    "            .edit()\n"
    "            .putString(VEHICLE_LAST_TAB_ROUTE, selectedTab.route)\n"
    "            .apply()\n"
    "        val index = orderedTabs.indexOf(selectedTab)\n"
    "        if (index >= 0) {\n"
    "            tabListState.animateScrollToItem(index)\n"
    "        }\n"
    "    }\n",
    "tab persistence",
)
layout = replace_once(
    layout,
    "                                startDestination = VEHICLE_QUEUE_ROUTE,",
    "                                startDestination = initialTab.route,",
    "nav start destination",
)
write(layout_path, layout)

# 4) Make RadioDNS observable and robust across CNAME/SRV alternatives.
resolver_path = "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt"
resolver = read(resolver_path)
resolver = replace_once(
    resolver,
    "import kotlinx.coroutines.withContext\n",
    "import kotlinx.coroutines.withContext\n"
    "import kotlinx.coroutines.flow.MutableStateFlow\n"
    "import kotlinx.coroutines.flow.StateFlow\n"
    "import kotlinx.coroutines.flow.asStateFlow\n",
    "RadioDNS flow imports",
)
resolver = replace_once(
    resolver,
    "    private const val MAX_SI_BYTES = 3_000_000\n",
    "    private const val MAX_SI_BYTES = 3_000_000\n"
    "    private const val MAX_CNAME_DEPTH = 8\n\n"
    "    data class Trace(\n"
    "        val status: String = \"Noch nicht geprüft\",\n"
    "        val lookup: String = \"\",\n"
    "        val cname: String = \"\",\n"
    "        val srv: String = \"\",\n"
    "        val siUrl: String = \"\",\n"
    "        val bearer: String = \"\",\n"
    "        val logoCount: Int = 0,\n"
    "        val error: String = \"\",\n"
    "    )\n\n"
    "    private val _lastTrace = MutableStateFlow(Trace())\n"
    "    val lastTrace: StateFlow<Trace> = _lastTrace.asStateFlow()\n",
    "RadioDNS trace state",
)
old_lookup = '''            val lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org"
            Timber.tag(TAG).d("lookup=%s PI=%s ECC=%s GCC=%s", lookup, piHex, resolvedEcc, gcc)
            val authoritative = dnsAnswers(lookup, 5).firstOrNull()?.trimEnd('.')
            if (authoritative.isNullOrBlank()) {
                Timber.tag(TAG).d("No CNAME for %s", lookup)
                return@withContext emptyList()
            }
            val srv = dnsAnswers("_radioepg._tcp.$authoritative", 33).mapNotNull(::parseSrv).minByOrNull { it.priority }
            if (srv == null) {
                Timber.tag(TAG).d("No RadioEPG SRV for %s", authoritative)
                return@withContext emptyList()
            }
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            Timber.tag(TAG).d("CNAME=%s SRV=%s:%d bearer=%s", authoritative, srv.target, srv.port, bearer)
            serviceInformationUrls(srv).forEach { siUrl ->
                val xml = download(siUrl)
                if (xml == null) {
                    Timber.tag(TAG).d("SPI unavailable %s", siUrl)
                    return@forEach
                }
                val logos = parseServiceInformation(xml, siUrl, bearer)
                if (logos.isNotEmpty()) {
                    Timber.tag(TAG).i("Resolved %d logo(s) for %s via %s", logos.size, bearer, siUrl)
                    return@withContext logos.sortedByDescending { it.ranking }
                }
            }
            Timber.tag(TAG).d("No matching multimedia entry for %s", bearer)
            emptyList()
'''
new_lookup = '''            val lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org"
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            _lastTrace.value = Trace(status = "DNS wird geprüft", lookup = lookup, bearer = bearer)
            Timber.tag(TAG).d("lookup=%s PI=%s ECC=%s GCC=%s", lookup, piHex, resolvedEcc, gcc)
            val authoritative = resolveCnameChain(lookup)
            if (authoritative.isNullOrBlank()) {
                val error = "Kein CNAME für $lookup"
                _lastTrace.value = Trace(status = "Fehlgeschlagen", lookup = lookup, bearer = bearer, error = error)
                Timber.tag(TAG).d(error)
                return@withContext emptyList()
            }
            val srvRecords =
                dnsAnswers("_radioepg._tcp.$authoritative", 33)
                    .mapNotNull(::parseSrv)
                    .sortedWith(compareBy<SrvRecord> { it.priority }.thenByDescending { it.weight })
            if (srvRecords.isEmpty()) {
                val error = "Kein RadioEPG-SRV für $authoritative"
                _lastTrace.value = Trace(status = "Fehlgeschlagen", lookup = lookup, cname = authoritative, bearer = bearer, error = error)
                Timber.tag(TAG).d(error)
                return@withContext emptyList()
            }
            for (srv in srvRecords) {
                val srvText = "${srv.target}:${srv.port} (Prio ${srv.priority}, Gewicht ${srv.weight})"
                Timber.tag(TAG).d("CNAME=%s SRV=%s bearer=%s", authoritative, srvText, bearer)
                for (siUrl in serviceInformationUrls(srv)) {
                    _lastTrace.value = Trace(
                        status = "SI wird geladen",
                        lookup = lookup,
                        cname = authoritative,
                        srv = srvText,
                        siUrl = siUrl,
                        bearer = bearer,
                    )
                    val xml = download(siUrl)
                    if (xml == null) {
                        Timber.tag(TAG).d("SPI unavailable %s", siUrl)
                        continue
                    }
                    val logos = runCatching { parseServiceInformation(xml, siUrl, bearer) }
                        .onFailure { Timber.tag(TAG).w(it, "Invalid SPI XML %s", siUrl) }
                        .getOrDefault(emptyList())
                    if (logos.isNotEmpty()) {
                        _lastTrace.value = Trace(
                            status = "Erfolgreich",
                            lookup = lookup,
                            cname = authoritative,
                            srv = srvText,
                            siUrl = siUrl,
                            bearer = bearer,
                            logoCount = logos.size,
                        )
                        Timber.tag(TAG).i("Resolved %d logo(s) for %s via %s", logos.size, bearer, siUrl)
                        return@withContext logos.sortedByDescending { it.ranking }
                    }
                }
            }
            val error = "SI geladen, aber kein passender Bearer/Logoeintrag"
            _lastTrace.value = Trace(
                status = "Fehlgeschlagen",
                lookup = lookup,
                cname = authoritative,
                srv = srvRecords.joinToString { "${it.target}:${it.port}" },
                bearer = bearer,
                error = error,
            )
            Timber.tag(TAG).d("No matching multimedia entry for %s", bearer)
            emptyList()
'''
resolver = replace_once(resolver, old_lookup, new_lookup, "RadioDNS lookup pipeline")
resolver = replace_once(
    resolver,
    "    private data class SrvRecord(val priority: Int, val port: Int, val target: String)\n",
    "    private data class SrvRecord(val priority: Int, val weight: Int, val port: Int, val target: String)\n\n"
    "    private fun resolveCnameChain(initial: String): String? {\n"
    "        var current = initial.trimEnd('.')\n"
    "        val visited = linkedSetOf<String>()\n"
    "        repeat(MAX_CNAME_DEPTH) {\n"
    "            if (!visited.add(current.lowercase(Locale.ROOT))) return null\n"
    "            val next = dnsAnswers(current, 5).firstOrNull()?.trimEnd('.') ?: return if (current == initial) null else current\n"
    "            current = next\n"
    "        }\n"
    "        return current\n"
    "    }\n",
    "CNAME resolver",
)
resolver = replace_once(
    resolver,
    "            priority = parts[0].toIntOrNull() ?: return null,\n"
    "            port = parts[2].toIntOrNull() ?: return null,\n",
    "            priority = parts[0].toIntOrNull() ?: return null,\n"
    "            weight = parts[1].toIntOrNull() ?: 0,\n"
    "            port = parts[2].toIntOrNull() ?: return null,\n",
    "SRV weight",
)
resolver = replace_once(
    resolver,
    "        val connection = open(url, \"application/xml,text/xml\") ?: return null\n",
    "        val connection = open(url, \"application/xml,text/xml,application/octet-stream;q=0.8,*/*;q=0.2\") ?: return null\n",
    "SPI Accept header",
)
write(resolver_path, resolver)

# 5) Do not let a non-RadioDNS fallback cache suppress a later valid RadioDNS result.
reliable_path = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/ReliableFmStationLogoResolver.kt"
reliable = read(reliable_path)
reliable = replace_once(
    reliable,
    "            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)\n"
    "            if (!force && cacheFresh) return@withContext cached\n",
    "            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)\n"
    "            val cachedSource = prefs.getString(SOURCE_PREFIX + key, \"\").orEmpty()\n"
    "            val cachedIsRadioDns = cachedSource == RadioLogoSource.RADIO_DNS.label\n"
    "            if (!force && cacheFresh && (pi <= 0 || cachedIsRadioDns)) return@withContext cached\n",
    "RadioDNS cache priority",
)
write(reliable_path, reliable)

# 6) Show the end-to-end RadioDNS stage in the in-app FM diagnostics.
diag_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/FmRadioDiagnostics.kt"
diag = read(diag_path)
diag = replace_once(
    diag,
    "    val revision by ReliableFmStationLogoResolver.revisions.collectAsState()\n",
    "    val revision by ReliableFmStationLogoResolver.revisions.collectAsState()\n"
    "    val radioDnsTrace by RadioDnsLogoResolver.lastTrace.collectAsState()\n",
    "diagnostic trace collection",
)
diag = replace_once(
    diag,
    "        Text(\"Bearer: $bearer\", style = MaterialTheme.typography.bodySmall)\n",
    "        Text(\"Bearer: $bearer\", style = MaterialTheme.typography.bodySmall)\n"
    "        Text(\"RadioDNS-Status: ${radioDnsTrace.status}\", style = MaterialTheme.typography.bodySmall)\n"
    "        if (radioDnsTrace.cname.isNotBlank()) Text(\"CNAME: ${radioDnsTrace.cname}\", style = MaterialTheme.typography.bodySmall)\n"
    "        if (radioDnsTrace.srv.isNotBlank()) Text(\"SRV: ${radioDnsTrace.srv}\", style = MaterialTheme.typography.bodySmall)\n"
    "        if (radioDnsTrace.siUrl.isNotBlank()) Text(\"SI: ${radioDnsTrace.siUrl}\", style = MaterialTheme.typography.bodySmall, maxLines = 3)\n"
    "        if (radioDnsTrace.logoCount > 0) Text(\"RadioDNS-Logos: ${radioDnsTrace.logoCount}\", style = MaterialTheme.typography.bodySmall)\n"
    "        if (radioDnsTrace.error.isNotBlank()) Text(\"RadioDNS-Fehler: ${radioDnsTrace.error}\", style = MaterialTheme.typography.bodySmall)\n",
    "diagnostic trace UI",
)
write(diag_path, diag)

# 7) Add focused source-level regression tests for the current requirements.
test_path = ROOT / "app/src/test/kotlin/com/metrolist/music/radio/RadioDnsFormatRegressionTest.kt"
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text(
    '''package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class RadioDnsFormatRegressionTest {
    @Test
    fun heartLondonExampleMatchesOfficialRadioDnsWalkthrough() {
        val frequencyCode = (106.2f * 100f).toInt().toString().padStart(5, '0')
        val pi = "c460"
        val gcc = "${pi.first()}e1"
        assertEquals("10620.c460.ce1.fm.radiodns.org", "$frequencyCode.$pi.$gcc.fm.radiodns.org")
        assertEquals("fm:ce1.c460.10620", "fm:$gcc.$pi.$frequencyCode")
    }
}
''',
    encoding="utf-8",
)

print("Applied Metrolist dudu7 13.7.27 final fixes")
