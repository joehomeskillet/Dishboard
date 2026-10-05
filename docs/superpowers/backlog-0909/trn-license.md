# Glossar-Rechte — kein 50k-Fremdbestand

Stand: 9. September 2026. Paket `MP-TRN-LICENSE-SCOPE`. Keine Dependency, keine Übersetzungs-API.

## Eigene Quellen (vorhanden)

| Quelle | Was sie ist | Rechte |
|---|---|---|
| Deutsche UI-Labels in `food_symbols.py`, `template_filters.py`, Templates | Produkttexte der Anwendung | Eigenbestand; erfüllt TRN-001 nicht (fünf Sprachen + Review fehlen) |
| Manuell erfasste Glossarzeilen nach `MP-TRN-SCHEMA` | künftig `glossary_terms` mit `source_kind` in `manual\|file_import\|url` | Nur mit nachvollziehbarer Herkunft; Review ist fachlich, nicht Lizenz |

## Externe / offene Rechte

| Angabe | Status |
|---|---|
| Herstellerumfang «rund 50'000 Begriffe» (BACKLOG / Entwurf §11, 5. September 2026) | Referenzzahl, kein installierbarer Wörterbuchbestand, kein Lizenz-PASS |
| Fremde Gastro-Glossare, Verlagsdaten, maschinelle Übersetzung | Offen; Nutzung erst nach tatsächlichem Rechtebeleg |
| HTTP-Übersetzungs-APIs, Pauli-SDK, Wörterbuchpakete | Nicht freigegeben (operations-sdd §0) |

## Grenze

Kein Plan- oder Herstellerzitat ersetzt eine Lizenz. Keine 50k-Datei ins Repo. Keine neue Dependency. Public/Signage bleiben in Stufe 1 deutsch.
