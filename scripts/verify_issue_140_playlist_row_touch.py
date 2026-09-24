from pathlib import Path

p = Path('app/src/main/kotlin/com/metrolist/music/ui/screens/playlist/OnlinePlaylistScreen.kt')
s = p.read_text()
required = [
    'LocalRightPaneScrollBridge',
    'rightPaneScrollBridge.register(',
    'handler = { delta -> lazyListState.dispatchRawDelta(delta) }',
    'tapHandler = { positionInRoot ->',
    'rightPaneSongTapTargets',
    'coordinates.boundsInRoot() to onSongClick',
    'userScrollEnabled = rightPaneScrollBridge == null',
    'Dudu7PlaylistPlayback',
    'YouTubePlaylistQueue(',
    'startIndex = index',
]
for needle in required:
    assert needle in s, needle
assert 'if (rightPaneScrollBridge != null) Modifier else Modifier.combinedClickable(' in s
print('PASS: Issue #140 embedded playlist rows use the Dudu7 bridge and preserve standard touch handling')
