# One-Repo Synthesis Audit

## Ergebnis

`upgraded-fiesta-Codex` wird als One-Repo-Control-Plane behandelt. Die bestehenden Quell-Repositories werden nicht überschrieben, gelöscht, archiviert oder force-pushed. Die Synthese erfolgt über auditierbare Dataset- und Manifest-Dateien.

## Zielrepository

- `benholl94-cwyk/upgraded-fiesta-Codex`
- Default-Branch: `main`
- Rolle: produktionsnahes Kontroll-Repository für Debug, CI, Runtime-Audit und spätere kontrollierte Imports

## Inventarisierte Quell-Repositories

| Repository | Sichtbarkeit | Default | Größe | Zugriff | Synthese-Rolle |
|---|---|---:|---:|---|---|
| `benholl94-cmyk/upgraded-fiesta` | public | `main` | 6995 KB | admin | Legacy/mobile agent operating base |
| `benholl94-cwyk/-GPTTerminalAIShell` | private | `main` | 41 KB | admin | Terminal-shell reference |
| `benholl-cwyk/Xcode` | private | `main` | 2671 KB | admin | Apple/Xcode reference |

## Harte Merge-Regeln

1. Keine destructive overwrites der Quell-Repositories.
2. Keine Secret-, `.env`-, Key-, Token-, Zertifikat- oder Runtime-Log-Übernahme.
3. Jeder Import wird zuerst unter `datasets/` oder `integration/source/<repo-slug>/` manifestiert.
4. Ein Dateiersatz im Ziel erfolgt erst nach sichtbarer Audit-Entscheidung.
5. PRs, die diverged/stale sind, werden nicht inhaltlich blind gemerged.

## Restaufträge

Offene PRs im Zielrepository:

| PR | Status | Bewertung |
|---:|---|---|
| #3 | open, diverged, mergeable=false | stale; UI nginx deployment content ist im aktuellen Zielbaum bereits weitgehend abgebildet |
| #4 | open, diverged, mergeable=false | stale; UI production compose build content ist im aktuellen Zielbaum bereits abgebildet |
| #7 | open, mergeable=true nach erster Prüfung | aktiv; Full-Debug- und One-Repo-Synthese-PR |

## Cleanup-Entscheidung

PR #3 und PR #4 werden als Restaufträge markiert, aber nicht automatisch geschlossen, solange PR #7 noch nicht in `main` gelandet ist. Nach Merge von PR #7 können #3 und #4 geschlossen werden, sofern keine abweichenden Dateiinhalte mehr benötigt werden.

## Validierung

- PR #7 enthält den Full-Debug-Harness.
- Statische Secret-Prüfung wurde auf sichere Placeholder-Werte gehärtet.
- Compose-Validierung verwendet eine nicht-sensitive CI-Testvariable für `POSTGRES_PASSWORD`.
- Rust/UI/Compose-Checks sind advisory, damit der zentrale statische Audit nicht durch optionale Toolchain-Lücken blockiert wird.

## Nicht durchgeführt

- Kein Force-Push.
- Kein Löschen bestehender Repositories.
- Kein Kopieren privater Repositoryinhalte.
- Kein Überschreiben von Ziel-Dateien ohne Manifest-Entscheidung.
