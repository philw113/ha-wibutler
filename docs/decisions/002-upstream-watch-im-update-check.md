# ADR-002 — Upstream-Watch im Update-Check statt GitHub-Action, Abgleich nur selektiv

**Status:** Akzeptiert
**Datum:** 2026-10-19
**Kontext:** AUF-208. Ersetzt Punkt 3 aus ADR-001 (Upstream-Watch per GitHub-Action).

## Problem

Die Action `upstream-watch.yml` lief zuletzt am 2026-07-20. GitHub schaltet zeitgesteuerte Workflows ab, wenn ein Repo 60 Tage lang keinen Commit bekommt, Status `disabled_inactivity`. Der Fork bekommt selten Commits, also fällt die Action immer wieder aus, und zwar lautlos. Patricks Commits vom 2026-09-12 (1.2.1) blieben deshalb ungemeldet.

Beim Probe-Merge von Upstream 1.2.1 am 2026-10-19 kam ein zweiter Punkt hoch: Upstream hat die `unique_id` der Licht-Entities von `{id}_{name}` auf `{id}` geändert. Ein voller Merge würde alle Wibutler-Lichter in HA neu anlegen. Automationen, Blueprints, Dashboards und die Alexa-Bridge würden auf verwaiste Entities zeigen. Dazu kommen Konflikte in 5 Dateien, darunter die eigene `climate.py`.

## Entscheidung

1. **Upstream-Watch läuft im Update-Check auf pve1** (srv-homelab `scripts/update-check/update-check.sh`, Wochenlauf Montag 07:00). Er fragt den HEAD von `patrickweh/ha-wibutler` bei GitHub ab und meldet jeden neuen Stand einmal per ntfy, mit der Zahl der Commits, die im Fork fehlen, und dem Compare-Link. Die Action und `.github/upstream-last-seen` sind gelöscht.
2. **Abgleich selektiv statt voller Merge** (Festlegung Philipp 2026-10-19): Übernommen werden einzelne Upstream-Fixes, die für unser Setup zählen, von Hand portiert. Der Umbau auf die Basisklasse `WibutlerEntity` und die Taster-Events (`rocker.py`) werden nicht übernommen. Die Taster laufen über eigene Blueprints in srv-home-pve-ha-home.
3. Die Manifest-Version behält die Upstream-Basis, auf der der Fork steht (`1.0.1`), und bekommt ein neues Datum. Jede Version für HACS bekommt ein GitHub-Release mit eigenem Tag.

Erster selektiver Abgleich: Upstream `62b6277` (Retry, wenn der Hub-Login keinen Token liefert), Version `1.0.1+philw113-fork-2026-10-19`.

## Konsequenzen

- Meldet der Update-Check einen neuen Upstream-Stand: die Commits sichten und nur übernehmen, was zählt. Dafür gibt es eine neue Notion-AUF nur bei echtem Bedarf. Eine Dauer-Karte gibt es nicht mehr.
- Ein voller Merge wird erst wieder Thema, wenn Upstream etwas bringt, das wir brauchen. Dann muss die Licht-`unique_id` auf `{id}_{name}` bleiben, oder die Entities werden per Registry-Migration umgezogen.
