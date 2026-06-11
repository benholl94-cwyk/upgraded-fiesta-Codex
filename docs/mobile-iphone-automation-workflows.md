# Produktions-Workflows: iPhone als mobile Entwickler-Kontrollplattform

Stand: 2026-06-11

Diese Datei definiert den verbindlichen mobilen Workflow. Das iPhone ist der Kontrollpunkt für Git, Editor, lokale Checks, SSH, Shortcuts, Logs und Freigaben. Rechenintensive Builds, Docker, Datenbanken und produktive Deployments laufen remote. Alles andere wäre auf iOS unzuverlässig.

## 1. Architektur ohne Schönreden

| Ebene | iPhone-Komponente | Aufgabe | Produktionsgrenze |
| --- | --- | --- | --- |
| Orchestrierung | Apple Shortcuts | Apps öffnen, Eingaben abfragen, SSH-Kommandos starten, Logs ablegen | Kann App-Sandboxing und iOS-Hintergrundlimits nicht umgehen |
| Git | Working Copy | Clone, Pull, Branch, Diff, Commit, Push | Kein Ersatz für CI oder Build-Runner |
| Editor | Textastic oder Code App | Dateien aus Working Copy bearbeiten | Keine parallelen Dateikopien pflegen |
| Lokale Shell | a-Shell | Kleine Skripte, Smoke-Checks, statische Vorschau | Keine langen Produktionsprozesse |
| Linux-Werkzeugkasten | iSH | Alpine-nahe CLI-Workflows und Pakettests | Kein echter Linux-Kernel, keine Container-Plattform |
| Remote-Ausführung | SSH/Blink/a-Shell/Shortcuts | Tests, Builds, Deployments, Recovery | Remote-Host muss gehärtet und reproduzierbar sein |
| Secrets | Passwortmanager | Tokens, SSH-Passphrasen, Recovery-Codes | Keine Klartext-Secrets in `Developer/` |

## 2. Verbindliche Ordnerstruktur auf dem iPhone

Lege unter **Auf meinem iPhone** oder in einem verwalteten iCloud-Drive-Bereich exakt diese Struktur an:

```text
Developer/
  repos/
  inbox/
  outbox/
  runs/
  logs/
  exports/
  backups/
  tmp/
  policies/
  datasets/
```

Regeln:

- `repos/` enthält aktive Arbeitskopien oder App-Verknüpfungen zu Working Copy.
- `inbox/` ist nur für importierte Dateien, die noch geprüft werden müssen.
- `outbox/` ist nur für Dateien, die bewusst geteilt oder übertragen werden.
- `runs/` enthält Tagesprotokolle und Checklisten.
- `logs/` enthält lokale und Remote-Ausgaben.
- `exports/` enthält Release-Notizen, Artefaktlisten und ZIPs.
- `backups/` enthält nur verschlüsselte oder nicht-sensitive Sicherungen.
- `tmp/` darf jederzeit gelöscht werden.
- `policies/` enthält lokale Kopien der Sicherheits- und Freigaberegeln.
- `datasets/` enthält Kopien der CSV/JSON-Steuerdaten aus diesem Repository.

Verboten in dieser Struktur:

- Private SSH-Schlüssel.
- `.env`-Dateien mit produktiven Werten.
- Cloud-Provider-Schlüssel.
- Datenbank-Dumps mit Personen- oder Produktionsdaten.
- Unverschlüsselte Backups.

## 3. Steuerdaten und Einstellungen

Die produktionsrelevanten Steuerdaten liegen versioniert im Repository:

| Datei | Zweck |
| --- | --- |
| `settings/mobile-iphone-platform/settings.json` | Plattformvertrag, iOS-Grenzen, Ordnervertrag, Gates und SLOs |
| `settings/mobile-iphone-platform/shortcuts.catalog.json` | Katalog der einzurichtenden iOS-Shortcuts |
| `datasets/mobile-iphone-platform/apps.csv` | App-Rollen, Grenzen und Automationsflächen |
| `datasets/mobile-iphone-platform/workflows.csv` | Workflow-Matrix von Trigger bis Rollback |
| `datasets/mobile-iphone-platform/repositories.csv` | Repository-Inventar als Vorlage |
| `datasets/mobile-iphone-platform/commands.csv` | Lokale und Remote-Kommandos als Vorlage |
| `datasets/mobile-iphone-platform/remote-hosts.csv` | Remote-Hosts, Authentifizierung und Netzanforderungen |
| `datasets/mobile-iphone-platform/deployments.csv` | Deployment- und Rollback-Befehle |
| `datasets/mobile-iphone-platform/backup-policy.csv` | Backup-Assets, Ziele, Häufigkeit und Prüfung |
| `datasets/mobile-iphone-platform/secret-inventory.template.csv` | Vorlage für Secret-Rotation ohne geheime Werte |
| `datasets/mobile-iphone-platform/runbook-checks.csv` | Checklisten für Gates und Incident-Workflows |

Diese Dateien sind Vorlagen. Ersetze Beispielwerte durch reale Repository-, Host- und Deployment-Daten. Committe niemals echte Secrets.

## 4. Einmalige Produktions-Einrichtung

### 4.1 Dateien auf das iPhone bringen

1. Repository in Working Copy klonen.
2. `settings/mobile-iphone-platform/` nach `Developer/policies/mobile-iphone-platform/` exportieren.
3. `datasets/mobile-iphone-platform/` nach `Developer/datasets/mobile-iphone-platform/` exportieren.
4. In der Dateien-App prüfen, dass keine privaten Schlüssel oder `.env`-Dateien im Export liegen.
5. In Working Copy einen Branch `ops/iphone-control-plane` anlegen, wenn du reale Werte ergänzt.

### 4.2 Shortcuts anlegen

Lege in Apple Shortcuts die Einträge aus `settings/mobile-iphone-platform/shortcuts.catalog.json` an:

- `Dev Daily Bootstrap`
- `Remote CI Controller`
- `Dev Backup Snapshot`
- `Incident Freeze`

Jeder Shortcut muss Logs nach `Developer/logs/` schreiben oder eine manuelle Notiz in `Developer/runs/` erzwingen. Ein Shortcut ohne Log gilt als fehlgeschlagen.

### 4.3 Remote-Host vorbereiten

Auf jedem Remote-Host:

```sh
mkdir -p ~/src ~/runs ~/logs ~/releases
chmod 700 ~/runs ~/logs
ssh-keygen -t ed25519 -C "remote-host-control"
```

Für jedes Projekt:

```sh
cd ~/src
git clone <repo-url>
cd <repo>
git status
```

Produktionsregel: Das iPhone startet Remote-Kommandos, aber der Remote-Host enthält die reproduzierbare Build- und Deployment-Umgebung.

## 5. Workflow: Daily Bootstrap

Ziel: Arbeitsfähigkeit herstellen, ohne unkontrolliert zu editieren.

Ablauf:

1. Shortcut `Dev Daily Bootstrap` starten.
2. Netzwerk prüfen: vertrauenswürdiges WLAN, Mobilfunk oder VPN.
3. Working Copy öffnen.
4. Aktive Repositories per Fetch aktualisieren.
5. a-Shell öffnen und Tageslog anlegen:

```sh
mkdir -p ~/Developer/runs ~/Developer/logs
date -u > ~/Developer/runs/$(date -u +%Y-%m-%d)-bootstrap.log
python3 --version >> ~/Developer/runs/$(date -u +%Y-%m-%d)-bootstrap.log 2>&1
```

Gate: Kein Workflow startet, wenn Authentifizierung, Netzwerk oder Repository-Zugriff nicht funktionieren.

## 6. Workflow: Git Sync

Ziel: Kein Editieren auf veralteter Basis.

Ablauf:

1. In Working Copy `Fetch` ausführen.
2. Prüfen, ob der Zielbranch hinter Remote liegt.
3. Wenn ja: Pull/Rebase nach Teamregel durchführen.
4. Neuen Arbeitsbranch erstellen.
5. Branchname nach Muster setzen:

```text
feature/<kurzname>
fix/<kurzname>
ops/<kurzname>
hotfix/<kurzname>
```

Gate: Keine Änderungen in `main`, außer dokumentierter Hotfix-Prozess verlangt es.

## 7. Workflow: Edit Commit Push

Ziel: Änderung kontrolliert aus Working Copy über Editor bis Remote bringen.

Ablauf:

1. Repository aus Working Copy in Textastic oder Code App öffnen.
2. Nur Dateien im aktiven Arbeitsumfang bearbeiten.
3. In Working Copy Diff prüfen.
4. Geheimnisse und unpassende Dateien ausschließen.
5. Lokale Smoke-Checks ausführen.
6. Commit erstellen.
7. Push auf Remote-Branch.

Commit-Regel:

```text
<scope>: <konkrete änderung>
```

Beispiele:

```text
docs: add iphone automation workflows
ops: add mobile control-plane datasets
fix: correct shortcut log path
```

Rollback: Revert-Commit oder neuer Fix-Branch. Kein Force-Push auf geteilte Branches ohne schriftliche Absprache.

## 8. Workflow: Lokaler Smoke-Test

Ziel: Auf dem iPhone nur schnelle, deterministische Prüfungen ausführen.

Beispiele:

```sh
python3 --version
node --version
python3 -m py_compile path/to/script.py
python3 -m http.server 8000
```

Log-Regel:

```sh
mkdir -p ~/Developer/logs
{
  date -u
  python3 --version
  node --version
} > ~/Developer/logs/local-smoke.log 2>&1
```

Gate: Wenn ein Tool auf iOS fehlt, wird der Check nicht schön geredet. Der Skip muss mit Grund in Commit- oder PR-Notiz stehen.

## 9. Workflow: Remote Build/Test

Ziel: Reproduzierbare Tests nicht auf dem iPhone erzwingen.

Shortcut `Remote CI Controller` fragt ab:

- Repository-ID.
- Branch.
- Testprofil.

Remote-Kommandovorlage:

```sh
cd ~/src/${REPO_ID}
git fetch --all --prune
git checkout ${BRANCH}
git status --short
make test
```

Gate:

- `git status --short` muss vor dem Test leer sein.
- Testausgabe wird nach `Developer/logs/remote-ci.log` kopiert oder manuell dokumentiert.
- Bei Fehlern ist Deployment blockiert.

## 10. Workflow: Lokale Web-Vorschau

Ziel: Dokumentation oder statische Seiten lokal prüfen.

```sh
cd ~/Developer/repos/<projekt>
python3 -m http.server 8000
```

Browser öffnen:

```text
http://localhost:8000
```

Grenze: Sobald Watch-Modus, Datenbank, Container oder lang laufender Dev-Server nötig sind, wechselt der Workflow auf Remote Build/Test.

## 11. Workflow: Deployment-Steuerung

Ziel: Das iPhone darf Deployment auslösen, aber nicht improvisieren.

Voraussetzungen:

- CI grün.
- Rollback-Befehl in `datasets/mobile-iphone-platform/deployments.csv` vorhanden.
- Version oder Tag ist festgelegt.
- Backup/Snapshot existiert.
- Approval ist dokumentiert.

Remote-Kommandovorlage:

```sh
cd ~/src/${REPO_ID}
git fetch --all --prune
git checkout ${VERSION}
./ops/deploy.sh ${VERSION}
./ops/healthcheck.sh
```

Rollback-Vorlage:

```sh
cd ~/src/${REPO_ID}
./ops/rollback.sh ${PREVIOUS_VERSION}
./ops/healthcheck.sh
```

Regel: Kein Deployment aus Shortcuts, wenn Healthcheck oder Rollback unbekannt ist.

## 12. Workflow: Backup

Ziel: Änderungen und Arbeitsnachweise nicht verlieren.

Ablauf:

1. Alle relevanten Branches pushen.
2. Tageslog nach `Developer/runs/` schreiben.
3. Relevante Logs nach `Developer/backups/<YYYY-MM-DD>/` kopieren.
4. Backup verschlüsselt in Zielsystem übertragen.
5. Wiederherstellung stichprobenartig prüfen.

Backup-Check:

```sh
mkdir -p ~/Developer/backups/$(date -u +%Y-%m-%d)
cp ~/Developer/logs/*.log ~/Developer/backups/$(date -u +%Y-%m-%d)/ 2>/dev/null || true
```

Regel: Git ist die primäre Sicherung für Code. Backups sichern Nachweise, Logs und nicht versionierte Arbeitsdaten.

## 13. Workflow: Secret Rotation

Ziel: Secrets sind kontrolliert, minimal berechtigt und rotierbar.

Ablauf:

1. Secret in `secret-inventory.template.csv` als reale private Kopie erfassen, nicht committen.
2. Neues Secret im Provider erstellen.
3. Neues Secret im Passwortmanager speichern.
4. Zugriff testen.
5. Altes Secret widerrufen.
6. Rotationsdatum dokumentieren.

Verboten:

- Secrets in `Developer/datasets/` ohne Verschlüsselung.
- Secrets in Screenshots.
- Secrets in Shortcut-Namen, Log-Dateien oder Commit-Nachrichten.

## 14. Workflow: Incident Freeze

Ziel: Schaden begrenzen, bevor weiterentwickelt wird.

Ablauf:

1. Shortcut `Incident Freeze` starten.
2. Deployment-Shortcut deaktivieren.
3. Betroffene Tokens/Keys sperren oder rotieren.
4. Incident-Log in `Developer/runs/incident-<timestamp>.md` anlegen.
5. Remote-Host-Zustand sichern.
6. Fix-Branch erstellen.
7. Erst nach Review Deployments wieder aktivieren.

Mindestlog:

```text
Zeitpunkt UTC:
Betroffenes System:
Erkannt durch:
Sofortmaßnahme:
Rotierte Secrets:
Offene Risiken:
Nächster Prüfschritt:
```

## 15. Produktions-Gates

| Gate | Muss erfüllt sein | Blockiert |
| --- | --- | --- |
| Netzwerk | trusted network oder VPN | Git, SSH, Deploy |
| Auth | Token/SSH funktioniert | Git, CI, Deploy |
| Diff | Änderung geprüft | Commit |
| Secret Scan | Keine Klartext-Secrets | Commit, Push |
| Test | Lokal oder remote geprüft | Push, Deploy |
| CI | Remote grün | Deploy |
| Rollback | Befehl bekannt und getestet | Deploy |
| Backup | Snapshot oder Git-Push vorhanden | riskante Änderungen |

## 16. Minimaler Betriebsstandard

Ein iPhone-Workflow ist erst produktionsfähig, wenn diese Punkte erfüllt sind:

- Repositories sind in Working Copy eingerichtet.
- Editor bearbeitet dieselben Dateien, nicht Kopien.
- Shortcuts existieren und schreiben Logs.
- Remote-Host ist per SSH erreichbar.
- Test- und Deploy-Kommandos stehen in CSV-Datensätzen.
- Secrets liegen nur im Passwortmanager oder Provider.
- Backups sind verschlüsselt und wiederherstellbar.
- Rollback ist dokumentiert.
- Skips und iOS-Grenzen werden offen dokumentiert.
