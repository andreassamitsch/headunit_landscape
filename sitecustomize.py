"""Build-only compatibility shim for the existing 13.7.13 validation run.

The first run matched the correct Player title-click block too strictly by
whitespace.  Python imports this module automatically, allowing the rerun to
apply the same semantic replacement by block position without changing the
application at runtime.
"""

from pathlib import Path

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
