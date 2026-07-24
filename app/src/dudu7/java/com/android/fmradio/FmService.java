package com.android.fmradio;

import android.util.Log;

/** Callback target looked up by the FYT firmware JNI layer. */
public final class FmService {
    private static final String TAG = "FytFmService";

    public interface RdsListener {
        void onRdsEvent(int eventType, int value1, int value2, int value3);
    }

    private static volatile RdsListener listener;

    private FmService() {}

    public static void setRdsListener(RdsListener value) {
        listener = value;
    }

    public static int Rdscallback(int eventType, int value1, int value2, int value3) {
        Log.v(TAG, "RDS event " + eventType + ": " + value1 + "," + value2 + "," + value3);
        RdsListener current = listener;
        if (current != null) current.onRdsEvent(eventType, value1, value2, value3);
        return 0;
    }

    public static int Rdscallback(int eventType, String value) {
        Log.v(TAG, "RDS text event " + eventType + ": " + value);
        return 0;
    }

    public static int Rdscallback(int eventType, byte[] value) {
        Log.v(TAG, "RDS byte event " + eventType + ": " + (value == null ? 0 : value.length));
        return 0;
    }

    public static int callback(int value1, int value2) {
        return 0;
    }
}
