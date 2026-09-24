# Dudu7 upstream baseline

Current Dudu7 synchronization review: 2026-08-20.

Dudu7 13.7.75 is based on the device-tested Dudu7 13.7.74 branch and selectively integrates/reviews Original MetroList changes through:

`e483f49f06ed235489b2a5e4647634e454ce30b3` (2026-08-19)

Explicitly integrated commits:

- `ad8390cdee408381a7effbb317486c515a48f0da` — persisted shuffle restore
- `ec9a6b3ec1ac8bc6cf362cab3eee9e632598e86f` — stream URL/cache/buffer recovery
- `0d37cc4658c18ac43123264edf48f7224b77d506` — Faraday cipher config store with Zemer fallback; Dudu7 build-tool files intentionally retained
- `0f316d1211c13c5f149777b2426e3be007b17619` — invalid playlist deep-link guard; existing Dudu7 dependency versions intentionally retained
- `e483f49f06ed235489b2a5e4647634e454ce30b3` — legacy DB migrations and artist alias persistence, including compatible pagination pieces in that commit

Dudu7 compatibility glue in this sync:

- the Dudu7 live-radio queue reset uses `StreamUrlCache.invalidate()` after the upstream cache-type migration;
- the `playlist_unavailable` string resource required by the selectively backported deep-link guard is carried locally.

This SHA is a reviewed-through baseline, not a claim that every upstream commit before it was merged. Future synchronization analyses must start after this review point and preserve Dudu7-specific FM, WebRadio, MediaSession and vehicle integrations.
