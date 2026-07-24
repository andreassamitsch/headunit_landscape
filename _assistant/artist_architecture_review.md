# Künstleransicht im Dudu7-Split-Layout – Architekturprüfung

Status: Analysebasis, keine neue Implementierung.

## Rücksetzpunkt

Die Codebasis entspricht wieder dem ausgelieferten Stand 13.7.1. Sämtliche nachfolgenden 13.7.2-Versuche für Scroll-, Pointer-, Render- und Non-Lazy-Sonderlogik sind nicht Teil dieser Basis.

## Beobachtete Fehler

- Die originale Künstlerseite wird im rechten Split-Pane dargestellt.
- Eine vertikale Geste kann den logischen Zustand der LazyColumn verändern, während der sichtbare Inhalt anschließend vollständig weiß bleibt.
- Play-/Abschnittsaktionen reagieren in der eingebetteten Variante nicht zuverlässig.
- Andere rechte Tabs können scrollen.
- Die globale Up-/Down-Geste des ursprünglichen Players muss erhalten bleiben.

## Schlussfolgerung

Der Fehler darf nicht als allgemeiner Player-Scrollfehler behandelt werden. Die bisherigen Versuche haben zu viele Ebenen gekoppelt:

1. Player-Bottom-Sheet beziehungsweise dessen Nested-Scroll-Verbindung.
2. Fester Dudu7-Split-Pane-Container.
3. Eigener NavHost des rechten Panes.
4. Originale ArtistScreen-LazyColumn mit App-Bar, FABs, horizontalen LazyRows und verschachtelten Clickables.
5. Zusätzliche Pointer- und Scroll-Bridges.

Manuelles Verschieben des LazyListState außerhalb seiner eigenen Scroll-Pipeline ist als Ursache für inkonsistente Semantik-/Renderzustände anzusehen und soll nicht erneut verwendet werden.

## Empfohlener nächster Architekturansatz

### 1. Reproduktions-Harness ohne Player

Die originale ArtistScreen wird zuerst in einer isolierten Dudu7-Test-Activity beziehungsweise Preview-ähnlichen Host-Activity mit exakt 640 × 720 dp eingebettet. Dadurch wird getrennt geprüft:

- Funktioniert Scrollen und Rendering bei halber Breite ohne Player?
- Funktionieren Play All, Radio, Shuffle und Abschnittsnavigation?
- Entsteht das Weißbild bereits nur durch Breite, Insets oder verschachtelte Lazy-Komponenten?

### 2. Danach schichtweise Integration

Nur wenn der isolierte Host funktioniert, werden einzeln ergänzt:

1. rechter NavHost,
2. Split-Row,
3. Player-Bottom-Sheet/Nested Scroll.

Nach jeder Stufe wird derselbe Pixel- und Interaktionstest ausgeführt. So lässt sich die erste fehlerhafte Schicht eindeutig bestimmen.

### 3. Gestenvertrag statt Pointer-Bridge

Es soll keine positionsbasierte Tap-Bridge und kein externer scrollBy-/dispatchRawDelta-Kanal mehr geben. Der rechte Pane braucht ein klares Gestenmodell:

- Gesten innerhalb des Pane gehen zunächst an dessen Inhalt.
- Nur nicht verbrauchte vertikale Bewegung am oberen beziehungsweise unteren Rand darf an die globale Player-Up-/Down-Geste weitergegeben werden.
- Das soll über Compose NestedScrollConnection/NestedScrollDispatcher erfolgen, nicht über PointerEventPass.Initial und manuelles Consuming.

### 4. Originale Künstlerseite möglichst unverändert lassen

Statt eine zweite reduzierte Künstlerseite zu pflegen, soll die originale ArtistScreen einen kleinen Host-Vertrag erhalten, beispielsweise:

- verfügbare Pane-Größe,
- angepasste Insets,
- optionales Scroll-Interop-Objekt,
- Callback für nicht verbrauchte Randgesten.

Datenaufbereitung, Songaktionen, Navigation und Play All bleiben in der Originalimplementierung.

### 5. Abnahmekriterien

Ein neuer Ansatz gilt erst als fertig, wenn auf demselben Build nachgewiesen ist:

- zweimal starkes vertikales Scrollen ohne weißen Pane,
- sichtbare Pixel und sichtbare Inhaltselemente nach jeder Geste,
- Play All startet eine normale Musikwarteschlange,
- Top Songs öffnet eine echte Detailroute,
- Zurück bleibt im rechten Pane,
- horizontale Listen bleiben bedienbar,
- die globale ursprüngliche Metrolist-Up-/Down-Geste funktioniert weiterhin,
- kein Crash und kein ANR.

## Teststrategie

Vor weiteren vollständigen GitHub-Action-Läufen soll zuerst ein kleiner lokaler beziehungsweise isolierter Komponententest erstellt werden. Ein kompletter Emulator-/ARM-Build wird erst gestartet, wenn die Architekturhypothese in dieser kleinen Testumgebung bestätigt ist.
