# Dudu7 Round 2 – FM, Tabs und Künstlerseite

## Umgesetzt

### Rechte Tabs

- Standardreihenfolge: Warteschlange, Bibliothek, WebRadio, FM, Suche, Hörverlauf
- Warteschlange bleibt Starttab
- Tabs lassen sich ohne Drag-Symbol durch langes Halten horizontal verschieben
- Benutzerdefinierte Reihenfolge wird dauerhaft gespeichert

### Eingebettete Künstlerseite

- Flache, touch-sichere Dudu7-Künstlerseite statt der überlagerten Handy-Ansicht
- Künstlerbild, Beschreibung, Radio und Shuffle
- Direkt spielbare sichtbare Songs
- Klickbare Unterkategorien mit `Alle anzeigen`
- Top-Songs-Fallback, wenn YouTube Music keinen `moreEndpoint` liefert
- Navigation zu Alben, Playlists, Künstlern, Podcasts und Episoden
- Normale Handy-Künstlerseite bleibt unverändert

### Physisches FM-Radio

- Getrennte Bereiche für Favoriten, automatischen Sendersuchlauf, manuelle Abstimmung und Radiofunktionen
- Nativer FYT-`autoScan` mit bandweitem RSSI-Fallback
- Suchfortschritt, aktuelle Frequenz und Anzahl gefundener Sender
- Ergebnisliste mit Senderlogo, Name, Frequenz, RSSI, Stereo/Mono, PTY und TP
- Einzel-/Mehrfachauswahl, Probehören und anschließendes Speichern
- AF-Schalter und manueller/automatischer AF-Versuch über `activeAf()`
- TA-Schalter und TA-Statusanzeige
- TP- und PTY-Anzeige
- REG-Schalter über bestmögliche FYT-`setconfig`-Anbindung
- Einstellungen werden dauerhaft gespeichert

## Automatisch geprüft

- Architekturprüfung
- Dudu7-Kompilierung
- Unit-Tests
- Lint
- signierte ARM-APK mit korrektem Paketnamen, Version und beiden ARM-ABIs
- x86_64-Emulator-Build
- WebRadio-Favoritenstart und aktive Senderanzeige
- Vor/Zurück-Reihenfolge der Radiofavoriten
- stabile Senderlogos
- WebRadio ↔ YouTube-Music-Wechsel
- Künstlerseite: Darstellung, Scrollen, Navigation und Radio-Aktion
- Hörverlauf ohne Radiosender
- keine App-Crashes oder ANRs

## Noch am echten Dudu7 zu prüfen

- realer FYT-Sendersuchlauf und Erkennungsqualität
- RDS-Namen, PI, PTY, TP und TA mit österreichischen Sendern
- AF-Wechsel während der Fahrt
- REG-Unterstützung der konkreten FYT-Firmware
- Senderlogos bei realen RDS-Namen
- Tab-Drag-and-drop per Touch am Headunit-Display
- FM/WebRadio-Audioroutenwechsel auf der Hardware
