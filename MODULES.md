# Module dieses Repos

**Letztes Update:** 2026-05-19 durch Claude Code

## Modul-Übersicht

### `custom_components/wibutler/` – HA Custom-Integration
**Zweck:** Code der Wibutler-Integration für Home Assistant
**Abhängigkeiten:** Home Assistant Core, aiohttp
**Optional:** nein
**Status:** Aktiv (Fork-Stand 2025-11-04 + lokale climate.py-Erweiterungen)

Sub-Dateien:
- `__init__.py` – Integration-Bootstrap
- `manifest.json` – HA-Manifest (Domain, Version, Codeowner)
- `config_flow.py` – Setup-UI
- `api.py` – aiohttp REST + WebSocket gegen Wibutler-Hub
- `const.py` – Konstanten
- `binary_sensor.py`, `climate.py`, `cover.py`, `light.py`, `sensor.py`, `switch.py` – Entity-Plattformen

### `FORK-NOTES.md` – Drift-Doku zum Upstream
**Zweck:** Stand der Abweichungen zum Upstream `patrickweh/ha-wibutler` festhalten — was lokal anders, was bewusst nicht gemergt
**Status:** Aktiv

## Modul-Erstellung
Bei neuer Funktionalität durch Claude Code zuordnen:
1. Code-Änderung an Integration → in passendes File unter `custom_components/wibutler/`
2. Doku zur Abweichung → in `FORK-NOTES.md`
3. NIEMALS „irgendwo" einbauen ohne Modul-Klarheit
