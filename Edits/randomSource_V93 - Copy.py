import sys
import subprocess
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel,
    QPushButton, QComboBox, QFileDialog, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

# --- Thread for Jupyter Launch and Environment Activation ---
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
                self.finished.emit(True, "Jupyter Notebook launched successfully.")
                self.jupyter_started.emit()
            else:
                self.finished.emit(True, "Virtual environment activated successfully.")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if "activate.bat" in str(e):
                error_msg = "Error: Failed to activate virtual environment. Check if 'activate.bat' exists."
            elif "jupyter" in str(e):
                error_msg = "Error: Jupyter Notebook failed to launch. Ensure Jupyter is installed."
            self.finished.emit(False, error_msg)

# --- Custom Widget for Running Indicator ---
class RunningBulb(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setToolTip("Jupyter Notebook is running.\nDon't close the terminal window.")
        self.color = QColor(255, 99, 71)  # Tomato red when off
        self.is_on = False
        self.setVisible(False)

    def set_on(self, on=True):
        self.is_on = on
        self.color = QColor(50, 205, 50) if on else QColor(255, 99, 71)  # Lime green when on
        self.setVisible(True)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bulb_color = self.color if self.is_on else QColor(100, 100, 100)
        painter.setBrush(QBrush(bulb_color))
        painter.setPen(QPen(Qt.GlobalColor.black, 0.5))
        painter.drawEllipse(2, 2, self.width() - 4, self.height() - 4)
        if self.is_on:
            highlight_color = QColor(255, 255, 255, 80)
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(4, 4, self.width() // 3, self.height() // 3)

# --- Main Application Window ---
class JupyterLauncher(QWidget):
    # Modern color scheme
    BACKGROUND = "#18181b"  # Zinc-900
    TEXT_COLOR = "#f4f4f5"  # Zinc-100
    ACCENT_BLUE = "#3b82f6"  # Blue-500
    INPUT_BG = "#27272a"  # Zinc-800
    BUTTON_BG = "#3f3f46"  # Zinc-700
    BUTTON_HOVER = "#52525b"  # Zinc-600
    BUTTON_PRESSED = "#27272a"  # Zinc-800
    ERROR_COLOR = "#d9534f"  # Red from CustomUI
    SUCCESS_COLOR = "#28a745"  # Green from CustomUI
    SEPARATOR_COLOR = "#3f3f46"  # Zinc-700

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jupyter Notebook Launcher")
        self.setFixedSize(600, 450)  # Fixed size as in provided code
        self.setStyleSheet(self.get_stylesheet())
        self.setup_ui()
        
        default_path = "D:/Codes/Machine Learning"
        if os.path.exists(default_path) and os.path.isdir(default_path):
            self.path_input.setText(default_path)
        else:
            self.path_input.setText(os.path.expanduser("~"))

        self.discover_virtual_environments()

    def get_stylesheet(self):
        return f"""
            QWidget {{
                background-color: {self.BACKGROUND};
                color: {self.TEXT_COLOR};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}

            /* === QComboBox === */
            QComboBox {{
                background-color: {self.INPUT_BG};
                border: 1px solid {self.ACCENT_BLUE};
                border-radius: 8px;
                padding: 8px 12px;
                color: {self.TEXT_COLOR};
                font-size: 13px;
                font-weight: 500;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 30px;
                background-color: {self.INPUT_BG};
            }}

            QComboBox::down-arrow {{
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAHCAYAAADXCDzzAAAAAXNSR0IArs4c6QAAADhJREFUKFOd0LEJACAMxND/f7kbkBA2kUkhpV2EJOJ3+CA4iYUzF8wL0D0M3fLCTnADb0n1AZpZBlz0l1+xAAAAAElFTkSuQmCC);
                width: 10px;
                height: 5px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {self.INPUT_BG};
                border: 1px solid {self.ACCENT_BLUE};
                border-radius: 6px;
                padding: 4px;
                color: {self.TEXT_COLOR};
                selection-background-color: {self.ACCENT_BLUE};
                selection-color: {self.BACKGROUND};
            }}

            QComboBox QAbstractItemView::item {{
                padding: 8px;
                min-height: 24px;
            }}

            /* === QLineEdit === */
            QLineEdit {{
                background-color: {self.INPUT_BG};
                border: 1px solid {self.ACCENT_BLUE};
                border-radius: 8px;
                padding: 8px 12px;
                color: {self.TEXT_COLOR};
                font-size: 13px;
                font-weight: 500;
            }}

            QLineEdit:focus {{
                border: 2px solid {self.ACCENT_BLUE};
            }}

            /* === QPushButton === */
            QPushButton {{
                background-color: {self.BUTTON_BG};
                color: {self.TEXT_COLOR};
                border: 1px solid {self.BUTTON_BG};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {self.BUTTON_HOVER};
                border: 1px solid {self.ACCENT_BLUE};
            }}

            QPushButton:pressed {{
                background-color: {self.BUTTON_PRESSED};
            }}

            /* === QLabel#currentCommandDisplay === */
            QLabel#currentCommandDisplay {{
                background-color: {self.INPUT_BG};
                border: 1px solid {self.ACCENT_BLUE};
                border-radius: 8px;
                padding: 12px;
                color: {self.TEXT_COLOR};
                font-family: 'Consolas', monospace;
                font-size: 12px;
                font-weight: 500;
            }}

            /* === QLabel#toastLabel === */
            QLabel#toastLabel {{
                background-color: transparent;
                color: #ffffff;
                padding: 10px;
                border-radius: 6px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 12px;
                font-weight: bold;
                text-align: center;
                min-height: 16px;
            }}

            /* === QFrame#separator === */
            QFrame#separator {{
                background-color: {self.SEPARATOR_COLOR};
            }}

            /* === Section Headers === */
            QLabel#sectionHeader {{
                color: {self.ACCENT_BLUE};
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 6px;
            }}
        """

    def setup_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(12)

        # Create a container widget for all content except the toast
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.content_widget.setLayout(self.content_layout)

        # Running Bulb Indicator
        self.running_bulb = RunningBulb(self)
        self.running_bulb.move(self.width() - 28, 12)

        # Project Directory Section
        self.setup_project_directory_section()

        # Separator
        self.content_layout.addWidget(self.create_separator())

        # Virtual Environment Section
        self.setup_venv_section()

        # Separator
        self.content_layout.addWidget(self.create_separator())

        # Command Display Section
        self.setup_command_display_section()

        # Buttons Section
        self.setup_buttons_section()

        # Add content widget to main layout with stretch to push it up
        self.main_layout.addWidget(self.content_widget)
        self.main_layout.addStretch(1)

        # Toast Message
        self.setup_toast_message()

        self.setLayout(self.main_layout)
        self.update_command_display()

    def setup_project_directory_section(self):
        script_location_label = QLabel("Project Directory")
        script_location_label.setObjectName("sectionHeader")
        self.content_layout.addWidget(script_location_label)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select project root directory")
        self.path_input.setMinimumHeight(36)
        self.path_input.textChanged.connect(self.discover_virtual_environments)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_path)
        browse_btn.setFixedWidth(100)
        browse_btn.setMinimumHeight(36)

        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        self.content_layout.addLayout(path_layout)

    def setup_venv_section(self):
        venv_label = QLabel("Virtual Environment")
        venv_label.setObjectName("sectionHeader")
        self.content_layout.addWidget(venv_label)

        self.venv_dropdown = QComboBox()
        self.venv_dropdown.setMinimumHeight(36)
        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Medium)
        self.venv_dropdown.setFont(font)
        self.content_layout.addWidget(self.venv_dropdown)

    def setup_command_display_section(self):
        current_cmd_label = QLabel("Generated Command")
        current_cmd_label.setObjectName("sectionHeader")
        self.content_layout.addWidget(current_cmd_label)

        self.command_display = QLabel('')
        self.command_display.setObjectName("currentCommandDisplay")
        self.command_display.setWordWrap(True)
        self.command_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.command_display.setMinimumHeight(80)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.command_display.setFont(font)
        self.content_layout.addWidget(self.command_display)

        self.path_input.textChanged.connect(self.update_command_display)
        self.venv_dropdown.currentTextChanged.connect(self.update_command_display)

    def setup_buttons_section(self):
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.activate_button = QPushButton("Activate Environment")
        self.activate_button.setToolTip("Opens a terminal and activates the selected environment")
        self.activate_button.clicked.connect(self.activate_environment)
        self.activate_button.setMinimumWidth(180)
        buttons_layout.addWidget(self.activate_button)

        self.launch_button = QPushButton("Launch Jupyter Notebook")
        self.launch_button.setToolTip("Launches Jupyter Notebook in the selected environment")
        self.launch_button.clicked.connect(self.launch_jupyter)
        self.launch_button.setMinimumWidth(180)
        buttons_layout.addWidget(self.launch_button)

        self.content_layout.addLayout(buttons_layout)

    def setup_toast_message(self):
        self.toast_label = QLabel("", self)
        self.toast_label.setObjectName("toastLabel")
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.hide()
        self.main_layout.addWidget(self.toast_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.hide_toast)

    def create_separator(self):
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        return separator

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.running_bulb.move(self.width() - 28, 12)

    def browse_path(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if selected_dir:
            self.path_input.setText(selected_dir)

    def discover_virtual_environments(self):
        self.venv_dropdown.clear()
        base_path = self.path_input.text().strip()

        valid_envs_found = False

        if not os.path.isdir(base_path):
            self.venv_dropdown.addItem("Invalid path or no environments found")
            self.venv_dropdown.setEnabled(False)
        else:
            found_venvs = []
            for item in os.listdir(base_path):
                full_path = os.path.join(base_path, item)
                if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, "Scripts", "activate.bat")):
                    found_venvs.append(item)

            if not found_venvs:
                self.venv_dropdown.addItem("No virtual environments found")
                self.venv_dropdown.setEnabled(False)
            else:
                self.venv_dropdown.addItems(sorted(found_venvs))
                self.venv_dropdown.setEnabled(True)
                valid_envs_found = True

        self.activate_button.setEnabled(valid_envs_found)
        self.launch_button.setEnabled(valid_envs_found)
        self.update_command_display()

    def update_command_display(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()

        venv_placeholder = "<selected_venv>"
        if selected_env not in ["No virtual environments found", "Invalid path or no environments found"] and selected_env:
            venv_placeholder = selected_env

        path_placeholder = "<path_to_project>"
        if base_path:
            path_placeholder = base_path

        activate_cmd = f'"{venv_placeholder}\\Scripts\\activate.bat"'
        cmd_parts = [
            f'cd /d "{path_placeholder}"',
            activate_cmd,
            "jupyter notebook"
        ]
        
        formatted_cmd = " && \\\n    ".join(cmd_parts)
        self.command_display.setText(formatted_cmd)

    def show_toast(self, message, is_success=True):
        prefix = "✅ " if is_success else "⚠ "
        self.toast_label.setText(prefix + message)
        bg_color = self.SUCCESS_COLOR if is_success else self.ERROR_COLOR
        self.toast_label.setStyleSheet(f"""
            QLabel#toastLabel {{
                background-color: {bg_color};
                color: #ffffff;
                padding: 10px;
                border-radius: 6px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 12px;
                font-weight: bold;
                min-height: 16px;
                text-align: center;
                border: 1px solid {self.ACCENT_BLUE};
            }}
        """)
        self.toast_label.show()
        self.toast_timer.start(2000)

    def hide_toast(self):
        self.toast_label.setText("")
        self.toast_label.setStyleSheet("")
        self.toast_label.hide()

    def handle_launch_result(self, success, message):
        self.show_toast(message, success)

    def handle_jupyter_started(self):
        self.running_bulb.set_on(True)

    def launch_jupyter(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()

        if not os.path.isdir(base_path):
            self.show_toast("Error: Invalid project directory.", False)
            return

        if selected_env in ["No virtual environments found", "Invalid path or no environments found"] or not selected_env:
            self.show_toast("Error: Select a valid virtual environment.", False)
            return

        self.show_toast("Launching Jupyter Notebook...", True)
        self.launch_thread = CommandThread(base_path, selected_env, command_type="jupyter")
        self.launch_thread.finished.connect(self.handle_launch_result)
        self.launch_thread.jupyter_started.connect(self.handle_jupyter_started)
        self.launch_thread.start()

    def activate_environment(self):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()

        if not os.path.isdir(base_path):
            self.show_toast("Error: Invalid project directory.", False)
            return

        if selected_env in ["No virtual environments found", "Invalid path or no environments found"] or not selected_env:
            self.show_toast("Error: Select a valid virtual environment.", False)
            return

        self.show_toast("Activating virtual environment...", True)
        self.activate_thread = CommandThread(base_path, selected_env, command_type="activate")
        self.activate_thread.finished.connect(self.handle_launch_result)
        self.activate_thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())