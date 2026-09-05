# Backlog

## API-001 — REST-API v1, MCP, FHIR R5 und API-Schlüssel

**Status:** Auf Nutzerwunsch ins Backlog verschoben (2026-09-05). Wiederaufnahme nach dem Produktionswechsel auf v16/Tabler; dieser bleibt vorrangig. Vorhandene API-Arbeiten erhalten, jetzt keine Lanes starten oder einsammeln.

**Umfang:** Dokumentierte REST-API v1 mit OpenAPI 3.1 und lokalem Swagger UI, FHIR-R5-Leseschnittstelle, MCP-Server sowie API-Schlüssel mit Admin-Verwaltung unter `/admin/api`.

**Quellen und vorhandene Planung:**

- Übergabe: `/nvmetank1/projects/menuplan/UEBERGABE-CODEX-API-2026-09-05.md` (insbesondere §4 und §6); dortige Lane-Stände bei Wiederaufnahme neu prüfen.
- Koordination: `/nvmetank1/projects/menuplan/KOORDINATION-API-CODEX-2026-09-05.md` für Dateigrenzen, Migration und Sidebar-Vertrag.
- Spec: `docs/superpowers/specs/2026-09-05-dishboard-api-mcp-fhir-design.md`, Branch `docs/api-mcp-fhir-spec-0905`, Commit `5e4750f`.
- Briefs und Logs: `.claude/state/api-mcp-fhir-0905/`.

**Reihenfolge bei Wiederaufnahme:**

1. Gemäß Übergabe §4 vorhandene Lanes sammeln: Abschlusslogs, Reports, Worktree-Status und Commits prüfen. Root wiederholt die jeweiligen Gates und Ruff selbst und committet erst danach. Fremde Änderungen und bestehende API-Worktrees erhalten; keine Quoten-Vorabprüfung oder Ausschlüsse anhand gespeicherter Quotenstände.
2. Welle 1 in `.claude/worktrees/api-integration-0905` auf Branch `integrate/api-mcp-fhir-0905` vervollständigen: Schema/Schlüssel-Store D, REST A1 und FHIR B integrieren; vorhandene Spec-, MCP-, Swagger- und Dokumentationsänderungen berücksichtigen.
3. Kombiniertes Gate aus §6 einschließlich Gesamtsuite, Ruff, Schema- und Swagger-Asset-Prüfung ausführen; anschließend Security-Review und unabhängiges Cross-Vendor-Review. **Der dort genannte alte `gate.sh`-Aufruf darf nicht blind ausgeführt werden:** Der bekannte alte Root-Wrapper verweist auf eine gelöschte Datenbank. Vorher gegen aktuell vorhandene Wrapper und eine tatsächlich verfügbare isolierte Testdatenbank prüfen. Fehlende DB-Umgebung beziehungsweise deswegen übersprungene DB-Tests sind kein grüner Nachweis.
4. Erst nach erfolgreicher Welle-1-Prüfung Welle 2 über `brief-e.md` und `brief-g.md` aufnehmen: Admin-Verwaltung und schlüsselgeschützte Endpunkte in eigenen Worktrees; Sidebar und Rendertests gemäß Spec ergänzen.
5. Rebase auf `main` erst nach dem v16/Tabler-Merge. Manifest aktualisieren, vollständige Offline-Paketprüfung ausführen und die Swagger-Verifikation aus Koordination §2.6 klären.
6. Deployment nach dem bestehenden Runbook vorbereiten: Backup, kontrollierte Migration **16→17**, danach Smokes für `/api/v1/status`, `/api/v1/docs`, `/fhir/metadata` und authentifiziert `/admin/api`. Schlüssel ausschließlich über die Admin-Verwaltung erzeugen; Klartext nicht in Chat oder Logs übernehmen.
