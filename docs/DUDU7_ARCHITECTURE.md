# Dudu7 overlay architecture

## Basis

- Offizieller MetroList-Upstream: `MetrolistGroup/Metrolist`
- Übernommener Upstream-Commit: `f0f91e4f7a7fa09fb3050dfe1d495e4c86542a99`
- MetroList-Version: `13.6.1`

## Prinzip

Playback, Login, Innertube, Cipher und Player-Konfigurationen stammen unverändert aus dem offiziellen Upstream. Die Dudu7-Anpassungen liegen überwiegend in der zusätzlichen Flavor-Dimension `device`:

- `app/src/standard`: unverändertes Standardverhalten
- `app/src/dudu7`: Querformat-, Player-, Queue-, Sprach- und Einstellungs-Erweiterungen

Der gemeinsame MetroList-Code enthält nur kleine, stabile Aufrufe an folgende Varianten-Hooks:

- `VehicleVariantDefaults`
- `VehicleLandscapeLayout`
- `VehiclePlayerControls`
- `VehicleNavigation`
- `VehicleQueueActions`
- `rememberVehicleVoiceSearch`
- `VehicleEmptyPlayer`

## Dudu7-Verhalten

- eigener Paket-Suffix `.dudu7`
- feste Querformat-Ausrichtung
- Player beim Start ausgeklappt
- RVX-inspirierter Player links, permanente Warteschlange rechts
- feste rechte Queue ohne zusätzliches Smartphone-Bottom-Sheet
- kompakter RVX-Player mit großem Cover und reiner Icon-Aktionsleiste
- rechte Tabs für Warteschlange, Playlists und Bibliothek
- Queue per Drag-and-drop sortierbar
- konfigurierbare Pane-Breite, Wischgeste und Auto-Zentrierung
- Android-Spracherkennung statt Musikerkennungsseite
- stabiler, im privaten Repository abgelegter Debug-Schlüssel für updatefähige Test-APKs

## Upstream-Aktualisierung

Der wöchentliche Workflow merged den offiziellen Upstream in einen Review-Branch, baut Standard und Dudu7 und öffnet einen Pull Request. Es findet kein automatischer Merge statt.
