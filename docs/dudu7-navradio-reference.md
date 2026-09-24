# NavRadio+ 4.08 Dudu7/UIS7870 reference

This note records the backend selection verified from the decompiled NavRadio+ 4.08 XAPK before implementation of issue #58.

## Device selection

- Brand: `DUDUAUTO`
- Product/device: `SC7870` or `uis7870*`
- NavRadio flags: `isDUDU7=true`, `is7870=true`

## Tuner backend

The Dudu7 branch uses the Syu `Media` / `RadioProxy` environment and creates `com.android.fmradio.FmService`, backed by `FmNative`. It does not select `android.tw.john.TWUtil`; that class belongs to another device backend.

## Media-key path

NavRadio is a `MediaSessionService`. It creates its custom Media3 radio player and MediaSession before completing the hardware-radio initialization. Next/previous transport commands are routed by that player to NavRadio's own station/favourite navigation.

## Metrolist implementation constraints

1. Keep the working Dudu7 `FmService`/`FmNative` tuner path.
2. Do not make optional TWUtil classes a prerequisite for FM.
3. Use the existing single MusicService MediaSession with the FM player/timeline.
4. Claim the MediaSession for the FM player before activating the vendor FM source.
5. Release the claim after FM shutdown or failed startup.
6. Do not activate a competing legacy MediaSession or TWUtil listener on Dudu7.
7. Preserve a fallback to the normal ExoPlayer session when FM is not claimed.
