# PKS / Pauli Nutzungsrechte — Recherchestand

Stand: 9. September 2026. Paket `MP-PKS-RIGHTS-SCOPE`. Kein Adapter, kein Import, keine Credentials.

## Quellen (belegt vs. offen)

| Quelle | Datum | Was sie belegt | Was sie nicht belegt |
|---|---|---|---|
| [Optisoft Produkte](https://optisoft.ch/preise-und-produkte/), [Optisoft](https://optisoft.ch/) | geprüft 5. September 2026 im Entwurf §11 | Anbieter nennt PKS-Serverzugang, Lieferantenimport, Excel-Vorlage für Lieferantendaten, Fremdprogrammexport | Kein Nutzungsvertrag für Dishboard; keine aktuelle API-/Auth-/Formatdoku für diesen Anschluss |
| [Lightspeed-Integration Pauli Kitchen Solution](https://www.lightspeedhq.de/integrationen/paulis-kitchen-solution/) | geprüft 5. September 2026 | Fremdprodukt-Integration existiert bei einem anderen Anbieter | Keine Rechte für Klinik Südhang / Dishboard |
| [Pauli-Verlag](https://pauliph.com/) | geprüft 5. September 2026 | Verlagskatalog und PKS-Bestand sind getrennte Angebote | Kein Lizenzbeleg für Rezeptübernahme |
| [Fremdprogrammexport, Juni 2021](https://optisoft.ch/wp-content/uploads/2021/06/Export-Fremdprogramme.pdf) | Juni 2021 | Historische Exportbeschreibung Rezepte/Gerichte/Menüs samt Zutaten, Nährwerten, Allergenen | Kein aktueller API-Nachweis 2026 |
| [Produktübersicht, Juni 2023](https://optisoft.ch/wp-content/uploads/2023/06/230616_Produktuebersicht-und-Preise.pdf) | Juni 2023 | Warenkorbbefüllung, Mengenübernahme, Lager, Inventur als Produktbeschreibung | Keine unbeaufsichtigte Bestellung; kein Rechtebeleg |
| Operations-SDD §6 / BACKLOG REC-004 | 9. September 2026 | Herstellerzahl «über 4'400 PKS, davon 1'655 Pauli» ist Referenz | Kein importierbarer Bestand, kein Test-PASS, keine Datei im Repo |

## Rechtsstatus

**Unbekannt, bis ein Betreiberbeleg vorliegt.** Es gibt in diesem Repository keine Lizenz, keinen Vertrag, keine Exportberechtigung und keine berechtigte PKS-/Pauli-Datei.

Ohne diesen Beleg:

- kein Mapping-WP (`MP-PKS-FIELD-MAP`) READY
- kein Export-Fixture (`MP-PKS-EXPORT-FIXTURE` bleibt `AWAITING_EXTERNAL`)
- kein Adapter, der 4400 oder 1655 Rezepte behauptet oder einspielt

`recipe_import.py` bleibt der bestehende Previewparser. Dieses Dokument ändert ihn nicht.

## Nächster Blocker

Eine vom Betreiber berechtigte Exportdatei plus Versionsangabe unter `reference_scaffold/tests/fixtures/pks/`. Ohne Datei kein Mapping.
