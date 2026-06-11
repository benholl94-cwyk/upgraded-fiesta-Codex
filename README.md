# Lokale Entwicklerumgebung auf dem iPhone

Dieses Repository enthält ein vollständiges, deutschsprachiges Setup für eine möglichst lokale Entwicklerumgebung auf dem iPhone.

- Hauptanleitung: [`docs/iphone-local-dev-setup.md`](docs/iphone-local-dev-setup.md)
- Schwerpunkt: lokale Shell, Git-Workflow, Editor, Python/JavaScript, SSH, Backups und Wartung
- Stand der geprüften App-/Tool-Informationen: 2026-06-11

## Kurzempfehlung

Für die meisten iPhone-Workflows ist die stabilste Kombination:

1. **Working Copy** für Git-Repositories, Commits, Branches und Push/Pull.
2. **Textastic** oder **Code App** als Code-Editor.
3. **a-Shell** für schnelle lokale Skripte, Python, JavaScript und Unix-Werkzeuge.
4. **iSH** als Alpine-Linux-ähnliche Umgebung, wenn du `apk`, Linux-Pakete oder eine klassische Shell brauchst.
5. **Blink Shell** oder ein anderer SSH/Mosh-Client optional für Remote-Builds, falls lokale iOS-Grenzen erreicht werden.

Die Details inklusive Installationsbefehlen, Verzeichnisstruktur, Git-Konfiguration, Testbefehlen und Fehlerbehebung stehen in der vollständigen Anleitung.

## Produktions-Workflow-Automation

Für den mobilen Betrieb als iPhone-Kontrollplattform enthält dieses Repository zusätzlich:

- Produktions-Workflows: [`docs/mobile-iphone-automation-workflows.md`](docs/mobile-iphone-automation-workflows.md)
- Plattform-Einstellungen: [`settings/mobile-iphone-platform/settings.json`](settings/mobile-iphone-platform/settings.json)
- Shortcut-Katalog: [`settings/mobile-iphone-platform/shortcuts.catalog.json`](settings/mobile-iphone-platform/shortcuts.catalog.json)
- Steuerdatensätze: [`datasets/mobile-iphone-platform/`](datasets/mobile-iphone-platform/)
- Validierung: [`scripts/validate_mobile_iphone_platform.py`](scripts/validate_mobile_iphone_platform.py)

Die Automatisierung ist bewusst als iPhone-Kontrollplattform ausgelegt: Git, Editor, lokale Smoke-Checks, Shortcuts und SSH laufen vom iPhone aus; Builds, Container, Datenbanken und Deployments werden reproduzierbar auf Remote-Hosts ausgeführt.
