# Full Debug Runbook

## Ergebnisziel

Dieses Runbook definiert die reproduzierbare Debug-Schleife für `benholl94-cwyk/upgraded-fiesta-Codex`.

## Ausführungsklassen

| Klasse | Zweck | Script |
|---|---|---|
| Init | Runtime-Verzeichnisse herstellen, Schutzregeln prüfen, Debug starten | `scripts/init_github_repo.py` |
| Static Debug | Struktur, Parser, Workspace, Secrets, Shell-Portabilität, mobile Constraints | `scripts/full_debug.py` |
| Deep Debug | Static Debug plus Cargo, npm und Docker-Prüfungen sofern verfügbar | `scripts/full_debug.py --deep` |

## Invarianten

- Keine Secrets werden erzeugt, angezeigt oder in Reports geschrieben.
- Runtime-Artefakte bleiben lokal: `logs/`, `runs/`, `backups/`, `exports/`, `.tmp/`, `.cache/`.
- Der statische Debug-Pfad ist dependency-free und benötigt nur Python 3.11+.
- Teure Build-Prüfungen sind explizit über `--deep` getrennt.

## Bewertungslogik

| Severity | Exit-Code-Wirkung | Bedeutung |
|---|---:|---|
| `error` | Fehlerhaft | Blocker für Merge oder Deployment |
| `warning` | Nicht blockierend | Risiko oder manuelle Prüfung erforderlich |
| `info` | Nicht blockierend | Zustandsinformation |

## Reports

Mit `--write-report` erzeugt `scripts/full_debug.py`:

- `reports/full_debug_report.json`
- `reports/full_debug_report.txt`

Der Textreport enthält einen SHA-256-Digest des JSON-Reports zur Integritätsprüfung.

## GitHub Actions

Der Workflow `.github/workflows/full-debug.yml` führt aus:

1. Python-Setup
2. statischen Full-Debug mit Report-Erzeugung
3. Upload der Reports als Workflow-Artefakt
4. Cargo-Check nur wenn Rust-Dateien betroffen sind
5. UI-Build nur wenn UI-Dateien betroffen sind
6. Docker-Compose-Konfigurationsprüfung nur wenn Compose/Dockerfile betroffen sind

## Mobile/a-Shell-Grenze

Der Python-Debugpfad ist für mobile Arbeitsumgebungen geeignet. Cargo, npm und Docker sind als optionale Deep-Checks klassifiziert, weil diese in iPhone/a-Shell-Umgebungen nicht zuverlässig als lokale Toolchain vorausgesetzt werden können.
