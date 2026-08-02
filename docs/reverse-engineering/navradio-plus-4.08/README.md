# NavRadio+ 4.08 – statische Dudu7-/FYT-Referenz

Diese Ablage sichert den für MetroList dudu7 relevanten, dekompilierten NavRadio+-Stand dauerhaft im Repository. Sie ersetzt frühere Chat-Zusammenfassungen als technische Referenz und gehört zu Issue #75 sowie zur Fehleranalyse #58.

## Was dauerhaft gespeichert ist

- Prüfsummen und Paket-/Versionsdaten der bereitgestellten XAPK
- reproduzierbares XAPK/APK/DEX-Extraktions- und Indexierungswerkzeug
- Klassen-/Methodenindex der relevanten NavRadio-, FM-, Syu-, QF- und Vendor-Key-Pakete
- lesbarer Pseudo-Smali-Codeauszug der verifizierten Geräte-, Service-, MediaSession- und Sendernavigationspfade
- direkte Zuordnung der wichtigen Methoden anhand ihrer DEX-Methoden-ID
- Kontextlink zum Entwicklerthread bei XDA

Die XAPK/APK selbst wird nicht in das öffentliche Repository eingecheckt. Ebenso wird nicht der vollständige proprietäre Drittanbieter-Code veröffentlicht. Der gespeicherte Referenzausschnitt deckt den für Interoperabilität, Dudu7-Tuneransteuerung und Lenkradtasten notwendigen Code ab. Mit dem Skript kann eine lokal vorhandene, hashgleiche XAPK erneut vollständig indexiert werden.

## Quellstand

| Merkmal | Wert |
|---|---|
| Paket | `com.navimods.radio` |
| App | NavRadio+ |
| Version | `4.08` |
| VersionCode | `1088` |
| XAPK SHA-256 | `4e362521d4b3bb093e32fc71dc16836ab1259ec38047dc4619958caa44a723c8` |
| Basis-APK SHA-256 | `9f28fd88d4df40920a4fae85f71c1e7975437b2af2b15c7a67005b581ceddf9f` |
| `classes.dex` SHA-256 | `3b76fbe9660d66b47936323b71739976e1e157bd01f1b8208c7757d19fdc6e5c` |
| DEX-Klassen | 8.061 |
| DEX-Methodenreferenzen | 49.198 |

Weitere Splits und Zähler stehen in `source-manifest.json`.

## Verifizierter Dudu7-/UIS7870-Codepfad

### 1. Geräteerkennung

`Lcom/google/gson/internal/c;->h()V` erkennt:

- Dudu über `Build.BRAND == "DUDUAUTO"` beziehungsweise `ro.customize.brand`
- UIS7870 über `ro.fota.platform == "SC7870"` oder ein mit `uis7870` beginnendes `ro.product.device`
- FYT zusätzlich über Gerätefamilien wie `uis7870`, `ums512`, `uis8581`, `sp9853i` und `sp7731e`

`RadioService.<init>()` übernimmt diese Ergebnisse getrennt nach `isDUDU7`, `is7870`, `isFYT7862` und `isQF01`.

### 2. Auswahl des Backends

Die Backend-Auswahl in `RadioService.g(RadioService)` ist eindeutig:

- `isFYT7862 == true` ruft `RadioService.x()` auf
- `isQF01 == true` ruft separat `RadioService.y()` auf

Damit darf das bloße Vorhandensein von QF- oder TWUtil-Klassen nicht als Beleg für deren Verwendung auf Dudu7 interpretiert werden.

### 3. Dudu7-/FYT-Tunerpfad

`RadioService.x()`:

- prüft auf Dudu7/UIS7870 das Paket `com.syu.music` mit App-Bezeichnung `Media`
- prüft beim älteren FYT-Pfad `com.syu.radio` mit App-Bezeichnung `RadioProxy`
- erstellt anschließend `com.android.fmradio.FmService`
- registriert den FYT-Empfänger

`RadioService.init()` überspringt den TWUtil-Block, sobald der FYT-Schalter aktiv ist. TWUtil ist damit kein Dudu7-/UIS7870-Tunerbackend dieser APK.

### 4. MediaSession und Player

`RadioService` erbt von `androidx.media3.session.MediaSessionService`.

`RadioService.onCreate()` erstellt zuerst den app-eigenen Player `com.navimods.radio.media.b` und baut daraus eine Media3-`MediaSession`. Die Hardwareinitialisierung erfolgt danach. `onGetSession()` gibt diese Session zurück.

Das beweist die Architektur und Reihenfolge. Es beweist für sich allein noch nicht, dass jedes Dudu7-Firmware-Release die Lenkradtaste an diese Session zustellt.

### 5. Next/Previous bis zur NavRadio-Senderliste

Der Playerpfad `com.navimods.radio.media.b->m1(IIJZ)V` setzt Media3-Navigationsbefehle um:

- Previous/Previous Media Item → Broadcast `com.navimods.radio.set.prev_station`
- Next/Next Media Item → Broadcast `com.navimods.radio.set.next_station`

`RadioService.onStartCommand()` beziehungsweise der registrierte Empfänger führen diese Aktionen auf `prevStation()` und `nextStation()`.

Diese Methoden verwenden NavRadios eigene unveränderte Senderliste und einen separat gehaltenen Index:

- Index erhöhen oder vermindern
- am Listenende beziehungsweise Listenanfang umlaufen
- `setStation(index, station)` aufrufen

Damit schalten MediaSession-/UI-Befehle nicht den Tuner-Suchlauf, sondern die app-eigene geordnete Stationsliste.

### 6. QF ist ein separater Hardwaretastenpfad

`RadioService.y()` erstellt `QFService` und registriert QF-spezifische Audio- und Key-Komponenten.

Dort existiert ein direkter Pfad:

`QFService$1.onMediaButtonEvent()` → `IMediaButtonListener` → `QFKeyEventInfo.onReceived()` → `RadioService.m(...)`

`RadioService.m(...)` ordnet unter anderem zu:

- Keycode 87 → `nextStation()`
- Keycode 88 → `prevStation()`

Dieser direkte Listener ist im Code an das QF-Backend gebunden. Er darf nicht als Dudu7-/FYT-Beweis verwendet werden.

## Konsequenz für Issue #58

Für Dudu7 zeigt NavRadio+ 4.08 im gesicherten Code:

1. FYT-/Syu-`FmService` als Tunerbackend
2. keine aktive TWUtil-Initialisierung
3. keine QF-Service-Initialisierung allein aufgrund von Dudu7
4. einen echten Media3-`MediaSessionService` mit eigenem Radioplayer
5. Next/Previous des Players führt auf die eigene Senderliste

Im Dudu7-/FYT-Initialisierer wurde kein zusätzlicher direkter Keycode-Callback gefunden, der wie der QF-`IMediaButtonListener` unmittelbar `nextStation()` oder `prevStation()` aufruft. Der explizit sichtbare Dudu7-kompatible Navigationsadapter ist daher der Media3-/Playerpfad. Eine angebliche zusätzliche geheime Binder-Registrierung ist durch diesen Stand nicht belegt.

Offen bleibt die gerätespezifische Zustellung durch `com.syu.ms`. Diese muss weiterhin durch ADB-/Gerätelogs belegt werden. Falls die Taste bei MetroList nicht am FM-Player ankommt, ist zunächst Sessionzustellung beziehungsweise aktiver Player zu prüfen. Erst wenn `FM_PLAYER_COMMAND` ankommt und das Ziel falsch ist, ist die Favoriten-/Indexlogik die primäre Ursache.

## Dateien

- `source-manifest.json`: Hashes, Paket- und DEX-Metadaten
- `key-symbol-index.txt`: kompakter Index der zentralen Klassen und Methoden; das Skript erzeugt zusätzlich den vollständigen Index mit 509 relevanten Klassen und 2.890 definierten Methoden
- `smali/`: verifizierte Schlüsselmethode als einzelne, direkt in GitHub lesbare Pseudo-Smali-Dateien
- `../../../tools/navradio_reference/extract_navradio_408_reference.py`: reproduzierbares Analysewerkzeug

## Reproduzieren

```bash
python tools/navradio_reference/extract_navradio_408_reference.py \
  /pfad/NavRadio+_4.08_APKPure.xapk \
  --out /tmp/navradio-408-reference \
  --expected-sha256 4e362521d4b3bb093e32fc71dc16836ab1259ec38047dc4619958caa44a723c8
```

Der geprüfte Lauf ergibt:

- 8.061 Klassen
- 49.198 Methodenreferenzen
- 234 direkte Referenztreffer
- 423 automatisch ausgewählte Methoden

## Grenzen

- Die Ausgabe ist eine statische DEX-Rekonstruktion und nicht der originale Java-/Kotlin-Quelltext.
- Obfuskierte Namen bleiben obfuskiert.
- Pseudo-Smali kann bei seltenen Opcodes unvollständig sein; die hier dokumentierten Schlüsselflüsse wurden zusätzlich direkt anhand der DEX-Referenzen, Sprungziele und Aufrufer geprüft.
- Laufzeitverhalten von Herstellerdiensten kann nur am Gerät vollständig bewiesen werden.
- Dieses Referenzpaket dient ausschließlich der Analyse und Interoperabilität von MetroList dudu7.

## Externer Kontext

Entwicklerthread von KoTiX2:

https://xdaforums.com/t/dev-new-navradio-ported-to-uis7862-uis7870-and-other-fyt-devices.4387965/

Der Thread beschreibt die Portierung auf FYT-Geräte mit UIS7862, UIS7870, UIS8581, sc9853i und sc9863a und enthält Dudu7-Gerätetests sowie Hinweise zu Lenkradtastenänderungen in früheren Versionen.
