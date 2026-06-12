# a-Shell Mobile Master-Grade Control Plane

Stand: 2026-06-12

Dieses Dokument definiert die produktionsnahe Nutzung von `upgraded-fiesta` auf dem iPhone mit a-Shell. Ziel ist nicht, iOS-Sandboxing zu umgehen. Ziel ist eine robuste mobile Bindung an die tiefste zuverlässig erreichbare Ebene: a-Shell-Dateisystem, lokale Python-Ausführung, `lg2`/libgit2, Files-App-Handoff, lokale HTTP-Vorschau, Logs, Audits, Shortcuts und SSH-gesteuerte Remote-Ausführung.

## Operativer Grundsatz

Das iPhone ist die Kontroll- und Freigabeebene. Es koordiniert Git, Editor, lokale Prüfungen, Audit-Logs, Runbooks, Shortcuts und SSH. Rechenintensive Builds, Docker, Datenbanken, Langläufer und produktive Deployments laufen auf einem reproduzierbaren Remote-Host oder in CI.

## Direkte Kommandos ohne Profile-Abhängigkeit

Diese Kommandos funktionieren aus dem Repository-Ordner `~/Documents/Developer/upgraded-fiesta.git`:

```sh
python3 scripts/mobile_operator.py validate
python3 scripts/mobile_operator.py doctor
python3 scripts/mobile_operator.py audit
python3 scripts/mobile_operator.py health
python3 scripts/mobile_operator.py backup
python3 scripts/mobile_operator.py serve
```

## Daily Bootstrap

```sh
cd ~/Documents/Developer/upgraded-fiesta.git
lg2 pull
python3 scripts/mobile_operator.py doctor
python3 scripts/mobile_operator.py audit
python3 scripts/mobile_operator.py health
```

Gate: Erst nach erfolgreichem `doctor` und `audit` wird editiert, committed oder gepusht.

## Lokale Vorschau

```sh
python3 scripts/mobile_operator.py serve
```

Dann Safari öffnen:

```text
http://localhost:8000/
```

Der Server behandelt fehlendes `/favicon.ico` sauber und reduziert Safari-Verbindungsabbrüche.

## Sichere Main-/Master-Modifikation

1. `lg2 pull` ausführen.
2. `python3 scripts/mobile_operator.py doctor` ausführen.
3. Arbeitsbranch in Working Copy oder über die Git-Plattform anlegen.
4. Änderung im Editor durchführen.
5. `python3 scripts/mobile_operator.py validate` ausführen.
6. `python3 scripts/mobile_operator.py audit` ausführen.
7. Diff in Working Copy prüfen.
8. Commit-Nachricht nach Muster schreiben: `<scope>: <konkrete änderung>`.
9. Push auf Remote-Branch.
10. Review/PR oder dokumentierter Hotfix-Prozess.

Kein Force-Push auf gemeinsam genutzte Branches. Keine sensiblen Dateien in Repo, Logs, Screenshots oder Shortcut-Namen.

## Incident Freeze

```sh
python3 scripts/mobile_operator.py runlog incident-freeze
python3 scripts/mobile_operator.py audit
python3 scripts/mobile_operator.py health
```

Danach: Deployment-Shortcuts deaktivieren, betroffene Zugangsdaten im Provider rotieren, Remote-Host-Zustand sichern und Fix-Branch erstellen. Auf dem iPhone wird koordiniert, nicht improvisiert.
