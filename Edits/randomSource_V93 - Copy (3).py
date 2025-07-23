import sys
import os
import subprocess
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen

# Thread for executing commands
class CommandThread(QThread):
    finished = pyqtSignal(bool, str)
    jupyter_started = pyqtSignal()

    def __init__(self, base_path, selected_env, command_type="jupyter"):
        super().__init__()
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type

    def run(self):
        try:
            activate_script = os.path.join(self.base_path, self.selected_env, "Scripts", "activate.bat")
            if self.command_type == "jupyter":
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}" && jupyter notebook'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}"'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            time.sleep(1)
            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook launched successfully!")
                self.jupyter_started.emit()
            else:
                self.finished.emit(True, "Virtual environment activated successfully!")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if "activate.bat" in error_msg:
                error_msg = "Error: Failed to activate virtual environment."
            elif "jupyter" in error_msg:
                error_msg = "Error: Jupyter Notebook not installed in environment."
            self.finished.emit(False, error_msg)

# Custom animated running indicator
class RunningIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setToolTip("Jupyter Notebook is running")
        self.is_on = False
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.setVisible(False)

    def set_on(self, on=True):
        self.is_on = on
        self.setVisible(True)
        if on:
            self.timer.start(50)
        else:
            self.timer.stop()
        self.update()

    def update_animation(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(34, 197, 94) if self.is_on else QColor(239, 68, 68)  # Green when on, red when off
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.black, 0.5))
        painter.drawEllipse(2, 2, 16, 16)
        if self.is_on:
            painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
            painter.translate(10, 10)
            painter.rotate(self.angle)
            painter.drawEllipse(-4, -4, 8, 8)

# Main application window
class JupyterLauncher(QWidget):
    # Modern color palette
    BACKGROUND = "#0f172a"  # Slate-900
    TEXT_COLOR = "#f1f5f9"  # Slate-100
    ACCENT = "#4f46e5"     # Indigo-600
    BUTTON_BG = "#1e293b"   # Slate-800
    BUTTON_HOVER = "#475569" # Slate-600
    SUCCESS = "#22c55e"     # Green-500
    ERROR = "#ef4444"       # Red-500

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pyhton Virtual Environment Launcher")
        self.setFixedSize(600, 500)  # Increased height to accommodate file list
        self.setStyleSheet(self.get_stylesheet())
        self.setup_ui()
        
        default_path = "P:/Codes/Machine Learning"  # Updated default path
        self.path_input.setText(default_path if os.path.isdir(default_path) else os.path.expanduser("~"))
        self.discover_virtual_environments()

    def get_stylesheet(self):
        return f"""
            QWidget {{
                background-color: {self.BACKGROUND};
                color: {self.TEXT_COLOR};
                font-family: 'Inter', Arial, sans-serif;
            }}
            QLineEdit {{
                background-color: #1e293b;
                border: 2px solid {self.ACCENT};
                border-radius: 10px;
                padding: 10px;
                color: {self.TEXT_COLOR};
                font-size: 14px;
            }}
            QComboBox {{
                background-color: #1e293b;
                border: 2px solid {self.ACCENT};
                border-radius: 10px;
                padding: 10px;
                color: {self.TEXT_COLOR};
                font-size: 14px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAHCAYAAADXCDzzAAAAAXNSR0IArs4c6QAAADhJREFUKFOd0LEJACAMxND/f7kbkBA2kUkhpV2EJOJ3+CA4iYUzF8wL0D0M3fLCTnADb0n1AZpZBlz0l1+xAAAAAElFTkSuQmCC);
                width: 12px;
                height: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1e293b;
                border: 2px solid {self.ACCENT};
                color: {self.TEXT_COLOR};
                selection-background-color: {self.ACCENT};
                padding: 5px;
            }}
            QPushButton {{
                background-color: {self.BUTTON_BG};
                color: {self.TEXT_COLOR};
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {self.ACCENT};
            }}
            QLabel#titleLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {self.ACCENT};
            }}
            QLabel#statusLabel {{
                background-color: #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            QProgressBar {{
                border: 2px solid {self.ACCENT};
                border-radius: 8px;
                background-color: #1e293b;
                text-align: center;
                font-size: 12px;
                color: {self.TEXT_COLOR};
            }}
            QProgressBar::chunk {{
                background-color: {self.ACCENT};
                border-radius: 6px;
            }}
            QListWidget {{
                background-color: #1e293b;
                border: 2px solid {self.ACCENT};
                border-radius: 10px;
                color: {self.TEXT_COLOR};
                font-size: 14px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {self.ACCENT};
                color: #ffffff;
            }}
        """

    def setup_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Title
        title_label = QLabel("Jupyter Launcher")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label)

        # Running Indicator
        self.running_indicator = RunningIndicator(self)
        self.running_indicator.move(560, 20)

        # Project Directory
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select project directory")
        self.path_input.textChanged.connect(self.discover_virtual_environments)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        self.main_layout.addLayout(path_layout)

        # Virtual Environment
        self.venv_dropdown = QComboBox()
        self.main_layout.addWidget(self.venv_dropdown)

        # Status Display
        self.status_label = QLabel("Select a directory and environment")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate Environment")
        self.activate_btn.clicked.connect(self.activate_environment)
        self.launch_btn = QPushButton("Launch Jupyter Notebook")
        self.launch_btn.clicked.connect(self.launch_jupyter)
        buttons_layout.addWidget(self.activate_btn)
        buttons_layout.addWidget(self.launch_btn)
        self.main_layout.addLayout(buttons_layout)

        # File and Folder List
        file_list_label = QLabel("Directory Contents")
        file_list_label.setStyleSheet(f"color: {self.ACCENT}; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(file_list_label)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        self.main_layout.addWidget(self.file_list)

        self.main_layout.addStretch()
        self.setLayout(self.main_layout)

    def browse_path(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if selected_dir:
            self.path_input.setText(selected_dir)

    def discover_virtual_environments(self):
        self.venv_dropdown.clear()
        self.file_list.clear()
        base_path = self.path_input.text().strip()

        if not os.path.isdir(base_path):
            self.venv_dropdown.addItem("Invalid directory")
            self.venv_dropdown.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            self.status_label.setText("Invalid directory")
            self.file_list.addItem("Invalid directory")
            return

        # Populate virtual environments
        venvs = [item for item in os.listdir(base_path) 
                if os.path.isdir(os.path.join(base_path, item)) and 
                os.path.exists(os.path.join(base_path, item, "Scripts", "activate.bat"))]
        
        if not venvs:
            self.venv_dropdown.addItem("No environments found")
            self.venv_dropdown.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            self.status_label.setText("No virtual environments found")
        else:
            self.venv_dropdown.addItems(sorted(venvs))
            self.venv_dropdown.setEnabled(True)
            self.activate_btn.setEnabled(True)
            self.launch_btn.setEnabled(True)
            self.status_label.setText("Ready to launch")

        # Populate file and folder list
        try:
            for item in sorted(os.listdir(base_path)):
                item_path = os.path.join(base_path, item)
                prefix = "📁 " if os.path.isdir(item_path) else "📄 "
                self.file_list.addItem(prefix + item)
        except Exception:
            self.file_list.addItem("Error reading directory contents")

    def show_progress_animation(self):
        self.progress_bar.setVisible(True)
        self.progress_value = 0
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.start(50)

    def update_progress(self):
        self.progress_value = (self.progress_value + 5) % 100
        self.progress_bar.setValue(self.progress_value)

    def hide_progress(self):
        self.progress_bar.setVisible(False)
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()

    def launch_jupyter(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()

        if not os.path.isdir(base_path) or selected_env in ["No environments found", "Invalid directory"]:
            self.status_label.setText("Invalid directory or environment")
            return

        self.status_label.setText("Launching Jupyter Notebook...")
        self.show_progress_animation()
        self.launch_thread = CommandThread(base_path, selected_env, "jupyter")
        self.launch_thread.finished.connect(self.handle_result)
        self.launch_thread.jupyter_started.connect(self.handle_jupyter_started)
        self.launch_thread.start()

    def activate_environment(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()

        if not os.path.isdir(base_path) or selected_env in ["No environments found", "Invalid directory"]:
            self.status_label.setText("Invalid directory or environment")
            return

        self.status_label.setText("Activating environment...")
        self.show_progress_animation()
        self.activate_thread = CommandThread(base_path, selected_env, "activate")
        self.activate_thread.finished.connect(self.handle_result)
        self.activate_thread.start()

    def handle_result(self, success, message):
        self.hide_progress()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel#statusLabel {{
                background-color: {self.SUCCESS if success else self.ERROR};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                color: #ffffff;
            }}
        """)
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet(""))

    def handle_jupyter_started(self):
        self.running_indicator.set_on(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())