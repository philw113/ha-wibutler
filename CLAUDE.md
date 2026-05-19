# srv-home-pve-ha-home-wibutler · CLAUDE.md

@../CLAUDE.md

## Repo-spezifisch
Sub-Projekt im Workspace `srv-homelab`. Workspace = Concept-Repo (eine Ebene drüber). Vollständige Workspace-Anweisungen in `../CLAUDE.md` (via `@`-Import oben).

**Dieses Repo ist ein Fork** von [patrickweh/ha-wibutler](https://github.com/patrickweh/ha-wibutler) mit lokalen Anpassungen. Siehe `FORK-NOTES.md` für die Drift zum Upstream.

## Kontext
Fachliche Ressourcen im Workspace + Parent-Sub-Projekt:
- Aktueller Workspace-Stand: `../STATUS.md`
- Service-Übersicht: `../docs/services.md`
- HA-Sub-Projekt: `../srv-home-pve-ha-home/`
- HA-Inventur: `../srv-home-pve-ha-home/docs/inventur.md`

## Notion
- Projekt-Workspace: https://www.notion.so/35a7f820f55c815d93b5d6eb881d4ccd (PRJ-10)
- Notion-Sub-Projekt: *(nachzutragen nach REP-Anlage)*
- GitHub (Fork): https://github.com/philw113/ha-wibutler
- GitHub (Upstream): https://github.com/patrickweh/ha-wibutler

## Was ist drin
Fork der Custom-Integration **Wibutler** für Home Assistant. Wird in der laufenden HA-Instanz unter `/config/custom_components/wibutler/` (auf HAOS: `/mnt/data/supervisor/homeassistant/custom_components/wibutler/`) deployed und ist damit der Code-Stand, der die Wibutler-Hub-Anbindung in HA realisiert.

## Stack
- Custom HACS-Integration, Python 3.x (in HA-Container 3.14)
- aiohttp REST + WebSocket gegen Wibutler-Hub-API
- Komponenten: binary_sensor, climate, cover, light, sensor, switch (+ rocker im Upstream, lokal noch nicht)

## Beziehung zum Upstream
- **Letzter Sync-Punkt:** `cab4be0` (2025-08-26, Merge PR #9 von Fochest)
- **Eigene Commits über Sync-Punkt:** `1e950af` (WiButler 1 Lights), `78a2713` (Ignore BTNRECON)
- **Upstream-Stand seit Sync:** v1.2.0 (Refactor `WibutlerEntity` base class, neue `rocker.py`, `strings.json` + translations, api.py-verify_ssl-Fix). Merge bewusst aufgeschoben — siehe `FORK-NOTES.md`.
- **Lokal nicht committed:** signifikante `climate.py`-Erweiterungen (Mode-Komponenten-Logik) — werden mit AUF-* nachgeholt.

## Deploy
Der Code lebt produktiv in der HAOS-VM 110 unter `/mnt/data/supervisor/homeassistant/custom_components/wibutler/`. Aktuell **kein automatisches Deploy** — nach Commits wird per `scp`/`qm guest exec` von Hand übertragen und HA neugestartet.

## ⚠️ Read-only-Default (vom Parent-Sub-Repo geerbt)
Default: keine Änderungen am laufenden HA. Code-Änderungen hier im Repo committen erst — Deploy auf VM nur auf explizite Philipp-Freigabe, Plan Mode + Proxmox-Snapshot Pflicht vor Deploy.

## ⚠️ Keine Secrets
Wibutler-Hub-Zugangsdaten (Username/Passwort/IP) leben in der HA-Config-Entry, nicht im Code. `.env` für lokale Tests ist via `.gitignore` raus.

## Modul-Architektur
Siehe `MODULES.md`.

## Test-Strategie
Keine automatisierten Tests. Verifikation auf der laufenden HA-Instanz (Wibutler-Entitäten verfügbar, Statuswechsel kommen an).

## Auto-Push-Policy
**Auto-Commit:** ja
**Auto-Push:** ja
**Begründung:** Sub-Projekt-Typ `service` — Code-Repo, lokal entwickelt, gepushter Stand wird per Hand auf HA deployed (Deploy ist separater Schritt mit Freigabe).

Sicherheitsnetz: Pre-Commit-Scan auf Secrets, sensible Datei-Endungen Bestätigung, Force-Push nie automatisch.

## Auto-Maintenance Routine

**Bei Beginn der Session:**
- `../STATUS.md` lesen
- `FORK-NOTES.md` lesen (Drift-Stand)
- Aktive Notion-AUFs für dieses Sub-Projekt prüfen

**Bei signifikanter Änderung:**
1. Committen (Conventional Commits)
2. `FORK-NOTES.md` aktualisieren, falls Drift zum Upstream verändert
3. `../STATUS.md` aktualisieren (kurze Zeile)
4. Auto-Push aktiv — Deploy auf HA bleibt separate Freigabe
