# EFI Mount Manager

![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green)
![License](https://img.shields.io/badge/license-MIT-green)

Eine native macOS Menübar-App zum Mounten und Unmounten von EFI-Partitionen.
Ideal für Hackintosh-User die regelmäßig auf die EFI zugreifen müssen.

![Screenshot](screenshots/menu.png)

## Features

- **Menübar-App** — lebt oben rechts in der macOS Leiste, kein Dock-Icon
- **EFI-Partitionen auflisten** — alle EFI-Partitionen auf allen Festplatten
- **Mount/Unmount** — mit macOS Admin-Auth-Dialog
- **In Finder öffnen** — gemountete EFI direkt im Finder öffnen
- **Auto-Refresh** — aktualisiert den Status alle 10 Sekunden
- **Eigenständig** — als PyInstaller-Binary gebaut, kein Python auf dem Ziel-System nötig
- **DMG-Installer** — fertiges `.dmg` mit Drag & Drop nach `/Applications`

## Installation

### Option 1: DMG-Installer (empfohlen)

1. Lade das [neueste Release](../../releases) herunter
2. Öffne das `.dmg`
3. Ziehe **EFI Mount Manager.app** in den **Applications**-Ordner
4. Fertig — kein Terminal nötig

### Option 2: Aus dem Quellcode

```bash
# Abhängigkeiten installieren
pip3 install PyQt6 pyinstaller

# App bauen und installieren
python3 install.py
```

Der Installer:
- Baut die App mit PyInstaller (eigenständige Binary)
- Kopiert sie nach `/Applications`
- Erstellt ein DMG für die Weitergabe

### Option 3: Direkt aus dem Repo

```bash
# PyQt6 installieren
pip3 install PyQt6

# App starten
python3 efimount_app.py
```

## Verwendung

Nach dem Start erscheint ein 💾-Icon in der Menüleiste:

```
💾 ──┬── EFI-Partitionen
     ├──   disk0s1  (200 MB)
     │   ├── ✓ Gemountet
     │   ├── → /Volumes/EFI
     │   ├── ⏎ Aushängen
     │   └── 📂 In Finder öffnen
     ├──   disk1s1  (300 MB)
     │   ├── ○ Nicht gemountet
     │   ├── ⏏ Mounten
     │   ├── ⏎ Aushängen
     │   └── 📂 In Finder öffnen
     ├── ↻ Aktualisieren
     ├── ℹ️ Über EFI Mount Manager
     └── ❌ Beenden
```

### Aktionen

| Aktion | Beschreibung |
|--------|-------------|
| **Mounten** | Mountet die EFI-Partition (Admin-Passwort erforderlich) |
| **Aushängen** | Unmountet die EFI-Partition (Admin-Passwort erforderlich) |
| **In Finder öffnen** | Öffnet den Mount-Point im Finder |
| **Aktualisieren** | Scannt die Partitionen neu |

## Projektstruktur

```
efimount_app/
├── efimount_app.py       # Hauptanwendung (PyQt6)
├── install.py            # Installer (baut + installiert + DMG)
├── build_dmg.py          # DMG-Builder (allein aufrufbar)
├── build.spec            # PyInstaller Build-Spec
├── gen_icon.py           # Icon-Generator
├── icon.iconset/         # App-Icon in verschiedenen Größen
├── dist/
│   ├── EFI Mount Manager.app        # Fertige App
│   └── EFI Mount Manager Installer.dmg  # DMG-Installer
└── README.md
```

## Systemanforderungen

- **macOS 11.0** (Big Sur) oder neuer
- **Python 3.9+** (nur zum Bauen, nicht zur Laufzeit)
- **Architektur**: Intel x86_64 (Apple Silicon: Rosetta 2)

## Entwicklung

```bash
# Abhängigkeiten
pip3 install PyQt6 pyinstaller

# App direkt starten
python3 efimount_app.py

# App neu bauen
python3 install.py

# Nur DMG erstellen
python3 build_dmg.py
```

## Technischer Hintergrund

Die App nutzt:
- `diskutil list` zum Ermitteln der EFI-Partitionen
- `diskutil info` für Mount-Point-Informationen
- `diskutil mount/unmount` über AppleScript mit Admin-Auth-Dialog
- `osascript -e 'do shell script "..." with administrator privileges'` für root-Rechte

## Bekannte Einschränkungen

- Admin-Rechte werden bei jeder Mount/Unmount-Operation abgefragt (macOS-Sicherheitsmodell)
- Apple Silicon: benötigt Rosetta 2 (PyInstaller-Build ist x86_64)

## Lizenz

MIT License — siehe ([LICENSE](https://en.wikipedia.org/wiki/MIT_License)) für Details.

## Autor

© 2026 by Werner Sellschopp

## Danksagung

- Basiert auf dem CLI-Tool `efimount`
- GUI mit [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Packaging mit [PyInstaller](https://pyinstaller.org/)
