import sys
import os
import subprocess
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont


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
            elif self.command_type == "install_jupyter":
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}" && pip install jupyter'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}"'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            time.sleep(1)
            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook launched successfully!")
                self.jupyter_started.emit()
            elif self.command_type == "install_jupyter":
                self.finished.emit(True, "Jupyter installation started successfully!")
            else:
                self.finished.emit(True, "Virtual environment activated successfully!")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if "activate.bat" in error_msg:
                error_msg = "Error: Failed to activate virtual environment."
            elif "jupyter" in error_msg:
                error_msg = "Error: Jupyter Notebook not installed in environment."
            self.finished.emit(False, error_msg)


class RunningIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
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
        color = QColor(34, 197, 94) if self.is_on else QColor(239, 68, 68)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.black, 0.5))
        painter.drawEllipse(2, 2, 20, 20)
        if self.is_on:
            painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
            painter.translate(12, 12)
            painter.rotate(self.angle)
            painter.drawEllipse(-5, -5, 10, 10)


class JupyterLauncher(QWidget):
    BACKGROUND = "#0f172a"
    TEXT_COLOR = "#f1f5f9"
    ACCENT = "#4f46e5"
    BUTTON_BG = "#1e293b"
    BUTTON_HOVER = "#475569"
    SUCCESS = "#22c55e"
    ERROR = "#ef4444"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notebook Nexus - Chakhdi.local")
        self.resize(800, 750)  # Resizable instead of fixed size
        self.setStyleSheet(self.get_stylesheet())

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        self.main_layout = QVBoxLayout(content_widget)
        self.scroll_area.setWidget(content_widget)

        window_layout = QVBoxLayout(self)
        window_layout.addWidget(self.scroll_area)
        self.setLayout(window_layout)

        self.setup_ui()

        default_path = "P:/Codes/Machine Learning"
        self.path_input.setText(default_path if os.path.isdir(default_path) else os.path.expanduser("~"))
        self.discover_virtual_environments()

    def get_stylesheet(self):
        return f"""
        QWidget {{
            background-color: {self.BACKGROUND};
            color: {self.TEXT_COLOR};
            font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
        }}
        QLineEdit, QComboBox {{
            background-color: #1e293b;
            border: 2px solid {self.ACCENT};
            border-radius: 12px;
            padding: 12px;
            color: {self.TEXT_COLOR};
            font-size: 15px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 32px;
        }}
        QComboBox::down-arrow {{
            width: 14px;
            height: 7px;
        }}
        QPushButton {{
            background-color: {self.BUTTON_BG};
            color: {self.TEXT_COLOR};
            border: none;
            border-radius: 12px;
            padding: 14px;
            font-size: 15px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {self.BUTTON_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {self.ACCENT};
        }}
        QLabel#titleLabel {{
            font-size: 28px;
            font-weight: bold;
            color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #22d3ee);
        }}
        QLabel#statusLabel {{
            background-color: #1e293b;
            border-radius: 10px;
            padding: 12px;
            font-size: 15px;
        }}
        QProgressBar {{
            border: 2px solid {self.ACCENT};
            border-radius: 10px;
            background-color: #1e293b;
            text-align: center;
            font-size: 13px;
            color: {self.TEXT_COLOR};
        }}
        QProgressBar::chunk {{
            background-color: {self.ACCENT};
            border-radius: 8px;
        }}
        QListWidget {{
            background-color: #1e293b;
            border: 2px solid {self.ACCENT};
            border-radius: 12px;
            color: {self.TEXT_COLOR};
            font-size: 15px;
            padding: 6px;
        }}
        QListWidget::item:selected {{
            background-color: {self.ACCENT};
            color: #ffffff;
        }}
        QLabel#copyrightLabel {{
            font-size: 12px;
            color: #64748b;
            text-align: center;
        }}
        """

    def setup_ui(self):
        title_label = QLabel("📘 Notebook Nexus")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label)

        self.running_indicator = RunningIndicator(self)
        self.running_indicator.move(760, 20)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select project directory")
        self.path_input.textChanged.connect(self.discover_virtual_environments)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_path)
        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self.open_in_explorer)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        path_layout.addWidget(open_btn)
        self.main_layout.addLayout(path_layout)

        self.venv_dropdown = QComboBox()
        self.main_layout.addWidget(self.venv_dropdown)

        self.status_label = QLabel("Select a directory and environment")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        buttons_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate Env")
        self.activate_btn.clicked.connect(self.activate_environment)
        self.launch_btn = QPushButton("Launch Jupyter")
        self.launch_btn.clicked.connect(self.launch_jupyter)
        self.install_btn = QPushButton("Install Jupyter")
        self.install_btn.clicked.connect(self.install_jupyter)
        buttons_layout.addWidget(self.activate_btn)
        buttons_layout.addWidget(self.launch_btn)
        buttons_layout.addWidget(self.install_btn)
        self.main_layout.addLayout(buttons_layout)

        file_list_label = QLabel("Directory Contents")
        file_list_label.setStyleSheet(f"color: {self.ACCENT}; font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(file_list_label)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(200)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.main_layout.addWidget(self.file_list)

        copyright_label = QLabel("© 2025 Chakhdi.local | All Rights Reserved")
        copyright_label.setObjectName("copyrightLabel")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(copyright_label)

    def browse_path(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if selected_dir:
            self.path_input.setText(selected_dir)

    def open_in_explorer(self):
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            os.startfile(path)

    def show_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item:
            return

        item_text = item.text()[2:]
        item_path = os.path.join(self.path_input.text().strip(), item_text)
        menu = QMenu()
        open_action = menu.addAction("Open File/Folder")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == open_action:
            os.startfile(item_path)
        elif action == delete_action:
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    import shutil
                    shutil.rmtree(item_path)
                self.discover_virtual_environments()
                self.status_label.setText(f"Deleted: {item_text}")
            except Exception as e:
                self.status_label.setText(f"Error deleting: {str(e)}")

    def discover_virtual_environments(self):
        self.venv_dropdown.clear()
        self.file_list.clear()
        base_path = self.path_input.text().strip()
        if not os.path.isdir(base_path):
            self.venv_dropdown.addItem("Invalid directory")
            self.venv_dropdown.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            self.install_btn.setEnabled(False)
            self.status_label.setText("Invalid directory")
            return

        venvs = [d for d in os.listdir(base_path)
                 if os.path.isdir(os.path.join(base_path, d)) and
                 os.path.exists(os.path.join(base_path, d, "Scripts", "activate.bat"))]

        if not venvs:
            self.venv_dropdown.addItem("No environments found")
            self.venv_dropdown.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            self.install_btn.setEnabled(True)
            self.status_label.setText("No virtual environments found")
        else:
            self.venv_dropdown.addItems(sorted(venvs))
            self.venv_dropdown.setEnabled(True)
            self.activate_btn.setEnabled(True)
            self.launch_btn.setEnabled(True)
            self.install_btn.setEnabled(True)
            self.status_label.setText("Ready to launch - Chakhdi.local")

        for item in sorted(os.listdir(base_path)):
            prefix = "📁 " if os.path.isdir(os.path.join(base_path, item)) else "📄 "
            self.file_list.addItem(prefix + item)

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

    def install_jupyter(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()
        if not os.path.isdir(base_path) or selected_env in ["No environments found", "Invalid directory"]:
            self.status_label.setText("Invalid directory or environment")
            return
        self.status_label.setText("Installing Jupyter Notebook...")
        self.show_progress_animation()
        self.install_thread = CommandThread(base_path, selected_env, "install_jupyter")
        self.install_thread.finished.connect(self.handle_result)
        self.install_thread.start()

    def handle_result(self, success, message):
        self.hide_progress()
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            QLabel#statusLabel {{
                background-color: {self.SUCCESS if success else self.ERROR};
                border-radius: 10px;
                padding: 12px;
                font-size: 15px;
                color: #ffffff;
            }}
        """)
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet(""))
        if success and "Jupyter installation" in message:
            self.discover_virtual_environments()

    def handle_jupyter_started(self):
        self.running_indicator.set_on(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Roboto", 10))
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())
