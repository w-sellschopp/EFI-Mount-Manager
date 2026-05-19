Dies ist ein EFI-Partition Mounter für Hackintosh. 

Was der Installer macht:
    
    1. Prüft Python 3.9+
    2. Installiert PyQt6 falls nötig
    3. Installiert PyInstaller falls nötig
    4. Baut die eigenständige .app (Mach-O Binary, kein Python nötig)
    5. Installiert nach /Applications mit eigenem Icon
    6. Erstellt DMG-Installer (EFI Mount Manager Installer.dmg)   
    
    DMG-Installer:
    - 24.3 MB komprimiert
    - Drag & Drop nach /Applications
    - Kein Python auf dem Ziel-System nötig
    - Funktioniert auf jedem macOS 11+
