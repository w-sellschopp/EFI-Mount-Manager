#!/usr/bin/env python3
"""
EFI Mount Manager — macOS Menübar-App zum Mounten/Unmounten von EFI-Partitionen.
"""
from __future__ import annotations

import sys
import subprocess
import os
import platform
from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QFontMetrics


# ─── Icons als SVG/Pixmap generieren ─────────────────────────────────

def create_disk_icon(color: str = "#ffffff", size: int = 22) -> QIcon:
    """Erstellt ein simples Disk-Icon als QPixmap."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Hintergrund-Farbe (weiß für Menübar, passt sich nicht automatisch an)
    pen_color = QColor(color)
    painter.setPen(pen_color)
    painter.setFont(QFont("SF Pro", 16, QFont.Weight.Bold))

    # Disk-Symbol als Unicode
    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        "💾"
    )
    painter.end()
    return QIcon(pixmap)


def create_efi_icon(is_mounted: bool = False, size: int = 22) -> QIcon:
    """Icon mit Status-Indikator."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Disk-Rechteck
    rect = painter.fontMetrics()
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("SF Pro", 14, QFont.Weight.Bold))
    painter.drawText(
        pixmap.rect(),
        Qt.AlignmentFlag.AlignCenter,
        "💾"
    )

    # Status-Punkt
    if is_mounted:
        painter.setBrush(QColor("#34c759"))  # Grün
    else:
        painter.setBrush(QColor("#8e8e93"))  # Grau
    painter.setPen(Qt.PenStyle.NoPen)

    dot_size = 6
    dot_x = size - dot_size - 1
    dot_y = size - dot_size - 1
    painter.drawEllipse(dot_x, dot_y, dot_size, dot_size)

    painter.end()
    return QIcon(pixmap)


# ─── Data Model ───────────────────────────────────────────────────────

@dataclass
class EFIPartition:
    device: str
    size: str
    mount_point: Optional[str] = None

    @property
    def is_mounted(self) -> bool:
        return self.mount_point is not None and self.mount_point != ""


# ─── Backend (diskutil + osascript) ──────────────────────────────────

def get_efi_partitions() -> list[EFIPartition]:
    """EFI-Partitionen über diskutil list ermitteln."""
    result = subprocess.run(
        ["diskutil", "list"], capture_output=True, text=True
    )
    partitions: list[EFIPartition] = []
    for line in result.stdout.splitlines():
        if "EFI EFI" in line:
            parts = line.split()
            if len(parts) >= 4:
                device = parts[-1]
                size_unit = parts[-2]
                size_num = parts[-3]
                size = f"{size_num} {size_unit}"
                mp = _get_mount_point(device)
                partitions.append(EFIPartition(device, size, mp))
    return partitions


def _get_mount_point(device: str) -> Optional[str]:
    """Mount-Point einer Partition ermitteln."""
    result = subprocess.run(
        ["diskutil", "info", device], capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if "Mount Point" in line and ":" in line:
            mp = line.split(":", 1)[1].strip()
            return mp if mp else None
    return None


def run_with_admin_auth(command: list[str]) -> subprocess.CompletedProcess:
    """Befehl mit macOS Admin-Auth-Dialog ausführen."""
    escaped_args = " ".join(
        arg.replace("\\", "\\\\").replace('"', '\\"')
        for arg in command
    )
    script = f'do shell script "{escaped_args}" with administrator privileges'
    return subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )


# ─── Worker Thread ────────────────────────────────────────────────────

class EFIOperationWorker(QThread):
    """Hintergrund-Thread für Mount/Unmount-Operationen."""
    finished = pyqtSignal(bool, str)

    def __init__(self, action: str, device: str):
        super().__init__()
        self.action = action
        self.device = device

    def run(self):
        if self.action == "mount":
            result = run_with_admin_auth(["diskutil", "mount", self.device])
        elif self.action == "unmount":
            result = run_with_admin_auth(["diskutil", "unmount", self.device])
        else:
            self.finished.emit(False, f"Unbekannte Aktion: {self.action}")
            return

        if result.returncode == 0:
            if self.action == "mount":
                mp = _get_mount_point(self.device)
                msg = f"{self.device} erfolgreich gemountet."
                if mp:
                    msg += f"\n→ {mp}"
                self.finished.emit(True, msg)
            else:
                self.finished.emit(True, f"{self.device} erfolgreich ausgehängt.")
        else:
            err = (result.stderr or result.stdout or "Fehler unbekannt").strip()
            self.finished.emit(False, err)


# ─── Menübar-App ─────────────────────────────────────────────────────

class EFIStatusBarApp:
    """Haupt-App als macOS Menübar-App."""

    REFRESH_INTERVAL = 10000  # 10 Sekunden

    def __init__(self):
        self._partitions: list[EFIPartition] = []
        self._worker: Optional[EFIOperationWorker] = None
        self._is_busy = False

        # Tray-Icon
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(create_efi_icon())
        self.tray.setToolTip("EFI Mount Manager")

        # Menü aufbauen
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        # Auto-Refresh Timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.REFRESH_INTERVAL)

        # Erstes Laden
        self._refresh()

        # Tray aktivieren und Notification
        self.tray.setVisible(True)

    def _refresh(self):
        """Partitionen neu laden und Menü aufbauen."""
        if self._is_busy:
            return

        self._partitions = get_efi_partitions()
        self._build_menu()

        # Tray-Icon aktualisieren (zeige gemountet-Status im Icon)
        any_mounted = any(p.is_mounted for p in self._partitions)
        self.tray.setIcon(create_efi_icon(is_mounted=any_mounted))

    def _build_menu(self):
        """Menü dynamisch aus Partitionen aufbauen."""
        self.menu.clear()

        if not self._partitions:
            action = self.menu.addAction("Keine EFI-Partitionen gefunden")
            action.setEnabled(False)
            self.menu.addSeparator()
            self._add_standard_actions()
            return

        # Header
        header = self.menu.addAction("EFI-Partitionen")
        header.setEnabled(False)
        self.menu.addSeparator()

        # Partition-Einträge
        for p in self._partitions:
            # Sub-Menü für jede Partition
            sub_menu = self.menu.addMenu(f"  {p.device}  ({p.size})")

            # Status-Zeile
            if p.is_mounted:
                status_action = sub_menu.addAction(f"✓ Gemountet")
                status_action.setEnabled(False)

                # Mount-Point anzeigen
                mp_action = sub_menu.addAction(f"  → {p.mount_point}")
                mp_action.setEnabled(False)

                # Actions
                sub_menu.addSeparator()

                mount_action = sub_menu.addAction("⏏ Mounten")
                mount_action.setEnabled(False)  # schon gemountet

                unmount_action = sub_menu.addAction("⏎ Aushängen")
                unmount_action.triggered.connect(
                    lambda checked, d=p.device: self._do_operation("unmount", d)
                )

                finder_action = sub_menu.addAction("📂 In Finder öffnen")
                finder_action.triggered.connect(
                    lambda checked, mp=p.mount_point: self._open_in_finder(mp)
                )
            else:
                status_action = sub_menu.addAction("○ Nicht gemountet")
                status_action.setEnabled(False)

                sub_menu.addSeparator()

                mount_action = sub_menu.addAction("⏏ Mounten")
                mount_action.triggered.connect(
                    lambda checked, d=p.device: self._do_operation("mount", d)
                )

                unmount_action = sub_menu.addAction("⏎ Aushängen")
                unmount_action.setEnabled(False)

                finder_action = sub_menu.addAction("📂 In Finder öffnen")
                finder_action.setEnabled(False)

        self.menu.addSeparator()
        self._add_standard_actions()

    def _add_standard_actions(self):
        """Standard-Menü-Einträge."""
        refresh_action = self.menu.addAction("↻ Aktualisieren")
        refresh_action.triggered.connect(self._refresh)

        about_action = self.menu.addAction("ℹ️ Über EFI Mount Manager")
        about_action.triggered.connect(self._show_about)

        quit_action = self.menu.addAction("❌ Beenden")
        quit_action.triggered.connect(QApplication.instance().quit)

    def _do_operation(self, action: str, device: str):
        """Mount/Unmount ausführen."""
        if self._is_busy:
            return

        self._is_busy = True
        self.tray.setToolTip(f"EFI Mount Manager — {action} {device}...")

        self._worker = EFIOperationWorker(action, device)
        self._worker.finished.connect(
            lambda success, msg: self._on_operation_done(success, msg, device)
        )
        self._worker.start()

    def _on_operation_done(self, success: bool, message: str, device: str):
        """Operation abgeschlossen."""
        self._is_busy = False
        self.tray.setToolTip("EFI Mount Manager")

        if success:
            # macOS Notification
            self.tray.showMessage(
                "EFI Mount Manager",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self._refresh()
        else:
            QMessageBox.critical(
                None,
                "Fehler",
                message,
                QMessageBox.StandardButton.Ok,
            )

    def _open_in_finder(self, mount_point: str):
        """Verzeichnis in Finder öffnen."""
        subprocess.Popen(["open", mount_point])

    def _show_about(self):
        """Über-Dialog mit eigenem Logo."""
        dialog = QDialog()
        dialog.setWindowTitle("Über EFI Mount Manager")
        dialog.setFixedSize(380, 320)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Logo
        logo = QLabel()
        logo_path = "/Users/werner/EFI.png"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Auf max 120x120 skalieren
            pixmap = pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(pixmap)
        else:
            pixmap = create_efi_icon(is_mounted=True, size=64)
            logo.setPixmap(pixmap.pixmap(64, 64))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        # Titel
        title = QLabel("EFI Mount Manager v1.0")
        title.setFont(QFont(".AppleSystemUIFont", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Beschreibung
        desc = QLabel(
            "macOS Menübar-App zum Mounten und Unmounten\n"
            "von EFI-Partitionen.\n\n"
            "Erstellt mit PyQt6"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(desc)

        # Copyright
        copyright_label = QLabel("© 2026 by Werner Sellschopp")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(copyright_label)

        layout.addStretch()

        # OK-Button
        btn = QPushButton("OK")
        btn.setFixedHeight(36)
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn)

        dialog.exec()


# ─── Entry Point ──────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)

    # WICHTIG: App nicht beenden wenn alle Fenster geschlossen sind
    app.setQuitOnLastWindowClosed(False)

    # App als reine Menübar-App (kein Dock-Icon)
    # LSUIElement via Info.plist setzen
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info['LSUIElement'] = '1'
    except ImportError:
        # Fallback: PyObjC nicht installiert — Dock-Icon bleibt sichtbar
        pass

    # Dark-Mode Support
    if sys.platform == "darwin":
        os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")

    # Menübar-App starten (globale Referenz =不会被 GC)
    global _tray_app
    _tray_app = EFIStatusBarApp()

    # Event-Loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
