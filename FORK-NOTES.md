# Fork-Notes — Drift zum Upstream

**Letztes Update:** 2026-05-19
**Notion-REP:** [REP-26](https://www.notion.so/3657f820f55c814ba31ace4847bbe88f)
**Pflege-Strategie:** [ADR-001](docs/decisions/001-fork-pflege-strategie.md)

## Sync-Punkt
Letzter Merge-from-Upstream: `cab4be0` (2025-08-26, Merge PR #9 von Fochest).

## Eigene Commits über Sync-Punkt (im Fork-`main`)
- `1e950af` (2025-11-04) — Improve WiButler 1 lights and button handling
- `78a2713` (2025-11-04) — Ignore BTNRECON in binary sensor setup
- `de49e3f` (2026-05-19) — docs: sub-project documentation
- `47e46d5` (2026-05-19) — feat(climate): extended mode/preset handling with CTSP/ETSP fallbacks
- `d21626d` (2026-05-19) — fix(api): work around aiohttp response.json() crash on large responses
- `8b523a8` (2026-05-19) — fix(light): migrate SUPPORT_BRIGHTNESS to ColorMode for HA 2026.5

## Upstream-Stand vs. Fork
- Upstream `main` ist auf v1.2.0 (Stand 2026-03-07): mehrere Commits voraus, 2 zurück, status `diverged`.
- Wesentliche Upstream-Änderungen seit Sync-Punkt:
  - `fcb02db` (2026-01-22) — Update api.py: verify_ssl-Fix + Content-Type-Check
  - `d189ef4` (2026-03-05) — Refactor: WibutlerEntity base class (16 Files berührt)
  - `5d58fb3` (2026-03-07) — Neue `rocker.py` (Rocker-Button-Events + Options-Flow)
  - Neue Files: `entity.py`, `rocker.py`, `strings.json`, `translations/de.json`, `translations/en.json`

## Pflege-Strategie (siehe [ADR-001](docs/decisions/001-fork-pflege-strategie.md))
- **HACS-Custom-Repo pollt diesen Fork**, nicht Upstream → kein „Update verfügbar"-Banner-Spam
- **Manifest-`version`-Schema:** `<upstream-base>+philw113-fork-<YYYY-MM-DD>` (PEP-440-Build-Metadata, vom Semver-Vergleich ignoriert). Aktuell: `1.0.1+philw113-fork-2026-05-19`.
- **Upstream-Awareness via GitHub-Action** `.github/workflows/upstream-watch.yml` → ntfy-Push an `srv-homelab-pve-...`-Topic (Montags 09:00 UTC, manuell triggerbar im Actions-Tab)
- **Letzter gesehener Upstream-SHA** in `.github/upstream-last-seen` (aktuell: `cf8916bc` = Patrick's „Bump version to 1.2.0" vom 2026-03-07)
- **Reagier-Karte in Notion:** [AUF-208](https://www.notion.so/3667f820f55c81ceba2ae2747d3d97b2) (Status: Wartet) — Sync-Prozess, Festlegungen, Diskussions-Log bei ntfy-Hits

## Sync-Prozess (wenn ntfy meldet)
```bash
cd srv-home-pve-ha-home-wibutler
git fetch upstream main
git merge upstream/main            # Konflikte in climate.py erwartet
# Konflikte auflösen (lokale Anpassungen drüber)
# manifest-version bumpen: <neue-upstream-version>+philw113-fork-<heute>
git commit && git push
# HACS bietet Update im HA-UI an → bestätigen → HACS pullt Fork → HA Restart
```

## Warum kein Upstream-Merge jetzt
- `climate.py` ist stark divergiert (96 Z. Upstream vs. 426 Z. lokal) — Upstream-Refactor (`WibutlerEntity`-Basisklasse) garantiert konfliktreich
- Aktuell läuft alles stabil seit Bugfix-Welle 2026-05-19, kein akuter Sync-Anlass
- Sync wird ausgelöst, wenn die GitHub-Action eine ntfy-Notification schickt (= Patrick hat einen neuen Commit gepusht)

## Convention-Abweichung: kein notify-on-failure.yml (CI)
`PROJEKT-PLAYBOOK §12.4 Schritt 4` verlangt für `service`-Repos ein `.github/workflows/notify-on-failure.yml` + Health-Check-Skript-Stub. **Hier bewusst übersprungen**, da:
- Dieses Repo ist ein passiver Fork-Mirror einer HA Custom-Integration — kein klassisches CI/CD
- Der einzige laufende Workflow ist `upstream-watch.yml` (Polling-Bot ohne Build/Test/Deploy), Failures dort sind unkritisch (im Worst Case verpassen wir einen Upstream-Hinweis, der sich beim nächsten Lauf nachholt)
- Der „Live"-Stand läuft in der HA-VM 110 (`/config/custom_components/wibutler/`), nicht im Repo — Health-Monitoring der Integration findet auf HA-Ebene statt (HA Repairs, Logs, Entity-States)

Falls künftig CI (Pre-Deploy-Lint, Tests, etc.) hinzukommt: nachpflegen.

## Bekannte Probleme
- ~~**JSONDecodeError beim Setup** seit HA Core 2026.5.1~~ — gefixt 2026-05-19 via `api.py`-Patch (`response.json()` → `json.loads(await response.text())`).
- ~~**ImportError `SUPPORT_BRIGHTNESS`** in `light.py` seit HA Core 2026.5~~ — gefixt 2026-05-19: migriert auf `_attr_supported_color_modes = {ColorMode.BRIGHTNESS}` + `_attr_color_mode = ColorMode.BRIGHTNESS`.
