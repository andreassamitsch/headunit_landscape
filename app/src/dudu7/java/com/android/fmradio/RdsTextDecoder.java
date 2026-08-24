package com.android.fmradio;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Decodes raw RDS strings returned by the FYT firmware.
 *
 * Some Dudu7 firmware paths return UTF-8 while classic RDS data may still be
 * exposed as ISO-8859-1. Decode well-formed UTF-8 first and only fall back to
 * ISO-8859-1 when the byte sequence is not valid UTF-8. This keeps the
 * decision at the byte/charset boundary instead of trying to repair already
 * decoded strings later in the UI.
 */
final class RdsTextDecoder {
    private RdsTextDecoder() {}

    static String decode(byte[] data) {
        if (data == null || data.length == 0) return "";

        String value;
        try {
            value = StandardCharsets.UTF_8
                    .newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(data))
                    .toString();
        } catch (CharacterCodingException error) {
            value = new String(data, StandardCharsets.ISO_8859_1);
        }

        value = value
                .replaceAll("[\\x00-\\x1F]", "")
                .replace('\u00A0', ' ')
                .trim();
        if (value.toLowerCase(Locale.ROOT).contains("not support")) return "";
        return value;
    }
}
