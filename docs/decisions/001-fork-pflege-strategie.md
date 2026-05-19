# ADR-001 — Fork-Pflege-Strategie ha-wibutler

**Status:** Akzeptiert
**Datum:** 2026-05-19
**Kontext:** Sub-Projekt-Anlage (REP-26) + Wibutler-Bugfix-Welle HA 2026.5

## Problem

Wir haben einen Fork `philw113/ha-wibutler` vom Upstream `patrickweh/ha-wibutler` mit lokalen Anpassungen (climate.py-Erweiterung um Comfort/Eco-Presets + CTSP/ETSP-Logik, api.py-JSONDecodeError-Workaround, light.py-ColorMode-Migration). Drei Spannungsfelder:

1. **HACS-Update-Banner-Schleife:** HACS pollt Upstream-Manifest (1.2.0) vs. unseren Local-Stand (1.0.0) → ewiges „Update verfügbar", obwohl Update unsere Anpassungen zerstören würde.
2. **Upstream-Awareness:** Wenn wir den Custom-Repo komplett aus HACS entfernen, sehen wir auch Patrick's legitime Bugfixes/Features nicht mehr.
3. **Merge-Konflikte:** climate.py ist stark divergiert (96 → 426 Zeilen), Upstream-Refactor (WibutlerEntity base class) konfligiert garantiert.

## Optionen

| Option | Pro | Contra |
|---|---|---|
| A) Status Quo (HACS pullt Upstream) | nichts zu tun | Banner-Spam, accidental Update zerschießt Stand |
| B) Fork raus aus HACS, scp-Deploy | simpel | Upstream-Awareness komplett verloren |
| C) Two-Branch-Strategie (`main`=Upstream, `local`=Anpassungen) | saubere Trennung | mentaler Tax: zwei Branches, Deploy aus `local` |
| D) **HACS auf Fork umstellen + manueller Sync + Watch-Bot** | HACS-Pipeline bleibt + Updates kontrolliert | Merge-Konflikte bei jedem Sync (selten — Patrick hat 2026 ~3 Commits gemacht) |

## Entscheidung

**Option D.**

### Implementierung

1. **HACS-Custom-Repo umstellen** auf `philw113/ha-wibutler` (User-Action in HACS-UI, einmalig)
2. **Manifest-`version`-Schema:** `<upstream-base>+philw113-fork-<YYYY-MM-DD>` — z.B. `1.0.1+philw113-fork-2026-05-19`. PEP-440-Build-Metadata-Suffix wird vom Semver-Vergleich ignoriert; HACS sieht keinen Update gegen unseren eigenen Fork. Bei Upstream-Sync: Basis-Version mitziehen, neues Datum.
3. **Upstream-Watch via GitHub-Action** (`.github/workflows/upstream-watch.yml`):
   - Cron: Montags 09:00 UTC
   - Fetcht `patrickweh/main`, vergleicht mit `.github/upstream-last-seen`
   - Bei neuen Commits: ntfy-Push an `srv-homelab-pve-a5bb56e899af66e2`-Topic (Topic aus AUF-98) + commit aktuellen SHA in `.github/upstream-last-seen` zurück ins Repo
   - Manuell triggerbar via Actions-Tab „Run workflow"
4. **Sync-Prozess** (manuell, wenn ntfy meldet):
   ```bash
   cd srv-home-pve-ha-home-wibutler
   git fetch upstream main
   git merge upstream/main          # erwartet Konflikte in climate.py, ggf. light.py
   # Konflikte auflösen (lokale Anpassungen wieder drüber)
   # manifest-version bumpen: <neue-upstream-version>+philw113-fork-<heute>
   git commit
   git push
   # HACS bietet Update an → User bestätigt in HA-UI → HACS pullt unseren Fork
   # HA Core restart, Verify
   ```

### Verworfen

- **A** wegen Banner-Spam und Risiko, dass eine unbeobachtete HACS-Update-Bestätigung unsere climate.py zerschießt.
- **B** weil Upstream-Bugfixes (z.B. der `Update api.py`-Commit für verify_ssl) ohne Awareness liegen bleiben würden.
- **C** weil zwei-Branch-Workflow keinen Mehrwert gegenüber D bietet — Konflikte entstehen so oder so an derselben Stelle (climate.py-Merge), und Deploy-Pipeline über HACS ist mit zwei Branches sperriger.

## Konsequenzen

**Positiv:**
- HACS bleibt als Deploy-Mechanismus aktiv — kein `scp` + base64-Pipe-Workaround mehr für jedes Update (außer für Ad-hoc-Patches)
- HACS-„Update verfügbar"-Banner ist still, solange unser Fork-Stand = HA-Stand
- Awareness für Upstream-Bewegung ist via ntfy garantiert, ohne dass Philipp aktiv Upstream-Repo beobachten muss
- Sync-Prozess ist dokumentiert + reproduzierbar

**Negativ:**
- Bei jedem Upstream-Sync entstehen Merge-Konflikte in `climate.py` (heavily diverged). Bei `binary_sensor.py` und `light.py` evtl. auch, falls Patrick dort wieder anpackt.
- Initial-Setup-Aufwand: User muss einmalig HACS-Custom-Repo umhängen
- Wenn der GitHub-Actions-Runner mal ausfällt, fällt die Awareness lautlos aus → quartalsweise Sanity-Check, ob `.github/upstream-last-seen` aktuell ist

**Bezogene Aufgaben:**
- Upstream-Merge auf v1.2.0 (Patrick's neuester Stand) — eigene AUF, später
- HACS-Repo-Umstellung — User-Action, dokumentiert in Sub-Projekt-README/CLAUDE.md
