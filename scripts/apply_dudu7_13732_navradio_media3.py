#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected block not found in {path}:\n{old[:240]}")
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one block in {path}, found {text.count(old)}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Install the Dudu7 FM Media3 player whenever the FYT backend is initialized.
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    "import com.metrolist.music.playback.Dudu7FmMediaButtonRouting\n",
    "import com.metrolist.music.playback.Dudu7FmMediaButtonRouting\n"
    "import com.metrolist.music.playback.Dudu7FmSessionRouting\n",
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    "        Dudu7FmMediaButtonRouting.install(applicationContext)\n"
    "        startRtrServices(applicationContext)\n",
    "        Dudu7FmMediaButtonRouting.install(applicationContext)\n"
    "        Dudu7FmSessionRouting.install(applicationContext)\n"
    "        startRtrServices(applicationContext)\n",
)

# While FM is represented by the session player, let Media3 handle the key instead
# of invoking the old direct bridge as a second independent path.
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7MediaButtonReceiver.kt",
    "        Dudu7FmMediaButtonRouting.install(context.applicationContext)\n"
    "        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return\n"
    "        MediaButtonReceiver().onReceive(context, intent)\n",
    "        Dudu7FmMediaButtonRouting.install(context.applicationContext)\n"
    "        Dudu7FmSessionRouting.install(context.applicationContext)\n"
    "        if (!PhysicalFmSessionBridge.isActive() && PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return\n"
    "        MediaButtonReceiver().onReceive(context, intent)\n",
)

replace_once(
    "app/src/main/kotlin/com/metrolist/music/playback/MediaLibrarySessionCallback.kt",
    "        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return true\n",
    "        if (!PhysicalFmSessionBridge.owns(session.player) &&\n"
    "            PhysicalFmMediaKeyBridge.handleMediaButton(intent)\n"
    "        ) return true\n",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/playback/MediaLibrarySessionCallback.kt",
    "        if (direction != null && PhysicalFmMediaKeyBridge.handleDirection(direction)) {\n"
    "            return SessionResult.RESULT_SUCCESS\n"
    "        }\n",
    "        if (direction != null &&\n"
    "            !PhysicalFmSessionBridge.owns(session.player) &&\n"
    "            PhysicalFmMediaKeyBridge.handleDirection(direction)\n"
    "        ) {\n"
    "            return SessionResult.RESULT_SUCCESS\n"
    "        }\n",
)

# Make the FM player's tested navigation rules the code path used for Media3 next/previous.
player_file = "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FmSessionPlayer.kt"
replace_once(
    player_file,
    "            -> wrapIndex(currentIndex + 1, favourites.size)\n",
    "            -> Dudu7FmSessionNavigation.adjacentIndex(favourites.size, currentIndex, next = true)\n",
)
replace_once(
    player_file,
    "            -> wrapIndex(currentIndex - 1, favourites.size)\n",
    "            -> Dudu7FmSessionNavigation.adjacentIndex(favourites.size, currentIndex, next = false)\n",
)
replace_once(
    player_file,
    "        if (detectedId != null) {\n"
    "            activeFavouriteId = detectedId\n"
    "        } else if (activeFavouriteId !in validIds) {\n"
    "            activeFavouriteId = resolveCurrentFavouriteId(state)\n"
    "        }\n",
    "        activeFavouriteId = Dudu7FmSessionNavigation.retainActiveId(\n"
    "            validIds = validIds,\n"
    "            rememberedId = activeFavouriteId,\n"
    "            detectedId = detectedId,\n"
    "            fallbackId = resolveCurrentFavouriteId(state),\n"
    "        )\n",
)
replace_once(
    player_file,
    "\n    private fun wrapIndex(value: Int, size: Int): Int {\n"
    "        if (size <= 0) return C.INDEX_UNSET\n"
    "        return ((value % size) + size) % size\n"
    "    }\n",
    "\n",
)

# Swap the existing MediaLibrarySession between ExoPlayer and the FYT FM player.
music = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
replace_once(
    music,
    "    private var mediaSession: MediaLibrarySession? = null\n"
    "    private var controllerFuture: com.google.common.util.concurrent.ListenableFuture<MediaController>? = null\n",
    "    private var mediaSession: MediaLibrarySession? = null\n"
    "    private var controllerFuture: com.google.common.util.concurrent.ListenableFuture<MediaController>? = null\n"
    "    private var removePhysicalFmSessionObserver: (() -> Unit)? = null\n"
    "    private var physicalFmSessionJob: Job? = null\n"
    "    private var physicalFmController: PhysicalFmSessionBridge.Controller? = null\n",
)
replace_once(
    music,
    "                ).setBitmapLoader(CoilBitmapLoader(this, scope))\n"
    "                .build()\n"
    "        player.repeatMode = startupPrefs!![RepeatModeKey] ?: REPEAT_MODE_OFF\n",
    "                ).setBitmapLoader(CoilBitmapLoader(this, scope))\n"
    "                .build()\n"
    "        observePhysicalFmSession()\n"
    "        player.repeatMode = startupPrefs!![RepeatModeKey] ?: REPEAT_MODE_OFF\n",
)
replace_once(
    music,
    "                try {\n"
    "                    mediaSession?.let { (it as MediaSession).player = newPlayer }\n"
    "                } catch (e: Exception) {\n"
    "                    Timber.tag(TAG).e(e, \"Failed to swap player in MediaSession\")\n"
    "                }\n",
    "                try {\n"
    "                    if (!PhysicalFmSessionBridge.isActive()) {\n"
    "                        mediaSession?.let { (it as MediaSession).player = newPlayer }\n"
    "                    }\n"
    "                } catch (e: Exception) {\n"
    "                    Timber.tag(TAG).e(e, \"Failed to swap player in MediaSession\")\n"
    "                }\n",
)
replace_once(
    music,
    "        if (playWhenReady && castConnectionHandler?.isCasting?.value == true) {\n"
    "            player.pause()\n"
    "            return\n"
    "        }\n\n"
    "        if (reason == Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST) {\n",
    "        if (playWhenReady && castConnectionHandler?.isCasting?.value == true) {\n"
    "            player.pause()\n"
    "            return\n"
    "        }\n\n"
    "        if (playWhenReady && PhysicalFmSessionBridge.isActive()) {\n"
    "            PhysicalFmSessionBridge.deactivate()\n"
    "        }\n\n"
    "        if (reason == Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST) {\n",
)

observer_function = '''\n    private fun observePhysicalFmSession() {\n        removePhysicalFmSessionObserver?.invoke()\n        removePhysicalFmSessionObserver = PhysicalFmSessionBridge.observe { controller ->\n            scope.launch {\n                physicalFmSessionJob?.cancel()\n                physicalFmController = controller\n                if (controller == null) {\n                    mediaSession?.let { session ->\n                        if (session.player !== player) {\n                            (session as MediaSession).player = player\n                        }\n                    }\n                    return@launch\n                }\n\n                physicalFmSessionJob = scope.launch {\n                    controller.isActive.distinctUntilChanged().collect { active ->\n                        val target = if (active) controller.player else player\n                        mediaSession?.let { session ->\n                            if (session.player !== target) {\n                                (session as MediaSession).player = target\n                                Timber.tag(TAG).i(\n                                    \"MediaSession player switched to %s\",\n                                    if (active) \"physical FM\" else \"ExoPlayer\",\n                                )\n                                updateNotification()\n                            }\n                        }\n                    }\n                }\n            }\n        }\n    }\n\n'''
replace_once(
    music,
    "    override fun onDestroy() {\n",
    observer_function + "    override fun onDestroy() {\n",
)
replace_once(
    music,
    "        mediaLibrarySessionCallback.release()\n"
    "        mediaSession?.release()\n",
    "        physicalFmSessionJob?.cancel()\n"
    "        physicalFmSessionJob = null\n"
    "        removePhysicalFmSessionObserver?.invoke()\n"
    "        removePhysicalFmSessionObserver = null\n"
    "        physicalFmController = null\n"
    "        mediaLibrarySessionCallback.release()\n"
    "        mediaSession?.release()\n",
)

# Update-compatible version bump.
replace_once(
    "app/build.gradle.kts",
    "        versionCode = 1370040\n        versionName = \"13.7.31\"\n",
    "        versionCode = 1370041\n        versionName = \"13.7.32\"\n",
)

print("Applied Dudu7 13.7.32 NavRadio-style Media3 FM player integration")
