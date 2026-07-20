# Dudu7-Schicht für MetroList

## Ziel

MetroList bleibt möglichst nah am offiziellen Upstream. Die Autoradio-Anpassungen werden nicht mehr als immer größere Änderungen in zentralen Dateien gepflegt, sondern als eigene Gerätevariante auf den bestehenden MetroList-Funktionen aufgebaut.

Die Dudu7-Variante kombiniert:

- den normalen MetroList-Kern für Login, YouTube Music, Datenbank, Downloads und Wiedergabe;
- den GMS-Diensteflavor für Google Cast und die auf dem Gerät vorhandenen Google-Dienste;
- ein eigenes `dudu7`-Source-Set für Startverhalten, Oberfläche und Fahrzeugoptionen.

Die installierbare Autoradio-Variante heißt technisch `gmsDudu7`. Normale MetroList-Builds verwenden das Geräteflavor `standard`.

## Flavor-Struktur

```text
Diensteflavor: foss | gms | izzy
Geräteflavor:  standard | dudu7
```

Beispiele:

```text
fossStandardDebug
 gmsStandardDebug
 gmsDudu7Debug
```

Unnötige Kombinationen können später über die Android-Variant-API deaktiviert werden. Entscheidend ist, dass Dienstefunktionen und Geräteoberfläche nicht mehr miteinander vermischt sind.

## Stabile Erweiterungspunkte

Der gemeinsame MetroList-Code kennt nur wenige kleine Verträge unter `com.metrolist.music.variant`:

- `VehicleVariantConfig` – unveränderliche Standardwerte je Geräteflavor;
- `VehicleVariantDefaults` – einmalige Voreinstellungen, ohne vorhandene Nutzereinstellungen zu überschreiben;
- `VehicleSettingsScreen` – Dudu7-Einstellungen; im Standardflavor eine leere Implementierung;
- `VehicleEmptyPlayer` – Dudu7-Startoberfläche ohne aktive Wiedergabe;
- `Dudu7Layout` – gemeinsam testbare Layoutgrenzen.

Neue Dudu7-Funktionen gehören grundsätzlich nach `app/src/dudu7`. Erst wenn eine Funktion Daten oder Verhalten aus dem Kern benötigt, wird ein möglichst kleiner Erweiterungspunkt mit einer Standard- und einer Dudu7-Implementierung ergänzt.

## Player und Warteschlange

Die Dudu7-App öffnet direkt den erweiterten Querformat-Player. Links befinden sich Cover, Titel und Wiedergabesteuerung, rechts die Warteschlange. Ohne aktiven Titel bleibt die Playeroberfläche sichtbar und bietet Schnellzugriffe auf Likes, Suche und Mediathek.

Es gibt keinen einschränkenden Fahrmodus. Die vorhandene MetroList-Warteschlange bleibt vollständig funktionsfähig:

- Drag-and-drop;
- Entfernen per Wischgeste;
- Mehrfachauswahl;
- Shuffle und Wiederholen;
- Queue-Menüs und Undo.

Die Dudu7-Einstellungen steuern unter anderem Playerbreite, Startansicht, Bearbeitungssperre, Wischgeste, automatische Zentrierung, Bildschirm-an-Verhalten und Bluetooth-Fortsetzung.

## Upstream-Aktualisierung

Der langfristige Branch ist `dudu7`. Ein geplanter Workflow:

1. holt `MetrolistGroup/Metrolist:main`;
2. erstellt oder aktualisiert `sync/metrolist-upstream`;
3. führt den Merge dort aus;
4. baut und prüft `gmsStandardDebug` und `gmsDudu7Debug`;
5. öffnet einen Pull Request nach `dudu7`.

Der Workflow führt niemals automatisch zusammen. Konflikte und funktionale Änderungen werden vor dem Merge geprüft.

## CI-Anforderungen

Jeder Architektur- oder Update-PR muss mindestens Folgendes bestehen:

```text
assembleFossStandardDebug
lintFossStandardDebug
assembleGmsDudu7Debug
lintGmsDudu7Debug
testGmsDudu7DebugUnitTest
```

Ein separater Schnellbuild erzeugt eine installierbare GMS-Dudu7-APK mit dauerhafter Debug-Signatur.

## Wartungsregeln

1. Keine neuen Build-Skripte, die vor jedem Build Quelltext per Zeichenkettenersetzung verändern.
2. Dudu7-Oberfläche bevorzugt im Dudu7-Source-Set implementieren.
3. Gemeinsame Kernänderungen klein, einzeln und klar benannt halten.
4. Standard- und Dudu7-Variante bei jeder Upstream-Aktualisierung gemeinsam prüfen.
5. Änderungen an Wiedergabe oder Innertube zuerst gegen den aktuellen MetroList-Upstream vergleichen, bevor sie dauerhaft im Fork bleiben.
