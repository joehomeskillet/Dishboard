# Lokale Tabler-Assets

Gepinnt: **@tabler/core 1.5.0** und **@tabler/icons 3.46.0**, beide MIT.
Die maschinenlesbare Paketdefinition und Lockdatei `tabler.lock.json` enthält
Quell-URLs, Versionen, npm-SHA-512-Integrität, SHA-256 aller Quellen und Ausgaben
sowie die geordnete Auswahl von 28 Icons. Keine `latest`-Abhängigkeit.

## Reproduzieren

Vom Projektverzeichnis:

```sh
rtk python3 tools/vendor_tabler.py --build
rtk python3 tools/vendor_tabler.py --verify
```

Ein frischer Build ausserhalb des Projekts:

```sh
rtk python3 tools/vendor_tabler.py --build --output-dir /tmp/dishboard-tabler-build --cache-dir /tmp/dishboard-tabler-sources
rtk python3 tools/vendor_tabler.py --verify --output-dir /tmp/dishboard-tabler-build
```

`--build` prüft sämtliche Quellen und Ausgaben vor dem ersten Dateiersatz und
schreibt nur Änderungen. `--verify` arbeitet ohne Netzwerk und Schreibzugriff.
Der optionale Cache wird bei jeder Verwendung erneut geprüft. Hashfehler brechen
ab; das Werkzeug passt Lockwerte nie automatisch an. Nur Python-Standardbibliothek,
kein npm-Installieren oder Ausführen von Paketskripten. Einzelne bekannte
Tar-Mitglieder werden im Speicher gelesen, niemals mit `extractall` ausgepackt.

## Ausgelieferte Dateien

- `tabler/tabler.min.css`: unverändertes `package/dist/css/tabler.min.css`.
- `tabler/tabler.min.js`: unverändertes `package/dist/js/tabler.min.js`;
  SHA-256 `0273fadc362ae4ddc8b68e9bd1fd98ae7c835b82fd9b6a4ff6ae2b7064839e55`.
- `tabler/LICENSE`: MIT-Lizenz aus dem offiziellen Core-1.5.0-Tag.
- `tabler-icons/tabler-icons.svg`: deterministischer Sprite aus den offiziellen
  Outline-SVGs; Namen und Reihenfolge im Lock.
- `tabler-icons/LICENSE`: unveränderte Paketlizenz.

Bestehende CSS-, Sprite- und Lizenzbytes bleiben erhalten. Keine Kerndatei wird
umgeschrieben. Source Maps sind Entwicklungsdateien und werden nicht ausgeliefert.
Tabler enthält die Bootstrap-Komponenten; kein zweites Bootstrap-Bundle laden.

## Einbindung

Die neue Admin-Basis lädt `tokens.css`, Tabler-CSS, `admin-tabler.css` und
`menu-images.css`; danach Tabler-JS und `admin.js` geordnet mit `defer`.
Public, Login, Vorschau und Signage laden `tokens.css`, `app.css` und
`menu-images.css`, ohne Tabler-Kerndateien. Assets und Fira-Sans-Schriften sind lokal.

[Tabler 1.5.0](https://github.com/tabler/tabler/releases/tag/@tabler%2Fcore@1.5.0)
nennt Chrome 123, Firefox 128 und Safari 17.5 als Mindestversionen. Die tatsächliche
XCover-Browserversion gehört ins Geräteabnahmeprotokoll.
[Installationsdokumentation](https://docs.tabler.io/ui/getting-started/installation).
