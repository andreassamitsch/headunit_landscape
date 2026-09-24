/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */
package com.metrolist.music.utils

import com.metrolist.innertube.utils.parseCookieString

internal data class AdvancedLoginToken(
    val cookie: String = "",
    val visitorData: String = "",
    val dataSyncId: String = "",
    val accountName: String = "",
    val accountEmail: String = "",
    val accountChannelHandle: String = "",
) {
    val hasValidCookie: Boolean
        get() = cookie.isNotBlank() && "SAPISID" in parseCookieString(cookie)
}

/**
 * Parses both the MetroList export template and tolerant variants copied through Android
 * clipboards (CRLF, leading bullets/spaces, Markdown asterisks/backticks, ':' instead of '=').
 * A raw cookie string containing SAPISID is also accepted.
 */
internal fun parseAdvancedLoginToken(input: String): AdvancedLoginToken {
    val values = linkedMapOf<String, String>()
    val linePattern = Regex(
        pattern = """^\s*[-•]?\s*`*\**\s*(INNERTUBE\s+COOKIE|VISITOR\s+DATA|DATASYNC\s+ID|DATA\s+SYNC\s+ID|ACCOUNT\s+NAME|ACCOUNT\s+EMAIL|ACCOUNT\s+CHANNEL\s+HANDLE)\s*\**`*\s*(?:=|:)\s*(.*?)\s*$""",
        option = RegexOption.IGNORE_CASE,
    )

    input.replace("\r\n", "\n").replace('\r', '\n').lineSequence().forEach { rawLine ->
        val match = linePattern.matchEntire(rawLine) ?: return@forEach
        val normalizedLabel = match.groupValues[1]
            .uppercase()
            .replace(Regex("""\s+"""), " ")
            .replace("DATA SYNC ID", "DATASYNC ID")
        val value = match.groupValues[2].trim().trim('`')
        values[normalizedLabel] = value
    }

    var cookie = values["INNERTUBE COOKIE"].orEmpty().trim()
    if (cookie.isBlank()) {
        val raw = input.trim().trim('`')
        if ("SAPISID" in parseCookieString(raw)) cookie = raw
    }

    return AdvancedLoginToken(
        cookie = cookie,
        visitorData = values["VISITOR DATA"].orEmpty().trim(),
        dataSyncId = values["DATASYNC ID"].orEmpty().trim().substringBefore("||"),
        accountName = values["ACCOUNT NAME"].orEmpty().trim(),
        accountEmail = values["ACCOUNT EMAIL"].orEmpty().trim(),
        accountChannelHandle = values["ACCOUNT CHANNEL HANDLE"].orEmpty().trim(),
    )
}
