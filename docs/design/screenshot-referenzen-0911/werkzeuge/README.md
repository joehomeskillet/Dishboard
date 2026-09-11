# Optionale Reproduktion der Referenzbilder

Die fertigen PNGs und `../ANSICHTEN.html` können ohne Python verwendet werden. Die Skripte sind ausschliesslich zur Reproduktion der isolierten Designreferenzen bestimmt, nicht zur Änderung der Klinik-Anwendung.

Aus dem Wurzelordner des entpackten Pakets:

```shell
python werkzeuge/build_mockups.py
python werkzeuge/render_mockups.py
```

`build_mockups.py` erzeugt die sechs HTML-Seiten und die gemeinsame CSS-Datei neu. Der mitgelieferte Logo-Ausschnitt muss erhalten bleiben. Python-Standardbibliothek genügt.

`render_mockups.py` verwendet separat vorhandenes Playwright und einen kompatiblen Chromium. Es kann ein bereits installierter Browser ausdrücklich angegeben werden:

```shell
python werkzeuge/render_mockups.py --chromium "/pfad/zum/chromium"
```

Kein automatisches Nachinstallieren und keine Änderung der Produktionsabhängigkeiten. Die Referenzdateien werden lokal gelesen und für den Browser eingebettet; es sind keine externe Website und kein lokaler Webserver erforderlich. Es findet kein Login oder schreibender Vorgang statt.

Das Rendering überschreibt die acht erzeugten PNGs und die Rendermetadaten, **ändert aber keine Bildfreigaben**. Nach gestalterischen Änderungen neue Fassungen unter neuen Namen ablegen und die führende Referenztabelle ausdrücklich aktualisieren. Die Vergleichstafeln sind statische Zusatzartefakte; sie werden durch diese beiden Befehle nicht automatisch neu zusammengesetzt.
