# Codex-App und GitHub: Production-Grade Setup

Stand: 2026-06-12

## Ziel

Dieses Repository ist für Codex so vorbereitet, dass Codex in der App oder in Codex Web reproduzierbar arbeiten kann: Repository-Kontext, Setup-Kommando, Validierung, Review-Regeln und CI-Gates sind definiert.

## Repository

- GitHub: `benholl94-cmyk/upgraded-fiesta`
- Standardbranch: `main`
- Codex-Projektführung: `AGENTS.md`
- Cloud-Setup-Skript: `scripts/codex_cloud_setup.sh`
- CI-Gate: `.github/workflows/codex-production-gates.yml`

## App-Verbindung

Öffne in ChatGPT/Codex:

1. `Codex` öffnen.
2. GitHub verbinden oder bestehende GitHub-Verbindung prüfen.
3. Repository-Zugriff auf `benholl94-cmyk/upgraded-fiesta` aktivieren.
4. In Codex das Repository `upgraded-fiesta` auswählen.
5. Environment für dieses Repository öffnen.
6. Setup-Kommando setzen:

```sh
bash scripts/codex_cloud_setup.sh
```

7. Internetzugang für die Agent-Phase standardmäßig aus lassen. Internet ist für dieses Repository nicht notwendig, weil der Standardpfad statische Dateien und Python-Standardbibliothek nutzt.
8. Code Review für das Repository aktivieren, wenn PR-Reviews über GitHub genutzt werden sollen.
9. Optional automatische Reviews aktivieren, wenn jeder PR geprüft werden soll.

## Lokale/iPhone-kompatible Befehle

In a-Shell, iSH, Working Copy Shell oder einer Remote-Shell im geklonten Repository:

```sh
python3 -m py_compile scripts/validate_mobile_iphone_platform.py
python3 scripts/validate_mobile_iphone_platform.py
sh scripts/codex_cloud_setup.sh
```

Statischer Smoke-Test:

```sh
python3 -m http.server 8000
```

Dann lokal öffnen:

```text
http://localhost:8000
```

## Codex-Startprompt für die App

Nutze diesen Prompt nach Auswahl des Repositorys:

```text
Arbeite im Repository benholl94-cmyk/upgraded-fiesta. Lade AGENTS.md, führe bash scripts/codex_cloud_setup.sh aus, prüfe die statische iPhone-Control-Plane, nenne mir die geladenen Projektregeln, die ausgeführten Validierungen und die nächsten risikoärmsten Verbesserungen als kleine PR-taugliche Arbeitspakete. Keine Desktop-Annahmen, keine Secrets, keine nicht validierten Behauptungen.
```

## GitHub-Review-Befehle

Manueller Codex-Review in einem Pull Request:

```text
@codex review
```

Fokussierter Review:

```text
@codex review for iPhone execution regressions, unsafe shell commands, dataset schema breaks, and secret leakage
```

Fix nach Review-Fund:

```text
@codex fix the P1 issue and keep the diff minimal
```

CI-Fix aus PR-Kontext:

```text
@codex fix the CI failures and explain the validation command that proves the fix
```

## Validierungskriterien

Ein Codex-Ergebnis ist erst akzeptabel, wenn mindestens diese Signale vorliegen:

- `python3 -m py_compile scripts/validate_mobile_iphone_platform.py` erfolgreich.
- `python3 scripts/validate_mobile_iphone_platform.py` erfolgreich.
- `sh scripts/codex_cloud_setup.sh` erfolgreich.
- Kein Secret oder Token in neuen/editierten Dateien.
- Änderungen bleiben iPhone-first und statisch deploybar.
- PR-Beschreibung enthält Zusammenfassung, Tests, Ergebnis und Restlimitierungen.

## Fehlerbehebung

Wenn das Repository in Codex nicht sichtbar ist:

1. ChatGPT App öffnen.
2. Settings öffnen.
3. Apps öffnen.
4. GitHub öffnen.
5. Repository-Zugriff neu konfigurieren.
6. `benholl94-cmyk/upgraded-fiesta` explizit erlauben.
7. Einige Minuten warten und Codex erneut öffnen.

Wenn Codex alte Setup-Ergebnisse nutzt:

1. Codex Environment öffnen.
2. Cache zurücksetzen.
3. Setup erneut ausführen lassen.
4. Prüfen, dass `bash scripts/codex_cloud_setup.sh` im Setup-Feld steht.

Wenn Codex Anweisungen ignoriert:

1. Prüfen, dass `AGENTS.md` im Repo-Root liegt.
2. In Codex fragen: `Show which instruction files you loaded.`
3. Neue Codex-Session starten, weil Instruktionen pro Lauf neu geladen werden.

## Sicherheitsgrenze

Dieses Setup verbindet Codex mit dem Repository-Workflow. Es gibt Codex keine versteckte OS-Kontrolle über dein iPhone. iOS-Sandboxing, App-Berechtigungen und GitHub-Berechtigungen bleiben die technischen Grenzen.
