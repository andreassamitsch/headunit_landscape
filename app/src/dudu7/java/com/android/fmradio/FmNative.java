package com.android.fmradio;

import android.content.Context;
import android.media.AudioManager;
import android.os.Bundle;
import android.util.Log;

import java.lang.reflect.Method;

/**
 * JNI bridge to the FYT firmware-provided libfmjni.so.
 *
 * The package and class name are part of the native contract. Do not move this
 * class without also changing the firmware JNI registration, which is outside
 * the application.
 */
public final class FmNative {
    private static final String TAG = "FytFmNative";

    public static final int CMD_GET_MONO_STEREO = 0x09;
    public static final int CMD_GET_RSSI = 0x0b;
    public static final int CMD_SET_GET_AREA = 0x14;
    public static final int CMD_RDS_ON_OFF = 0x15;
    public static final int CMD_RDS_GET_PS = 0x1e;
    public static final int CMD_RDS_GET_TEXT = 0x1f;

    public static final int AREA_EUROPE = 2;

    private static final int STREAM_FM = 10;

    private static final FmNative INSTANCE = new FmNative();
    private static boolean libraryLoaded;
    private static AudioManager audioManager;
    private static Method setParameterMethod;

    static {
        try {
            System.loadLibrary("fmjni");
            libraryLoaded = true;
            Log.i(TAG, "Loaded firmware libfmjni.so");
        } catch (Throwable error) {
            libraryLoaded = false;
            Log.e(TAG, "Could not load firmware libfmjni.so", error);
        }
    }

    private FmNative() {}

    public static FmNative getInstance() {
        return INSTANCE;
    }

    public static boolean isLibraryLoaded() {
        return libraryLoaded;
    }

    public static void initAudio(Context context) {
        if (audioManager != null) return;
        try {
            audioManager = (AudioManager) context.getApplicationContext().getSystemService(Context.AUDIO_SERVICE);
            setParameterMethod = AudioManager.class.getDeclaredMethod("setParameter", String.class, String.class);
            setParameterMethod.setAccessible(true);
        } catch (Throwable error) {
            Log.w(TAG, "Hidden FM volume hook is unavailable; FYT service routing remains active", error);
        }
    }

    public static void setFirmwareFmVolumeEnabled(boolean enabled) {
        if (audioManager == null || setParameterMethod == null) return;
        try {
            int volume = audioManager.getStreamVolume(STREAM_FM);
            if (volume <= 0) volume = 15;
            setParameterMethod.invoke(audioManager, "FM_Volume", enabled ? String.valueOf(volume) : "0");
        } catch (Throwable error) {
            Log.w(TAG, "Could not set FYT FM volume", error);
        }
    }

    public native boolean openDev();
    public native boolean closeDev();
    public native boolean powerUp(float frequency);
    public native boolean powerDown(int type);
    public native boolean tune(float frequency);
    public native float[] seek(float frequency, boolean isUp);
    public native int setMute(boolean mute);
    public static native short[] autoScan(int band);
    public native boolean stopScan();

    public native byte[] getPs();
    public native byte[] getLrText();
    public native int setRds(boolean enable);
    public native short readRds();
    public native int isRdsSupport();

    public native int setmonostero(int mode);
    public native int getmonostero(int mode);
    public native boolean stereoMono();
    public native int readRssi();
    public native short getPI();
    public native byte getECC();
    public native short[] getAFList();
    public native int switchAntenna(int antenna);
    public native short activeAf();
    public native int setconfig(String config);
    public native int sqlautoScan(int band, short[] frequencies, short[] rssiValues);
    public native int fmsyu_jni(int command, Object input, Object output);

    public int getRssi() {
        if (!libraryLoaded) return 0;
        try {
            int direct = readRssi();
            if (direct != 0) return direct;
        } catch (Throwable error) {
            Log.d(TAG, "Direct RSSI command unavailable", error);
        }
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_RSSI, new Bundle(), output);
            if (result == 0 && output.containsKey("rssilevel")) {
                return output.getInt("rssilevel");
            }
        } catch (Throwable error) {
            Log.d(TAG, "RSSI bundle command unavailable", error);
        }
        return 0;
    }

    public boolean setEuropeArea() {
        if (!libraryLoaded) return false;
        try {
            Bundle input = new Bundle();
            input.putInt("area", AREA_EUROPE);
            return fmsyu_jni(CMD_SET_GET_AREA, input, new Bundle()) == 0;
        } catch (Throwable error) {
            Log.d(TAG, "Area command unavailable", error);
            return false;
        }
    }

    /**
     * @return 1 for stereo, 0 for confirmed mono, -1 when the firmware exposes
     *         no reliable stereo state. Unknown must never be rendered as Mono.
     */
    public int getStereoState() {
        if (!libraryLoaded) return -1;
        try {
            return stereoMono() ? 1 : 0;
        } catch (Throwable error) {
            Log.d(TAG, "Direct stereoMono command unavailable", error);
        }
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_MONO_STEREO, new Bundle(), output);
            if (result == 0) {
                String[] keys = {"stereo", "isStereo", "monoStereo", "monostereo", "value"};
                for (String key : keys) {
                    if (!output.containsKey(key)) continue;
                    Object raw = output.get(key);
                    if (raw instanceof Boolean) return ((Boolean) raw) ? 1 : 0;
                    if (raw instanceof Number) {
                        int value = ((Number) raw).intValue();
                        if (value == 0 || value == 1) return value;
                        if (value == 2) return 1;
                    }
                }
            }
        } catch (Throwable error) {
            Log.d(TAG, "Stereo bundle command unavailable", error);
        }
        try {
            int value = getmonostero(0);
            if (value == 0 || value == 1) return value;
            if (value == 2) return 1;
        } catch (Throwable error) {
            Log.d(TAG, "Legacy mono/stereo command unavailable", error);
        }
        return -1;
    }

    public boolean isStereoReceiving() {
        return getStereoState() == 1;
    }

    public int getProgramIdentifier() {
        if (!libraryLoaded) return 0;
        try {
            return getPI() & 0xffff;
        } catch (Throwable error) {
            Log.d(TAG, "Direct PI command unavailable", error);
            return 0;
        }
    }

    public String getExtendedCountryCode() {
        if (!libraryLoaded) return "";
        try {
            int value = getECC() & 0xff;
            return value == 0 ? "" : String.format(java.util.Locale.ROOT, "%02x", value);
        } catch (Throwable error) {
            Log.d(TAG, "Direct ECC command unavailable", error);
            return "";
        }
    }

    public float[] getAlternativeFrequencies() {
        if (!libraryLoaded) return new float[0];
        try {
            short[] raw = getAFList();
            if (raw == null || raw.length == 0) return new float[0];
            java.util.ArrayList<Float> values = new java.util.ArrayList<>();
            for (short item : raw) {
                float value = item & 0xffff;
                float decoded;
                if (value >= 875f && value <= 1080f) {
                    decoded = value / 10f;
                } else if (value >= 8750f && value <= 10800f) {
                    decoded = value / 100f;
                } else if (value >= 87500f && value <= 108000f) {
                    decoded = value / 1000f;
                } else {
                    continue;
                }
                if (decoded >= 87.5f && decoded <= 108.0f && !values.contains(decoded)) {
                    values.add(decoded);
                }
            }
            float[] result = new float[values.size()];
            for (int index = 0; index < values.size(); index++) result[index] = values.get(index);
            return result;
        } catch (Throwable error) {
            Log.d(TAG, "AF list command unavailable", error);
            return new float[0];
        }
    }

    public String getPsString() {
        if (!libraryLoaded) return "";
        try {
            Bundle output = new Bundle();
            if (fmsyu_jni(CMD_RDS_GET_PS, new Bundle(), output) == 0) {
                String value = RdsTextDecoder.decode(output.getByteArray("PSname"));
                if (!value.isEmpty()) return value;
            }
        } catch (Throwable error) {
            Log.d(TAG, "PS bundle command unavailable", error);
        }
        try {
            return RdsTextDecoder.decode(getPs());
        } catch (Throwable error) {
            Log.d(TAG, "Direct PS read unavailable", error);
            return "";
        }
    }

    public String getRadioText() {
        if (!libraryLoaded) return "";
        try {
            Bundle output = new Bundle();
            if (fmsyu_jni(CMD_RDS_GET_TEXT, new Bundle(), output) == 0) {
                String value = RdsTextDecoder.decode(output.getByteArray("Text"));
                if (!value.isEmpty()) return value;
            }
        } catch (Throwable error) {
            Log.d(TAG, "RT bundle command unavailable", error);
        }
        try {
            return RdsTextDecoder.decode(getLrText());
        } catch (Throwable error) {
            Log.d(TAG, "Direct RT read unavailable", error);
            return "";
        }
    }
}
