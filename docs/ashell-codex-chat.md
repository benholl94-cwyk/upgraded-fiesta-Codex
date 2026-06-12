# a-Shell Codex Chat

## Zweck

`scripts/ashell_codex_chat.py` ist ein interaktives a-Shell-Interface für dieses Repository. Es verbindet drei Dinge in einer Oberfläche:

- Live-Monitoring des Repository-Zustands.
- Lokale Validierungs- und Audit-Kommandos.
- Einen austauschbaren Chat-Bridge-Prozess über `CODEX_CHAT_BRIDGE_CMD`.

Das Repository speichert keine Zugangsdaten. Der Bridge-Prozess wird lokal in a-Shell über eine Umgebungsvariable gesetzt und erhält den Prompt über stdin. Die Antwort muss über stdout zurückkommen.

## Start

```sh
cd ~/Documents/Developer/upgraded-fiesta.git
python3 scripts/ashell_codex_chat.py
```

## UI-Kommandos

```text
/help
/status
/audit
/validate
/bridge-test
/run python3 scripts/mobile_operator.py self-test
/exit
```

## Bridge-Vertrag

Die Chat-UI ruft nur dann ein Modell auf, wenn diese Variable gesetzt ist:

```sh
export CODEX_CHAT_BRIDGE_CMD='python3 ~/Documents/Developer/private-bridges/openai_responses_bridge.py'
```

Der Bridge-Prozess muss:

1. Prompt und Repo-Kontext von stdin lesen.
2. Die Antwort auf stdout schreiben.
3. Zugangsdaten nur aus lokaler Umgebung oder Passwortmanager-Übergabe lesen.
4. Keine Zugangsdaten in dieses Repository schreiben.

## Monitoring

Die UI schreibt:

- Logs: `~/Documents/Developer/logs/ashell-codex-chat-YYYYMMDD.jsonl`
- Letzter Zustand: `~/Documents/Developer/runs/ashell-codex-chat-last.json`

## Sicherheitsgrenzen

- `/run` akzeptiert nur eine feste Allowlist lokaler Befehle.
- Destruktive Befehle, Pipes, Shell-Verkettung und blinde Remote-Ausführung sind blockiert.
- Die UI behauptet keine versteckte Kontrolle über die ChatGPT- oder Codex-App.
- Codex-App-Remote-Control bleibt eine separate Codex-App/Workspace-Berechtigung.
