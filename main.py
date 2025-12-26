import sys
import os
import requests
import subprocess
import ctypes  # Taskbar Icon Fix සඳහා අවශ්‍ය වේ
from packaging import version
from version import CURRENT_VERSION, REPO_OWNER, REPO_NAME

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QLinearGradient, QColor, QPainter, QFont, QIcon

# Import pages
from dashboard_page import DashboardPage
from students_page import StudentsPage
from analysis_page import AnalysisPage
from reports_page import ReportsPage
from settings_page import SettingsPage, ModernMessageDialog
from presentation_page import PresentationPage  # අලුත් Page එක Import කළා

# Import Alert
from system_alert import SystemAlertDialog

# ---------------- Path Management ----------------
def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_data_path():
    base_path = get_base_path()
    data_dir = os.path.join(base_path, "data")
    
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
        except Exception as e:
            print(f"Error creating data directory: {e}")
            
    return data_dir


# ---------------- Navigation Button ----------------
class NavigationButton(QPushButton):
    def __init__(self, text, icon="", parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {text}")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

        self.default_style = """
        QPushButton {
            background-color: transparent;
            color: rgba(255, 255, 255, 0.85);
            text-align: left;
            padding: 14px 24px;
            margin: 4px 16px;
            border-radius: 8px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12pt;
            border: none;
            outline: none;
        }
        QPushButton:focus { outline: none; }
        """

        self.hover_style = """
        QPushButton {
            background-color: rgba(255, 255, 255, 0.12);
            color: white;
            text-align: left;
            padding: 14px 24px;
            margin: 4px 16px;
            border-radius: 8px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12pt;
            border: none;
            outline: none;
        }
        """

        self.active_style = """
        QPushButton {
            background-color: rgba(255, 255, 255, 0.28);
            color: white;
            text-align: left;
            padding: 14px 24px;
            margin: 4px 16px;
            border-radius: 8px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12pt;
            font-weight: 600;
            border: none;
            outline: none;
        }
        """

        self.setStyleSheet(self.default_style)
        self.active = False

    def setActive(self, active):
        self.active = active
        self.setStyleSheet(self.active_style if active else self.default_style)

    def enterEvent(self, event):
        if not self.active:
            self.setStyleSheet(self.hover_style)

    def leaveEvent(self, event):
        if not self.active:
            self.setStyleSheet(self.default_style)


# ---------------- Gradient Background ----------------
class GradientFrame(QFrame):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#001733"))  # Deep blue
        gradient.setColorAt(1, QColor("#003366"))  # Medium blue

        painter.fillRect(self.rect(), gradient)


# ---------------- Navigation Panel ----------------
class NavigationPanel(QWidget):
    navigation_changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.buttons = []
        self.current_index = 0
        self.setFocusPolicy(Qt.StrongFocus)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 32, 0, 20)
        layout.setSpacing(8)

        # Presentation Button එකතු කරන ලදි
        nav_items = [
            ("📊", "Dashboard", "dashboard"),
            ("👨‍🎓", "Students", "students"),
            ("📈", "Analysis", "analysis"),
            ("📋", "Reports", "reports"),
            ("📺", "Presentation", "presentation"), # New Item Added
            ("⚙️", "Settings", "settings")
        ]

        for icon, text, btn_id in nav_items:
            btn = NavigationButton(text, icon)
            btn.setProperty("btn_id", btn_id)
            btn.setProperty("btn_text", text)
            btn.clicked.connect(
                lambda _, b=btn_id, t=text: self.activate_by_id(b, t)
            )
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

        # Display Version from version.py (Navigation Panel Bottom)
        version_lbl = QLabel(f"v{CURRENT_VERSION}")
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.4);
                font-size: 9pt;
                padding: 12px 24px;
            }
        """)
        layout.addWidget(version_lbl)

        self.activate_index(0)

    def activate_index(self, index):
        self.current_index = index
        for btn in self.buttons:
            btn.setActive(False)

        btn = self.buttons[index]
        btn.setActive(True)
        self.navigation_changed.emit(
            btn.property("btn_id"),
            btn.property("btn_text")
        )

    def activate_by_id(self, btn_id, btn_text):
        for i, btn in enumerate(self.buttons):
            if btn.property("btn_id") == btn_id:
                self.activate_index(i)
                break

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            self.activate_index((self.current_index + 1) % len(self.buttons))
        elif event.key() == Qt.Key_Up:
            self.activate_index((self.current_index - 1) % len(self.buttons))
        else:
            super().keyPressEvent(event)


# ---------------- Workspace Area ----------------
class WorkspaceArea(QWidget):
    def __init__(self, data_path):
        super().__init__()
        self.data_path = data_path
        self.current_page = None
        
        self.stack = QStackedWidget()
        
        # Create dashboard page first
        self.dashboard_page = DashboardPage(data_path)
        self.pages = {
            "dashboard": self.dashboard_page,
            "students": None,
            "analysis": None,
            "reports": None,
            "presentation": None, # New Page Placeholder
            "settings": None
        }
        
        self.stack.addWidget(self.dashboard_page)
        self.initUI()
        self.create_other_pages()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    def create_other_pages(self):
        """Create other pages after dashboard is initialized"""
        self.students_page = StudentsPage(self.data_path, self.dashboard_page)
        self.pages["students"] = self.students_page
        
        self.pages["analysis"] = AnalysisPage(self.data_path)
        self.pages["reports"] = ReportsPage(self.data_path)
        
        # Presentation Page එක සෑදීම
        self.pages["presentation"] = PresentationPage(self.data_path)
        
        self.pages["settings"] = SettingsPage(self.data_path)
        
        self.stack.addWidget(self.students_page)
        self.stack.addWidget(self.pages["analysis"])
        self.stack.addWidget(self.pages["reports"])
        self.stack.addWidget(self.pages["presentation"]) # Add to stack
        self.stack.addWidget(self.pages["settings"])

    def switch_page(self, page_id, page_title):
        if page_id in self.pages and self.pages[page_id] is not None:
            self.stack.setCurrentWidget(self.pages[page_id])
            self.current_page = page_id
            
            if page_id == "students" and self.students_page:
                self.students_page.load_year_options()


# ---------------- Main Window ----------------
class MainWindow(QMainWindow):
    def __init__(self, data_path):
        super().__init__()
        self.data_path = data_path
        
        # App name GIMI Pro ලෙස.
        self.setWindowTitle(f"GIMI Pro ")
        
        # Set application icon
        icon_path = os.path.join(get_base_path(), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Icon file not found at: {icon_path}")
        
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        self.setWindowFlags(
            Qt.Window | 
            Qt.CustomizeWindowHint | 
            Qt.WindowTitleHint | 
            Qt.WindowMinimizeButtonHint | 
            Qt.WindowCloseButtonHint |
            Qt.WindowSystemMenuHint
        )

        self.initUI()
        self.setFixedSize(screen_geometry.width(), screen_geometry.height())
        self.showMaximized()
        QTimer.singleShot(500, self.check_alerts)

    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        nav_bg = GradientFrame()
        nav_bg.setFixedWidth(260)

        nav_layout = QVBoxLayout(nav_bg)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self.nav = NavigationPanel()
        self.nav.navigation_changed.connect(self.on_navigation_changed)
        nav_layout.addWidget(self.nav)

        self.workspace = WorkspaceArea(self.data_path)

        layout.addWidget(nav_bg)
        layout.addWidget(self.workspace, 1)

    def on_navigation_changed(self, tab_id, tab_name):
        self.workspace.switch_page(tab_id, tab_name)

    def check_alerts(self):
        SystemAlertDialog.check_and_show(self.data_path, self)


# ---------------- Update Checker ----------------
def check_for_updates(parent_widget):
    print("Checking for updates...")
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            latest_version = data['tag_name'].replace('v', '')
            
            print(f"Current: {CURRENT_VERSION}, Latest: {latest_version}")

            if version.parse(latest_version) > version.parse(CURRENT_VERSION):
                download_url = ""
                for asset in data['assets']:
                    if asset['name'].endswith('.exe'):
                        download_url = asset['browser_download_url']
                        break
                
                if download_url:
                    dlg = ModernMessageDialog(
                        "Update Available", 
                        f"A new version ({latest_version}) is available.\nDo you want to update now?", 
                        "question", parent_widget
                    )
                    
                    if dlg.exec(): 
                        target_exe = "GIMI_Pro.exe" 
                        updater_exe = "updater.exe"
                        
                        if not os.path.exists(updater_exe):
                            ModernMessageDialog("Update Error", "updater.exe missing!", "error", parent_widget).exec()
                            return

                        subprocess.Popen([updater_exe, download_url, target_exe])
                        sys.exit() 
            else:
                print("System is up to date.")
    except Exception as e:
        print(f"Update check failed: {e}")


# ---------------- Run App ----------------
def main():
    # --- TASKBAR ICON FIX (වැදගත්ම කොටස) ---
    # Windows Taskbar එකේ Icon එක පෙන්වීමට මෙය අත්‍යවශ්‍යයි
    try:
        myappid = f'gimipro.student.system.{CURRENT_VERSION}' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"Could not set AppUserModelID: {e}")
    # ----------------------------------------

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    icon_path = os.path.join(get_base_path(), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    data_folder = get_data_path()

    window = MainWindow(data_folder)
    QTimer.singleShot(3000, lambda: check_for_updates(window))
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
