package com.android.fmradio;

import android.content.Context;
import android.media.AudioManager;
import android.os.Bundle;
import android.util.Log;

import java.lang.reflect.Method;
import java.nio.charset.Charset;

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
    private static final Charset RDS_CHARSET = Charset.forName("ISO-8859-1");

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
    public native int switchAntenna(int antenna);
    public native short activeAf();
    public native int setconfig(String config);
    public native int sqlautoScan(int band, short[] frequencies, short[] rssiValues);
    public native int fmsyu_jni(int command, Object input, Object output);

    public int getRssi() {
        if (!libraryLoaded) return 0;
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_RSSI, new Bundle(), output);
            if (result == 0) return output.getInt("rssilevel", 0);
        } catch (Throwable error) {
            Log.d(TAG, "RSSI command unavailable", error);
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

    public boolean isStereoReceiving() {
        if (!libraryLoaded) return false;
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_MONO_STEREO, new Bundle(), output);
            if (result == 0) {
                return output.getInt("status", output.getInt("value", 0)) == 1;
            }
        } catch (Throwable error) {
            Log.d(TAG, "Stereo command unavailable", error);
        }
        return false;
    }

    public String getPsString() {
        if (!libraryLoaded) return "";
        try {
            Bundle output = new Bundle();
            if (fmsyu_jni(CMD_RDS_GET_PS, new Bundle(), output) == 0) {
                String value = decode(output.getByteArray("PSname"));
                if (!value.isEmpty()) return value;
            }
        } catch (Throwable error) {
            Log.d(TAG, "PS bundle command unavailable", error);
        }
        try {
            return decode(getPs());
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
                String value = decode(output.getByteArray("Text"));
                if (!value.isEmpty()) return value;
            }
        } catch (Throwable error) {
            Log.d(TAG, "RT bundle command unavailable", error);
        }
        try {
            return decode(getLrText());
        } catch (Throwable error) {
            Log.d(TAG, "Direct RT read unavailable", error);
            return "";
        }
    }

    private static String decode(byte[] data) {
        if (data == null || data.length == 0) return "";
        String value = new String(data, RDS_CHARSET)
                .replaceAll("[\\x00-\\x1F]", "")
                .replace('\u00A0', ' ')
                .trim();
        if (value.toLowerCase().contains("not support")) return "";
        return value;
    }
}
