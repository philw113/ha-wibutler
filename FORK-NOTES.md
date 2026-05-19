# Fork-Notes — Drift zum Upstream

**Letztes Update:** 2026-05-19
**Notion-REP:** [REP-26](https://www.notion.so/3657f820f55c814ba31ace4847bbe88f)

## Sync-Punkt
Letzter Merge-from-Upstream: `cab4be0` (2025-08-26, Merge PR #9 von Fochest).

## Eigene Commits über Sync-Punkt (im Fork-`main`)
- `1e950af` (2025-11-04) — Improve WiButler 1 lights and button handling
- `78a2713` (2025-11-04) — Ignore BTNRECON in binary sensor setup

## Lokal noch nicht committed (Live-VM-Stand vs. Fork-`main`)
- `custom_components/wibutler/climate.py` — **+331 Zeilen lokal**: erweiterte Mode-Komponenten-Logik (`RTSPMODE`/`_prf_*_RTSPMODE`, `CTSP`/`_prf_*_CTSP`, `ETSP`/`_prf_*_ETSP`, Preset Comfort/Eco). Wird mit AUF-* in den Fork gehoben.
- `custom_components/wibutler/binary_sensor.py`, `light.py` — nur Encoding-Drift (Mojibake auf VM), inhaltlich identisch zum Fork.

## Upstream-Stand vs. Fork
- Upstream `main` ist auf v1.2.0 (Stand 2026-03-07): 7 Commits voraus, 2 zurück, status `diverged`.
- Wesentliche Upstream-Änderungen seit Sync-Punkt:
  - `fcb02db` (2026-01-22) — Update api.py: verify_ssl-Fix + Content-Type-Check
  - `d189ef4` (2026-03-05) — Refactor: WibutlerEntity base class (16 Files berührt)
  - `5d58fb3` (2026-03-07) — Neue `rocker.py` (Rocker-Button-Events + Options-Flow)
  - Neue Files: `entity.py`, `rocker.py`, `strings.json`, `translations/de.json`, `translations/en.json`

## Warum kein Upstream-Merge jetzt
- `climate.py` ist lokal stark überarbeitet (siehe oben) — Upstream-Refactor würde konfliktieren
- Aktueller Bugfix-Bedarf ist orthogonal zum Upstream-Refactor
- Merge wird als eigene AUF eingeplant, nachdem lokale climate.py-Erweiterungen committed sind

## Bekannte Probleme
- ~~**JSONDecodeError beim Setup** seit HA Core 2026.5.1~~ — gefixt 2026-05-19 via `api.py`-Patch (`response.json()` → `json.loads(await response.text())`).
- ~~**ImportError `SUPPORT_BRIGHTNESS`** in `light.py` seit HA Core 2026.5~~ — gefixt 2026-05-19: migriert auf `_attr_supported_color_modes = {ColorMode.BRIGHTNESS}` + `_attr_color_mode = ColorMode.BRIGHTNESS`.
