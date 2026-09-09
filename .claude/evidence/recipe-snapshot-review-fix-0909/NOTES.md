# Private Notiz — wp-6c2cc5130438 (M1, L1, L2 aus der Snapshot-v2-Review)

Worktree `recipe-snapshot-review-fix-0909`, Branch `fix/recipe-snapshot-review-0909`,
Basis `ac424a6041ed92e50725351c057bcca21b798d37`. Ursprünglicher Autor der
Snapshot-v2-Strecke ist ein anderer; dieses WP behebt ausschliesslich die drei
Befunde aus `/nvmetank1/projects/rag-stack/.claude/reports/wp-4e2f8700157e.md`.
Kein SQL, keine Grants, kein DTO, keine Lesetransaktion, kein kanonischer Hash,
kein Closure-Limit, keine API, kein Auth/CSRF, keine Route, kein Freeze-Write.

## M1 — unvollständige v1-Kinder im v2-Verschluss

`_body` hat die Vollständigkeit nur für v2-Körper geprüft. Derselbe `_body`
behandelt aber auch die v1-Kinder aus `index`, und `recipe_payload` lässt
historische Lücken bewusst zu. Damit akzeptierte `verified_prepared` einen
v2-Elternstand, dessen unveränderliches v1-Kind NULL-Food, NULL-Menge oder gar
keine Zutaten hatte.

SQL27 ist an dieser Stelle strenger: `0024_v26_to_v27.sql:319-321` ruft
`recipe_snapshot_complete_v27(body)` für **jeden** Knoten der Warteschlange auf,
und zwar **vor** dem v1-terminalen `CONTINUE` in Zeile 329. Die Funktion selbst
(Zeilen 69-86) verlangt 1..64 Zutaten, je Zutat eine UUID in `food_public_id`,
einen `unit_code` nach `^[A-Z][A-Z0-9_]{0,15}$` und ein gültiges
`master_quantity`.

Die Python-Seite muss dafür nur die Prüfung aus dem v2-Zweig herausziehen: die
Obergrenze 64 kommt bereits aus `rows()`, und `quantity_pair()` bindet Menge und
Einheit ohnehin aneinander und validiert beide. Übrig bleibt genau
„nicht leer, jede Zutat verknüpft und beziffert". Die Mengengleichheit
`set(foods) == {food_public_id}` bleibt v2-spezifisch, weil SQL27 die Foods-Suche
für v1 gar nicht erst erreicht.

Standalone-v1 bleibt unberührt: `recipe_reads._get_revision_connection` ruft den
v2-Pfad nur bei `schema_version == 2` auf, und `reconstructed_snapshots` weist
jede andere Wurzelversion sofort ab. Ein historischer v1-Stand erreicht `_body`
also nie.

## L1 — Zeitstempel

`rezepte_revision.html:13` hat `created_at.strftime('%d.%m.%Y, %H:%M %Z')`
benutzt und damit UTC angezeigt. Der Filter `datetime_short` aus
`template_filters.py:33-41` existiert bereits, rechnet nach Europe/Zurich und ist
in `routes.py` registriert. Der v1-Zweig mit `isoformat()` bleibt unverändert.
Beleg: `screens/recipe-v2-1440-viewport.png` zeigt „Erstellt am 09.09.2026 04:03"
bei einem UTC-Zeitpunkt von 02:03.

## L2 — Hinweistext

`amount_form` behauptete pauschal „keine Einheitenumrechnung". Für v2 stimmt das
nicht: `admin/recipe_scaling.py:78-79` rechnet die erfassten Zubereitungen mit
`convert(...)` zwischen Elterneinheit und Kind-Ausbeuteeinheit um, unter
Verwendung der festgehaltenen Dichte bzw. des Stückgewichts.

Gelöst über den begrenzten optionalen Makroparameter `converts_units=false`. Nur
`rezepte_revision.html` setzt ihn, und zwar über `calculated.prepared` — also
genau dann, wenn tatsächlich erfasste Zubereitungen angezeigt und umgerechnet
werden. Der Entwurfsaufruf in `rezepte_scale.html:26` bleibt unverändert und
behält den alten Wortlaut. Kein neues Styling, keine neue Palette.

Nicht angefasst: die Modul-Dokzeile `admin/recipe_scaling.py:1` sagt weiterhin
„no unit conversion or persistence" und ist für den v2-Zweig ebenfalls ungenau.
Die Datei gehört nicht zu diesem WP; gemeldet, nicht geändert.

## Tests

- `test_recipe_pdf.prepared_revision` erzeugte ein v1-Kind mit `food_public_id`
  `None` — genau der Zustand aus M1. Das Kind ist jetzt vollständig; die
  Fixture repräsentiert damit einen gültigen Verschluss.
- Drei Offline-Regressionen (`incomplete_child`) bauen die Fixture mit NULL-Food,
  NULL-Menge+Einheit und leeren Zutaten neu auf. Pin, Indexhash und kanonischer
  Text bleiben dabei durchgehend konsistent, damit die Vollständigkeit der
  einzig verbleibende Ablehnungsgrund ist.
- `test_complete_captured_v1_child_is_still_reconstructed` hält fest, dass der
  gültige Fall weiterhin durchgeht und das Kind wirklich v1 ist.
- `test_real_reader_rejects_an_incomplete_captured_v1_child` ist der
  End-to-End-Beweis über die bestehende privilegierte PG-Korruptionsfixture: ein
  zusätzlicher, selbst korrekt gehashter Revisionsdatensatz mit unvollständigem
  eingebettetem v1-Kind wird abgewiesen, während beide Originalzeilen unverändert
  bleiben (`state(owner)` vor und nach dem Lesen identisch).
- Die historische Abdeckung unvollständiger **standalone**-v1-Stände ist
  unverändert erhalten; nichts davon wurde zu einem Erfolgsfall normalisiert.

## Offener Punkt aus dem Poolwechsel

Der erste Gate-Versuch scheiterte mit `connection refused`, weil die Lane-Env auf
den alten Port zeigte, während der Container nach dem DiskFull-Ereignis neu
erstellt worden war. Ich habe weder die Env-Datei angefasst noch einen eigenen
Connection-String gebaut, sondern gemeldet. Root hat den Pool korrigiert; der
zweite Lauf über denselben Wrapper lief durch.
