# Safe Write / Edit / Ops Object Tool

## Ergebnis

Dieses Tool definiert und verarbeitet ein maschinenlesbares `safe_write/edit/ops`-Object für reale Repository-Änderungen. Es ist für kontrollierte Schreib-, Editier- und Quarantäne-Operationen innerhalb des One-Repo-Control-Plane-Modells gebaut.

## Komponenten

| Datei | Rolle |
|---|---|
| `scripts/safe_write_edit_ops.py` | Dependency-freier Executor für `validate`, `plan`, `apply` |
| `schemas/safe-write-edit-ops.schema.json` | JSON-Schema für das Operation-Object |
| `datasets/safe-write-edit-ops.policy.json` | Maschinenlesbare Policy mit erlaubten Roots, Deny-Globs und realen Repo-Werten |
| `examples/safe-write-edit-ops.object.json` | Realwert-basiertes Beispiel-Object im `plan`-Modus |

## Object-Modi

| Modus | Wirkung |
|---|---|
| `plan` | validiert und berechnet Zielzustände, schreibt nichts |
| `apply` | führt Änderungen aus, sofern Object, Policy, Pfade und Hash-Guards gültig sind |

## Unterstützte Operationen

| Operation | Zweck | Sicherheitsbedingung |
|---|---|---|
| `mkdir` | Verzeichnis anlegen | Zielpfad muss erlaubt sein |
| `write_file` | Datei schreiben | `overwrite=false` blockiert existierende Dateien; Überschreiben ist explizit |
| `append_file` | Datei erweitern | optionaler Hash-Guard möglich |
| `edit_replace` | exakte Text-Ersetzung | `expected_sha256` ist verpflichtend |
| `copy_file` | erlaubte Datei kopieren | Source/Target müssen erlaubt sein; Hash-Guards optional erzwingbar |
| `quarantine_path` | Pfad in `.tmp` verschieben | kein Delete; nur Quarantäne |

## Harte Grenzen

- Keine absoluten Pfade außerhalb des Repositories.
- Kein `..`-Traversal.
- Keine `.env`, Key-, Zertifikat-, Secret- oder Node/Target/Runtime-Pfade.
- Kein Delete-Befehl; nur Quarantäne.
- Atomic Write via temporärer Datei und `os.replace`.
- Backup bei existierenden Zielen unter `.tmp/safe_write_edit_ops_backups`.
- Apply-Audit unter `runs/safe_write_edit_ops`.

## Make-Ziele

```sh
make safe-ops-validate
make safe-ops-plan
```

`apply` ist absichtlich kein Make-Default-Ziel. Apply erfordert ein Object mit `mode=apply` und expliziten direkten CLI-Aufruf.

## Reale Materialbasis

Das Policy-/Object-Material basiert auf aktuellen Repo-Fakten:

- Zielrepo: `benholl94-cwyk/upgraded-fiesta-Codex`
- Default-Branch: `main`
- Synthese-Merge: `d0fce4a66703364f8c3d28333c03ac3ebe27d21d`
- Rebase-Guard-Merge: `147049e6ac2b832d80c492415bf5d9f9c9c750ec`
- geschlossene stale PRs: `#3`, `#4`
- gemergte PRs: `#7`, `#8`

## Validierungsentscheidung

Das Tool ist produktionsnah bewusst konservativ: Es verhindert destruktive Defaults und verlangt für riskante Edits Hash-gebundene Vorbedingungen.
