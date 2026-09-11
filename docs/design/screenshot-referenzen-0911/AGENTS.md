# AGENTS.md — Bildreferenzen und verbindlicher UI-Auftrag

Dieses Paket ergänzt vorhandene Projektanweisungen. Es ersetzt keine bestehende Projekt-`AGENTS.md` und erlaubt keine Änderung des technischen Unterbaus.

## Pflichtlektüre

Lies zuerst [UI_REFERENZEN.md](UI_REFERENZEN.md), dann [KRITIK_UND_NACHBESSERUNG.md](KRITIK_UND_NACHBESSERUNG.md), [das UI/UX-Konzept](grundlagen/UI_UX_KONZEPT.md) und [die ursprünglichen Agentenregeln](grundlagen/AGENTS_UI_UX_REFERENZ.md). Untersuche vor Änderungen die tatsächlichen Templates, Formularwege und vorhandenen Prüfregeln im Projekt.

## Regeln für die Referenzen

1. Die zentrale Tabelle in `UI_REFERENZEN.md` ordnet Ist, Soll und Freigabe zu. Nicht allein Dateiname, Änderungsdatum oder eine Datei namens „final“ bestimmen das Soll.
2. Sieh dir die tatsächlich vorhandenen Bilder an. Ein Dateipfad in einer Tabelle beweist keine vorhandene Datei. Eine Datei beweist keine Freigabe.
3. `ist/` ist Beobachtungsmaterial; `soll/` enthält ergänzbare Designziele; `umgesetzt/` ist für echte spätere Browsernachweise. Diese drei Rollen nicht vermischen.
4. Der Entwurf X1 ist ausdrücklich nicht freigegeben. Keine zusätzlichen Menüarten, falschen Kennzahlen, 14-Punkte-Navigation oder dominante Essensbilder daraus übernehmen.
5. Bei fehlendem Sollbild gelten die Textanforderungen weiterhin. Setze belegte, unabhängige Verbesserungen um; die visuelle Übereinstimmung bleibt offen. Erfinde kein Sollbild und markiere nichts selbst als vom Benutzer freigegeben.
6. Ein freigegebenes Bild bestimmt nur die ausdrücklich freigegebenen visuellen Bereiche. Es ändert weder fachliche Regeln noch Datenmodelle, Rollen, URLs oder Formularverträge.
7. Flask und Tabler bleiben. Keine neuen Frameworks, Abhängigkeiten, APIs, Datenfelder, Berechtigungs- oder Prüf-/Publikationsregeln. Sicherheitsregeln und Formulardaten erhalten.
8. Kernaufgaben müssen für technisch sehr unerfahrene Benutzer durch sichtbare, beschriftete Aktionen funktionieren. Keine Hover-, Doppelklick- oder Drag-and-Drop-Pflicht.
9. Tatsächliche Nachher-Screenshots und Tests selbst prüfen. Kein Mockup als laufende Implementierung ausgeben. Keine ungefragten Produktivänderungen, Testveröffentlichungen oder externen Uploads.
10. Abschluss pro Referenz-ID: Änderung, echte Dateien, erhaltene Verträge, Tests, Nachweis und offene Punkte. Kein pauschales „alles umgesetzt“ ohne Beleg.

Die detaillierten Freigabe-, Konflikt-, Gestaltungs- und Abnahmeregeln stehen in `UI_REFERENZEN.md`. Agenten dürfen Anforderungen nicht abschwächen, damit ein Abschluss grün erscheint.

## Ergänzung: neue Einzelentwürfe

Acht neue Bilder unter `soll/` sind als browsergerenderte statische HTML-Mockups enthalten. Die führende Tabelle kennzeichnet sie als `ENTWURF`. X2 unter `entwuerfe/` ist als Soll verworfen. `vorlagen/` und `werkzeuge/` dienen nur zur Reproduktion dieser Referenzen, nicht als neue Anwendungsarchitektur oder Produktionsabhängigkeit. Keine Demo-Statuswerte, Preise, nicht angebundenen Buttons, Vorschauillustrationen oder Erfassungslogik ungeprüft in das Projekt übernehmen.
