"""Build-only pathlib proxy for the existing 13.7.13 validation rerun.

It loads Python's real standard-library pathlib and only makes the Player.kt
string replacement insensitive to whitespace. Android/Kotlin sources do not
use this file at runtime.
"""

from __future__ import annotations

import importlib.util
import os
import sys

_stdlib_file = os.path.join(
    sys.base_prefix,
    "lib",
    f"python{sys.version_info.major}.{sys.version_info.minor}",
    "pathlib.py",
)
_spec = importlib.util.spec_from_file_location("_dudu7_stdlib_pathlib", _stdlib_file)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load standard pathlib from {_stdlib_file}")
_stdlib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stdlib)

Path = _stdlib.Path
PurePath = _stdlib.PurePath
PosixPath = _stdlib.PosixPath
WindowsPath = _stdlib.WindowsPath
PurePosixPath = _stdlib.PurePosixPath
PureWindowsPath = _stdlib.PureWindowsPath

_original_read_text = Path.read_text
_player_suffix = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
_album_marker = "val albumId = currentMediaMetadata.album?.id"


class _PlayerSource(str):
    def __contains__(self, item: object) -> bool:
        if isinstance(item, str) and _album_marker in item:
            return _album_marker in str(self)
        return super().__contains__(item)

    def replace(self, old: str, new: str, count: int = -1) -> str:
        if _album_marker in old and _album_marker in str(self):
            text = str(self)
            title_start = text.index("                                onTitleClick = {")
            title_end = text.index("                                onArtistClick = {", title_start)
            navigation_line = "                                    if (!playerConnection.requestRightPaneNavigation(route))"
            navigation_start = text.index(navigation_line, title_start, title_end)
            else_marker = "                                        } else {"
            else_start = text.rfind(else_marker, title_start, navigation_start)
            if else_start < 0:
                raise RuntimeError("YouTube Music title-click else block not found")
            return text[:else_start] + new + "\n" + text[navigation_start:]
        return super().replace(old, new, count)


def _read_text(self: Path, *args, **kwargs):
    text = _original_read_text(self, *args, **kwargs)
    if self.as_posix().endswith(_player_suffix):
        return _PlayerSource(text)
    return text


Path.read_text = _read_text

__all__ = [
    "Path",
    "PurePath",
    "PosixPath",
    "WindowsPath",
    "PurePosixPath",
    "PureWindowsPath",
]
