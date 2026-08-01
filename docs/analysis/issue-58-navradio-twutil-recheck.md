# Issue #58 – NavRadio+ TWUtil parity recheck

## Anlass

Gerätetest mit Metrolist dudu7 13.7.39:

- WebRadio-Lenkradtasten funktionieren.
- Bei aktivem FM ändern die Lenkradtasten zwar die reale Frequenz, aber nicht entlang der MetroList-Favoriten.
- Nach dem Tastendruck erscheinen keine `FYT_TW_EVENT`- oder `FYT_TW_ROUTE`-Zeilen.

## Erneute Prüfung von NavRadio+ 4.08

Die XAPK wurde erneut dekompiliert und der FYT-Pfad direkt gegen den aktuellen MetroList-Code verglichen.

### NavRadio+-Architektur

NavRadio+ verwendet **eine einzige gemeinsame `TWUtil(1)`-Instanz** für:

1. Ereignisabonnement,
2. Handlerregistrierung,
3. FYT-Initialisierungsabfragen,
4. Aktivieren/Deaktivieren der FM-Quelle,
5. Empfang der Lenkradtasten.

Der Handler wird mit `Looper.getMainLooper()` erzeugt. Die Initialisierung erfolgt synchron im `RadioService.init()`-Pfad.

### NavRadio+-Initialisierung

Abonnierte Ereignisse:

```text
0x0109, 0x010A, 0x0201, 0x0203,
0x0301, 0x0302,
0x0401, 0x0402, 0x0404, 0x0405, 0x0406,
0x9E00
```

Ablauf:

```text
new TWUtil(1)
open(events)
start()
addHandler("radio", mainLooperHandler)
```

Danach folgen elf `write(...)`-Aufrufe:

```text
write(0x0109, 0xFF)
write(0x010A, 0xFF)
write(0x010A, 0xFF, 1)
write(0x0112, 0xFF)
write(0x010A, 0xFF, 0)
write(0x0301, 0xFF)
write(0x0406, 0)
write(0x0401, 0xFF)
write(0x0404, 0xFF)
write(0x0405, 0xFF)
write(0x0203, 0xFF)
```

Beim Aktivieren der FM-Quelle ruft NavRadio+ über dieselbe Instanz unter anderem auf:

```text
write(0x0301, 0xC0, 1)
write(0x9E00, 1)
write(0x9E11, 0xC0, 1)
```

Beim Deaktivieren werden die entsprechenden Werte zurückgesetzt und anschließend `stop()`/`close()` verwendet.

### NavRadio+-Handler

Der Handler setzt aus Ereignis `0x0301` einen internen Radio-aktiv-Zustand. `0x0201` wird nur bei aktivem Radio weitergegeben:

```text
keyCode = message.arg2
pressType = message.arg1
RadioService.onKeyPress(keyCode, pressType)
```

Standardmapping:

- `(19,1)` nächster Favorit
- `(21,1)` vorheriger Favorit
- `(19,2)` Suchlauf vor
- `(21,2)` Suchlauf zurück

## Abweichungen in MetroList 13.7.39

### 1. Zwei getrennte `TWUtil(1)`-Instanzen

MetroList besitzt bereits in `FytPhysicalRadio.TwUtilBridge` eine `TWUtil(1)`-Instanz für Radio-/Audio-Steuerung.

PR #70 ergänzte zusätzlich `Dudu7FytTwMediaKeys` mit einer zweiten `TWUtil(1)`-Instanz nur für Lenkradtasten.

Damit können zwei Clients mit derselben Client-ID gegeneinander arbeiten. Sehr wahrscheinlich überschreibt oder verdrängt der spätere `FytPhysicalRadio.powerOn()`-Aufruf die vorherige Handlerregistrierung. Das passt exakt zum Gerätetest:

- vor FM ist der Key-Listener möglicherweise registriert,
- beim FM-Start öffnet `FytPhysicalRadio` erneut `TWUtil(1)`,
- anschließend fehlen `FYT_TW_EVENT`-Callbacks,
- die serienmäßige FYT-Umschaltung ändert trotzdem die reale Frequenz.

### 2. Falscher Ereignissatz im bestehenden `FytPhysicalRadio.TwUtilBridge`

Der bestehende Bridge-Code öffnet aktuell:

```text
0x0101 bis 0x0106 sowie 0x0110 bis 0x0115
```

Das entspricht nicht dem NavRadio+-Ereignissatz und enthält insbesondere nicht `0x0201`.

### 3. Abweichende Initialisierungsbefehle

`FytPhysicalRadio.TwUtilBridge.initRadioSequence()` verwendet aktuell andere IDs wie `0x0101`, `0x0102`, `0x0104`, `0x0105` und `0x0110`.

Die NavRadio+-Initialisierung mit `0x0109`, `0x010A`, `0x0301`, `0x040x`, `0x0203` und `0x9Exx` wird nicht vollständig nachgebildet.

### 4. Falscher Thread-/Lifecycle-Aufbau

NavRadio+:

- eine Instanz,
- Handler am Main Looper,
- synchrone Initialisierung im Service-Lifecycle.

MetroList 13.7.39:

- zweite Instanz,
- eigener `HandlerThread`,
- asynchrones `handler.post { initialize() }`.

### 5. Quellenübernahme fehlt im Key-Adapter

`Dudu7FytTwMediaKeys` führt nur `open -> start -> addHandler` aus. Die NavRadio+-`write(...)`-Sequenz und die Aktivierung der FM-Quelle erfolgen dort nicht. Der getrennte Radio-Bridge-Code nutzt wiederum andere Befehle.

## Schlussfolgerung

13.7.39 bildet NavRadio+ **nicht vollständig und nicht architektonisch korrekt** nach. Das Favoritenmapping 19/21 ist zwar richtig, der gemeinsame FYT-Client davor ist jedoch falsch auf zwei Instanzen verteilt.

## Geplanter korrekter Lösungsansatz

1. Die zweite `Dudu7FytTwMediaKeys`-Instanz entfernen.
2. `FytPhysicalRadio.TwUtilBridge` zum einzigen gemeinsamen FYT-Client ausbauen.
3. Exakten NavRadio+-Ereignissatz abonnieren.
4. Handler am Main Looper an derselben Instanz registrieren.
5. Exakte Initialisierungsabfragen und FM-Quellenbefehle ergänzen.
6. `0x0301` als FYT-Radio-Aktivsignal protokollieren und auswerten.
7. `0x0201` über dieselbe Instanz an die MetroList-Favoritenbrücke routen.
8. Jede `write(...)`-Rückgabe und jeden Callback diagnostisch protokollieren.
9. Deduplizierung gegen die parallel beobachtete serienmäßige Tuneränderung vorsehen.
10. Erst nach erfolgreichem Gerätetest Issue #58 schließen.

## Status

Analyse aktualisiert. Noch keine neue Codeänderung nach dem Gerätetest.
