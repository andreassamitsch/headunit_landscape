package com.metrolist.music.radio.fyt

import java.text.Normalizer
import java.util.Locale
import kotlin.math.roundToInt

data class FmResolvedStationIdentity(
    val stableId: String,
    val canonicalName: String,
    val recognized: Boolean,
    val source: String,
)

/**
 * One station identity shared by the FM player, favourites, artwork and AF logic.
 * Raw RDS PS is treated as an observation, never as a persistent primary key.
 */
object FmStationIdentity {
    private val transientNames =
        setOf(
            "antenne",
            "stmk",
            "antennestmk",
            "antstmk",
            "radio",
            "fm",
            "antennenempfang",
            "physischerantennenempfang",
        )

    fun resolve(
        rawPs: String,
        storedName: String?,
        frequencies: Collection<Float>,
        pi: Int = 0,
        ecc: String? = null,
    ): FmResolvedStationIdentity {
        val normalizedFrequencies =
            frequencies
                .asSequence()
                .filter { it.isFinite() && it in 87.5f..108.0f }
                .map { (it * 10f).roundToInt() / 10f }
                .distinct()
                .sorted()
                .toList()
        val stored = storedName.orEmpty().trim()
        val raw = rawPs.trim()
        val catalog =
            AustrianFmStationCatalog.identify(stored, normalizedFrequencies)
                ?: AustrianFmStationCatalog.identify(raw, normalizedFrequencies)
                ?: shortRegionalIdentity(stored, raw, normalizedFrequencies)
        val specificStored = stored.takeIf { usefulName(it) && !isTransient(it) }
        val canonical =
            specificStored
                ?: catalog?.canonicalName
                ?: stored.takeIf(::usefulName)
                ?: raw.takeIf(::usefulName)
                ?: normalizedFrequencies.firstOrNull()?.let { "FM ${"%.1f".format(Locale.ROOT, it)} MHz" }
                ?: "FM"
        val stableId =
            when {
                catalog != null -> "station:${keyPart(catalog.canonicalName)}"
                pi > 0 -> {
                    val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
                    val eccPart = ecc.orEmpty().trim().lowercase(Locale.ROOT).takeIf { it.matches(Regex("[0-9a-f]{2}")) }
                    if (eccPart == null) "pi:$piHex" else "pi:$piHex:$eccPart"
                }
                specificStored != null -> "name:${keyPart(specificStored)}"
                usefulName(stored) -> "name:${keyPart(stored)}"
                usefulName(raw) -> "name:${keyPart(raw)}"
                normalizedFrequencies.isNotEmpty() -> "freq:${(normalizedFrequencies.first() * 10f).roundToInt()}"
                else -> "unknown"
            }
        val source =
            when {
                catalog != null -> "Katalog/Frequenzverbund"
                pi > 0 -> "PI/ECC"
                specificStored != null -> "gespeicherter Name"
                usefulName(raw) -> "RDS-PS"
                else -> "Frequenz"
            }
        return FmResolvedStationIdentity(
            stableId = stableId,
            canonicalName = canonical,
            recognized = catalog != null,
            source = source,
        )
    }

    fun orderKeys(
        rawPs: String,
        storedName: String?,
        frequencies: Collection<Float>,
        pi: Int = 0,
        ecc: String? = null,
    ): Set<String> {
        val resolved = resolve(rawPs, storedName, frequencies, pi, ecc)
        return buildSet {
            add(resolved.stableId)
            if (pi > 0) add("pi:${(pi and 0xffff).toString(16).padStart(4, '0')}")
            storedName?.takeIf(::usefulName)?.let { add("name:${keyPart(it)}") }
            rawPs.takeIf(::usefulName)?.let { add("name:${keyPart(it)}") }
            frequencies
                .filter { it.isFinite() && it in 87.5f..108.0f }
                .forEach { add("freq:${(it * 10f).roundToInt()}") }
            when (resolved.stableId) {
                "station:antenne_steiermark" -> {
                    add("name:antenne")
                    add("name:stmk")
                    add("name:antennestmk")
                    add("name:antstmk")
                }
                "station:antenne_kaernten" -> {
                    add("name:antenne")
                    add("name:antennektn")
                    add("name:antktn")
                }
            }
        }
    }

    private fun shortRegionalIdentity(
        storedName: String,
        rawPs: String,
        frequencies: List<Float>,
    ): AustrianFmIdentity? {
        val compactNames = listOf(storedName, rawPs).map(::compact)
        if (compactNames.any { it in setOf("stmk", "antennestmk", "antstmk") }) {
            return AustrianFmStationCatalog.identify("ANTENNE", frequencies)
                ?.takeIf { it.canonicalName == "Antenne Steiermark" }
        }
        return null
    }

    private fun isTransient(value: String): Boolean = compact(value) in transientNames

    private fun usefulName(value: String): Boolean {
        val normalized = normalize(value)
        if (normalized.isBlank()) return false
        if (normalized.matches(Regex("fm \\d{2,3}(?: \\d)?(?: mhz)?"))) return false
        return compact(value) !in setOf("fm", "radio", "antennenempfang", "physischerantennenempfang")
    }

    private fun keyPart(value: String): String = normalize(value).replace(' ', '_').ifBlank { "unknown" }

    private fun compact(value: String): String = normalize(value).replace(" ", "")

    private fun normalize(value: String): String {
        val transliterated =
            value.lowercase(Locale.GERMAN)
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
        return Normalizer.normalize(transliterated, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace("&", " und ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
    }
}
