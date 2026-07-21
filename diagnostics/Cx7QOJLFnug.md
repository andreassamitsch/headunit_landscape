# Playback-Diagnose: Cx7QOJLFnug

Datum: 2026-07-21

## Ergebnis

Die Video-ID `Cx7QOJLFnug` wurde ohne Benutzer-Cookies mit yt-dlp 2026.07.04 gegen mehrere YouTube-Player-Clients abgefragt.

- `web_music`: `LOGIN_REQUIRED`
- `android`: `LOGIN_REQUIRED`
- `ios`: `LOGIN_REQUIRED`
- Standard-/Android-VR-Abfrage: `UNPLAYABLE`
- YouTube-Meldung: `Sign in to confirm you’re not a bot`
- Es wurden keine nutzbaren Audioformate ausgeliefert.
- Beim `web_music`-Client wurde außerdem die Bindung des GVS-PoTokens an die konkrete Video-ID erkannt.

## Kontrollvergleich

Als Kontrolle wurde `dQw4w9WgXcQ` im selben Lauf und vom selben GitHub-Runner abgefragt.

- Der Android-Client lieferte Status `public`.
- Format 18 (`mp4`, HTTPS, AAC/H.264) war abspielbar.
- Damit ist die Sperre nicht nur eine allgemeine Blockade der GitHub-Runner-IP.

## Schlussfolgerung

`Cx7QOJLFnug` unterliegt aktuell einer strengeren Login-/Bot-/PoToken-Prüfung als ein gewöhnliches öffentliches Video. Ein anonymer oder von YouTube nicht als vollständig verifiziert akzeptierter Innertube-Client erhält keine Stream-URL. Die offizielle YouTube-Music-App kann den Titel abspielen, weil sie mit einer offiziell verifizierten Google-Sitzung und den aktuellen internen Playback-Tokens arbeitet.
