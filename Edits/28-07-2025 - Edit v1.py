import sys
import os
import subprocess
import time
import shutil
import traceback
import json
import tempfile
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip,
    QMessageBox, QStyle, QFrame, QTextEdit, QDialog, QListWidgetItem,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot, QSettings
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction

def global_exception_hook(exctype, value, tb):
    error_message = f"An unexpected error occurred:\n\n{value}"
    traceback_details = "".join(traceback.format_tb(tb))
    try:
        with open("error_log.txt", "a") as f:
            f.write(f"--- {time.ctime()} ---\n")
            f.write(f"{error_message}\n")
            f.write(f"{traceback_details}\n\n")
    except Exception as e:
        print(f"Error logging failed: {e}")

    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Unhandled Application Error")
    error_box.setText(error_message)
    error_box.setDetailedText(traceback_details)
    error_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_box.exec()

    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

class CommandThread(QThread):
    finished = pyqtSignal(bool, str)
    process_started = pyqtSignal()
    output_received = pyqtSignal(str)

    def __init__(self, base_path, selected_env=None, command_type="jupyter", **kwargs):
        super().__init__()
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type
        self.kwargs = kwargs
        self.process = None

    def run(self):
        try:
            cmd_list = []
            shell = False
            
            if sys.platform == "win32":
                full_cmd_prefix = f'cmd.exe /c "cd /d "{self.base_path}" && '
            else:
                self.finished.emit(False, "Unix-like OS execution is not yet implemented.")
                return

            if self.command_type == "create_venv":
                new_env_name = self.kwargs.get("new_env_name")
                cmd_list = [ 'python', '-m', 'venv', new_env_name]
                full_cmd = full_cmd_prefix + ' '.join(cmd_list) + '"'
                shell = True
            elif self.command_type == "get_env_details":
                 cmd_list = [ 'python', '--version' ]
                 full_cmd = self._get_activated_command(cmd_list)
                 shell = True
            elif self.command_type == "freeze":
                cmd_list = [ 'pip', 'freeze' ]
                full_cmd = self._get_activated_command(cmd_list)
                shell = True
            else:
                if not self.selected_env:
                     raise ValueError("An environment must be selected.")
                
                cmd_list = None
                if self.command_type == "launch":
                    tool = self.kwargs.get("tool", "jupyter notebook")
                    cmd_list = tool.split()
                elif self.command_type == "install_requirements":
                    req_path = self.kwargs.get("requirements_path")
                    cmd_list = ['pip', 'install', '-r', f'"{req_path}"']
                elif self.command_type == "activate":
                    cmd_list = []
                
                if cmd_list is None:
                    self.finished.emit(False, f"Unsupported command type: {self.command_type}")
                    return

                full_cmd = self._get_activated_command(cmd_list, new_console=True)
                shell=True

            if full_cmd:    
                self.process = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if shell else 0,
                    shell=shell
                )
                self.process_started.emit()

                for line in iter(self.process.stdout.readline, ''):
                    self.output_received.emit(line.strip())
                self.process.stdout.close()
                return_code = self.process.wait()

                if return_code == 0:
                    self.finished.emit(True, f"Command '{self.command_type}' completed successfully.")
                else:
                    self.finished.emit(False, f"Command '{self.command_type}' failed with exit code {return_code}.")
            else:
                self.finished.emit(True, "Process launched in new terminal.")


        except FileNotFoundError as e:
            self.finished.emit(False, f"Error: A required file was not found. {str(e)}")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred: {str(e)}")

    def _get_activated_command(self, cmd_list, new_console=False):
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        activate_script_path = os.path.join(self.base_path, self.selected_env, script_folder, "activate.bat")
        
        if not os.path.exists(activate_script_path):
            raise FileNotFoundError(f"Activation script not found: {activate_script_path}")
        
        command_str = ' '.join(cmd_list)
        
        base_path_norm = os.path.normpath(self.base_path)
        activate_script_norm = os.path.normpath(activate_script_path)

        if new_console:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.bat', newline='\r\n') as bat_file:
                temp_bat_path = bat_file.name
                bat_file.write('@echo off\n')
                bat_file.write(f'cd /d "{base_path_norm}"\n')
                bat_file.write(f'call "{activate_script_norm}"\n')
                if command_str:
                    bat_file.write(f'{command_str}\n')
                if not command_str:
                     bat_file.write('echo.\n')
                     bat_file.write('echo Environment is now active in this terminal.\n')

            full_cmd = f'start "PyEnv Launcher - {self.selected_env}" cmd.exe /k "{temp_bat_path}"'
            
            QTimer.singleShot(10000, lambda: os.remove(temp_bat_path))
            
            return full_cmd
            
        else:
            commands_to_run = f'cd /d "{base_path_norm}" && call "{activate_script_norm}" && {command_str}'
            return f'cmd.exe /c "{commands_to_run}"'

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        if event.event_type in ['created', 'deleted', 'moved']:
            self.callback()

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About PyEnv Launcher")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title_label = QLabel("PyEnv Launcher")
        title_label.setObjectName("aboutTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        company_label = QLabel("<b>Company : </b> Chakhdi.local")
        year_label = QLabel("<b>Year : </b> 2025")
        copyright_label = QLabel("Copyright © 2025 Chakhdi.local - All Rights Reserved")

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        terms_label = QLabel("<b>Terms and Conditions:</b>")
        terms_text = QTextEdit()
        terms_text.setReadOnly(True)
        terms_text.setText(
            "This software is provided 'as-is', without any express or implied warranty. In no event will the authors be held liable for any damages arising from the use of this software.\n\n"
            "Permission is granted to anyone to use this software for any purpose, including commercial applications, and to alter it and redistribute it freely, subject to the following restrictions:\n\n"
            "1. The origin of this software must not be misrepresented; you must not claim that you wrote the original software. If you use this software in a product, an acknowledgment in the product documentation would be appreciated but is not required.\n"
            "2. Altered source versions must be plainly marked as such, and must not be misrepresented as being the original software.\n"
            "3. This notice may not be removed or altered from any source distribution."
        )
        terms_text.setFixedHeight(200)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)

        layout.addWidget(title_label)
        layout.addWidget(company_label)
        layout.addWidget(year_label)
        layout.addWidget(copyright_label)
        layout.addWidget(separator)
        layout.addWidget(terms_label)
        layout.addWidget(terms_text)
        layout.addWidget(self.button_box)

        # Apply basic styling to match the main window's theme
        c = parent.current_theme
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c['primary']}; border: 1px solid {c['border']}; border-radius: 8px; }}
            QLabel, QTextEdit {{ color: {c['text']}; background: transparent; }}
            #aboutTitle {{ font-size: 14pt; font-weight: bold; color: {c['text_header']}; }}
            QTextEdit {{ background-color: {c['background']}; }}
            QPushButton {{ background-color: {c['border']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 8px; font-weight: bold; }}
            QPushButton:hover {{ border-color: #8b949e; }}
        """)
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        
        layout = QVBoxLayout(self)
        
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        
        default_path_label = QLabel("Default Project Directory:")
        self.default_path_input = QLineEdit()
        self.browse_button = QPushButton("Browse...")
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.default_path_input)
        path_layout.addWidget(self.browse_button)

        layout.addWidget(theme_label)
        layout.addWidget(self.theme_combo)
        layout.addWidget(default_path_label)
        layout.addLayout(path_layout)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.browse_button.clicked.connect(self._browse_default_path)

        self._load_settings()

    def _load_settings(self):
        theme = self.settings.value("theme", "Dark")
        self.theme_combo.setCurrentText(theme)
        default_path = self.settings.value("default_path", os.path.expanduser("~"))
        self.default_path_input.setText(default_path)

    def _browse_default_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Default Directory", self.default_path_input.text())
        if path:
            self.default_path_input.setText(path)

    def accept(self):
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("default_path", self.default_path_input.text())
        super().accept()

class JupyterLauncher(QWidget):
    DARK_THEME = {
        "background": "#0d1117", "primary": "#161b22", "border": "#30363d",
        "text": "#c9d1d9", "text_header": "#f0f6fc", "text_secondary": "#8b949e",
        "accent": "#2f81f7", "success": "#238636", "error": "#da3633", "border_window": "#87CEEB"
    }
    LIGHT_THEME = {
        "background": "#f6f8fa", "primary": "#ffffff", "border": "#d0d7de",
        "text": "#24292f", "text_header": "#24292f", "text_secondary": "#57606a",
        "accent": "#0969da", "success": "#1a7f37", "error": "#cf222e", "border_window": "#0969da"
    }
    FONT_MAIN = "Segoe UI"

    def __init__(self):
        super().__init__()
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.current_theme = self.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else self.LIGHT_THEME
        
        self.setWindowTitle("PyEnv Launcher")
        self.setObjectName("JupyterLauncher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 800)

        self.observer = None
        self.old_pos = None
        self.command_thread = None

        self._setup_main_layout()
        self._setup_ui_components()
        self._apply_stylesheet()
        self._connect_signals()

        self._load_app_settings()
        self._update_file_observer()
        self.discover_virtual_environments()

    def _setup_main_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.main_layout.addWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        self.container_layout.setSpacing(0)

    def _setup_ui_components(self):
        title_bar = self._create_title_bar()
        self.container_layout.addWidget(title_bar)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.container_layout.addWidget(scroll_area)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(15)
        
        content_layout.addLayout(self._create_path_section())
        content_layout.addLayout(self._create_new_venv_section())
        content_layout.addWidget(self._create_separator())
        content_layout.addLayout(self._create_manage_venv_section())
        content_layout.addLayout(self._create_files_section())
        content_layout.addLayout(self._create_log_section())
        content_layout.addStretch()
        content_layout.addLayout(self._create_footer_section())

    def _create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        
        self.about_btn = QPushButton("?")
        self.about_btn.setObjectName("controlBtn")
        self.about_btn.setToolTip("About PyEnv Launcher")
        self.about_btn.setFixedSize(30, 30)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.settings_btn.setObjectName("controlBtn")
        self.settings_btn.setToolTip("Open Settings")
        
        title = QLabel("📘 PyEnv Launcher")
        title.setObjectName("titleLabel")
        
        self.running_indicator = QLabel("●")
        self.running_indicator.setObjectName("runningIndicator")
        self.running_indicator.setVisible(False)
        self.running_indicator.setToolTip("A command process is currently active.")
        
        minimize_btn = QPushButton("—")
        close_btn = QPushButton("✕")
        for btn, tip in [(minimize_btn, "Minimize"), (close_btn, "Close")]:
            btn.setObjectName("controlBtn")
            btn.setFixedSize(30, 30)
            btn.setToolTip(tip)
            
        layout.addWidget(self.about_btn)
        layout.addWidget(self.settings_btn)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.running_indicator)
        layout.addWidget(minimize_btn)
        layout.addWidget(close_btn)
        return title_bar

    def _create_path_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Project Directory"))
        path_layout = QHBoxLayout()
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter or browse to your project path")
        self.path_input.setToolTip("The main folder for your project and environments.")
        
        self.recent_paths_btn = QPushButton("▼")
        self.recent_paths_btn.setObjectName("recentBtn")
        self.recent_paths_btn.setFixedWidth(30)
        self.recent_paths_btn.setToolTip("Show recent project paths")
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.recent_paths_btn)
        layout.addLayout(path_layout)
        
        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Select Directory")
        self.browse_btn.setToolTip("Browse for a project directory.")
        self.open_btn = QPushButton("Open Path")
        self.open_btn.setToolTip("Open the current directory in the file explorer.")
        btn_layout.addWidget(self.browse_btn)
        btn_layout.addWidget(self.open_btn)
        layout.addLayout(btn_layout)
        return layout

    def _create_new_venv_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Create New Environment"))
        creation_layout = QHBoxLayout()
        self.new_venv_name_input = QLineEdit()
        self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.new_venv_name_input.setToolTip("Name for the new virtual environment (e.g., .venv, env).")
        
        self.create_venv_btn = QPushButton("Create")
        self.create_venv_btn.setObjectName("createBtn")
        self.create_venv_btn.setToolTip("Create a new Python virtual environment in the project directory.")
        
        creation_layout.addWidget(self.new_venv_name_input)
        creation_layout.addWidget(self.create_venv_btn)
        layout.addLayout(creation_layout)
        return layout

    def _create_manage_venv_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Manage Existing Environment"))
        
        env_select_layout = QHBoxLayout()
        self.venv_dropdown = QComboBox()
        self.venv_dropdown.setToolTip("Select an existing virtual environment.")
        self.delete_venv_btn = QPushButton("🗑️")
        self.delete_venv_btn.setObjectName("deleteBtn")
        self.delete_venv_btn.setFixedWidth(40)
        self.delete_venv_btn.setToolTip("Permanently delete the selected environment.")
        env_select_layout.addWidget(self.venv_dropdown)
        env_select_layout.addWidget(self.delete_venv_btn)
        layout.addLayout(env_select_layout)

        self.env_details_label = QLabel("Select an environment to see details.")
        self.env_details_label.setObjectName("detailsLabel")
        layout.addWidget(self.env_details_label)

        pkg_layout = QHBoxLayout()
        self.install_reqs_btn = QPushButton("Install from File")
        self.install_reqs_btn.setToolTip("Install packages from a requirements.txt or similar file.")
        self.freeze_btn = QPushButton("Freeze to requirements.txt")
        self.freeze_btn.setToolTip("Save all installed packages into a requirements.txt file.")
        pkg_layout.addWidget(self.install_reqs_btn)
        pkg_layout.addWidget(self.freeze_btn)
        layout.addLayout(pkg_layout)

        launch_buttons_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setToolTip("Open a new command prompt with the environment activated.")
        self.launch_jupyter_btn = QPushButton("Launch Jupyter")
        self.launch_jupyter_btn.setObjectName("launchBtn")
        self.launch_jupyter_btn.setToolTip("Launch Jupyter Notebook in the activated environment.")
        
        launch_buttons_layout.addWidget(self.activate_btn)
        launch_buttons_layout.addWidget(self.launch_jupyter_btn)
        layout.addLayout(launch_buttons_layout)
        
        return layout

    def _create_files_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Project Directory Contents"))
        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.file_list)
        return layout
    
    def _create_log_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(4)
        log_header_layout = QHBoxLayout()
        log_header_layout.addWidget(QLabel("Activity Log"))
        log_header_layout.addStretch()
        self.clear_log_btn = QPushButton("Clear")
        self.clear_log_btn.setToolTip("Clear the activity log.")
        log_header_layout.addWidget(self.clear_log_btn)
        layout.addLayout(log_header_layout)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("logOutput")
        self.log_output.setFixedHeight(100)
        layout.addWidget(self.log_output)
        return layout

    def _create_footer_section(self):
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 5, 0, 0)
        self.status_label = QLabel("Welcome!")
        self.status_label.setObjectName("statusLabel")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)

        sizegrip = QSizeGrip(self.container)
        sizegrip.setFixedSize(16, 16)
        
        status_layout = QVBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        footer_layout.addLayout(status_layout, 1)
        footer_layout.addWidget(sizegrip)
        return footer_layout

    def _connect_signals(self):
        self.about_btn.clicked.connect(self._open_about_dialog)
        self.settings_btn.clicked.connect(self._open_settings)
        self.path_input.textChanged.connect(self._on_path_changed)
        self.recent_paths_btn.clicked.connect(self._show_recent_paths_menu)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        self.create_venv_btn.clicked.connect(self._create_environment)
        self.venv_dropdown.currentTextChanged.connect(self._on_venv_selection_changed)
        self.delete_venv_btn.clicked.connect(self._delete_environment)
        self.install_reqs_btn.clicked.connect(self._install_requirements)
        self.freeze_btn.clicked.connect(self._freeze_requirements)
        self.activate_btn.clicked.connect(self._activate_environment)
        self.launch_jupyter_btn.clicked.connect(self._launch_jupyter)
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        self.clear_log_btn.clicked.connect(self.log_output.clear)
        
        title_bar = self.container_layout.itemAt(0).widget()
        control_buttons = title_bar.findChildren(QPushButton)
        control_buttons[-1].clicked.connect(self.close)
        control_buttons[-2].clicked.connect(self.showMinimized)

    def _apply_stylesheet(self):
        c = self.current_theme
        self.setStyleSheet(f"""
            #JupyterLauncher {{ background-color: transparent; }}
            #container {{ background-color: {c['primary']}; border: 2px solid {c['border_window']}; border-radius: 15px; }}
            QWidget {{ font-family: "{self.FONT_MAIN}"; color: {c['text']}; font-size: 9pt; }}
            #titleBar {{ background-color: {c['background']}; border-top-left-radius: 13px; border-top-right-radius: 13px; }}
            #titleLabel {{ color: {c['text_header']}; font-weight: bold; font-size: 11pt; padding-left: 5px;}}
            #controlBtn, #recentBtn, #deleteBtn {{ background: transparent; border: none; font-size: 12pt; font-weight: bold; }}
            #controlBtn:hover, #recentBtn:hover, #deleteBtn:hover {{ background: {c['border']}; border-radius: 4px; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
            QLabel {{ font-weight: bold; background: transparent;}}
            #detailsLabel {{ font-weight: normal; color: {c['text_secondary']}; }}
            QLineEdit, QComboBox, QTextEdit {{ background-color: {c['background']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 7px; }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
            QComboBox QAbstractItemView {{ background-color: {c['background']}; border: 1px solid {c['border']}; selection-background-color: {c['accent']}; color: {c['text']}; outline: 0px; }}
            QComboBox QAbstractItemView::item {{ padding: 10px 6px; }}
            QPushButton {{ background-color: {c['border']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 8px; font-weight: bold; }}
            QPushButton:hover {{ border-color: #8b949e; }}
            QPushButton:pressed {{ background-color: #21262d; }}
            QPushButton:disabled {{ background-color: {c['border']}; color: {c['text_secondary']}; border-color: {c['border']}; }}
            #launchBtn {{ background-color: {c['success']}; border-color: #318a44; }}
            #launchBtn:hover {{ background-color: #318a44; }}
            #createBtn {{ background-color: {c['accent']}; border-color: #3e8bf7; }}
            #createBtn:hover {{ background-color: #3e8bf7; }}
            #statusLabel {{ font-weight: normal; background-color: transparent; }}
            #runningIndicator {{ color: {c['success']}; font-size: 16pt; font-weight: bold; padding-bottom: 4px; }}
            QProgressBar {{ border-radius: 3px; background-color: {c['border']}; text-align: center; }}
            QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 3px; }}
            QListWidget, #logOutput {{ background-color: {c['background']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 4px; }}
            QListWidget::item {{ padding: 6px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: {c['border']}; }}
            QListWidget::item:selected {{ background-color: {c['accent']}; color: white; }}
            QMenu {{ background-color: {c['primary']}; border: 1px solid {c['border']}; }}
            QMenu::item:selected {{ background-color: {c['accent']}; }}
        """)
    
    def _run_command(self, command_type, on_finish=None, **kwargs):
        if self.command_thread and self.command_thread.isRunning():
            self._update_status("A command is already running.", "error")
            return

        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()
        if not os.path.isdir(base_path):
             self._update_status("Invalid directory selected.", "error")
             return
        if command_type not in ["create_venv"] and ("found" in selected_env or "Invalid" in selected_env):
            self._update_status("Invalid environment selected.", "error")
            return
        
        self.command_thread = CommandThread(base_path, selected_env, command_type, **kwargs)
        self.command_thread.output_received.connect(self._log_message)
        self.command_thread.process_started.connect(lambda: self._set_progress_bar_active(True))
        self.command_thread.finished.connect(lambda s, m: self._on_command_finished(s, m, on_finish))
        
        self.command_thread.start()
        self._log_message(f"Starting command: {command_type}...")

    def _on_command_finished(self, success, message, on_finish_callback):
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")
        self._log_message(f"Finished: {message}")
        if success and on_finish_callback:
            on_finish_callback()
        self.command_thread = None

    def _open_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings.sync()
            self.current_theme = self.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else self.LIGHT_THEME
            self._apply_stylesheet()
            self._update_status("Settings saved.", "info")

    def _load_app_settings(self):
        self.current_theme = self.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else self.LIGHT_THEME
        default_path = self.settings.value("default_path", os.path.expanduser("~"))
        if not self.path_input.text():
            self.path_input.setText(default_path)
        self._add_to_recent_paths(self.path_input.text())
            
    def _on_path_changed(self):
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True)
            self._path_change_timer.timeout.connect(self._update_path_resources)
        self._path_change_timer.start(500)

    def _update_path_resources(self):
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            self.discover_virtual_environments()
            self._update_file_observer()
            self._add_to_recent_paths(path)

    def _add_to_recent_paths(self, path):
        if not path or not os.path.isdir(path): return
        recent_paths = self.settings.value("recent_paths", [], type=list)
        if path in recent_paths:
            recent_paths.remove(path)
        recent_paths.insert(0, path)
        self.settings.setValue("recent_paths", recent_paths[:10])

    def _show_recent_paths_menu(self):
        recent_paths = self.settings.value("recent_paths", [], type=list)
        if not recent_paths:
            self._update_status("No recent paths found.", "info")
            return
        menu = QMenu(self)
        for path in recent_paths:
            action = QAction(path, self)
            action.triggered.connect(lambda checked, p=path: self.path_input.setText(p))
            menu.addAction(action)
        menu.exec(self.recent_paths_btn.mapToGlobal(QPoint(0, self.recent_paths_btn.height())))
        
    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.path_input.text())
        if path:
            self.path_input.setText(path)

    def _open_in_explorer(self):
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        else: self._update_status("Directory not found.", "error")

    def _create_environment(self):
        base_path = self.path_input.text().strip()
        new_env_name = self.new_venv_name_input.text().strip()
        if not new_env_name or ' ' in new_env_name:
            self._update_status("Provide a valid name with no spaces.", "error")
            return
        if os.path.exists(os.path.join(base_path, new_env_name)):
            self._update_status(f"'{new_env_name}' already exists.", "error")
            return
        self._run_command("create_venv", new_env_name=new_env_name, on_finish=self.discover_virtual_environments)
        self.new_venv_name_input.clear()

    def _delete_environment(self):
        env_name = self.venv_dropdown.currentText()
        if not env_name or "found" in env_name: return

        reply = QMessageBox.question(self, 'Confirm Deletion', 
            f"Are you sure you want to permanently delete the environment '{env_name}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            env_path = os.path.join(self.path_input.text().strip(), env_name)
            self._log_message(f"Attempting to delete {env_path}...")
            shutil.rmtree(env_path, ignore_errors=True)
            QTimer.singleShot(500, self.discover_virtual_environments)
            self._update_status(f"Environment '{env_name}' deleted.", "success")
            self._log_message(f"Successfully deleted environment '{env_name}'.")

    def _on_venv_selection_changed(self, env_name):
        if not env_name or "found" in env_name:
            self.env_details_label.setText("Select an environment to see details.")
            return
        
        self.env_details_label.setText("Fetching details...")
        self._run_command("get_env_details", on_finish=self._update_env_details)
        
    def _update_env_details(self):
        env_name = self.venv_dropdown.currentText()
        env_path = os.path.join(self.path_input.text().strip(), env_name)
        
        last_line = self.log_output.toPlainText().strip().split('\n')[-1]
        py_version = "Unknown"
        if "Python" in last_line:
            py_version = last_line
            
        creation_date = time.ctime(os.path.getctime(env_path))
        self.env_details_label.setText(f"Path: {env_path} | Version: {py_version} | Created: {creation_date}")
        self.env_details_label.setToolTip(self.env_details_label.text())

    def _install_requirements(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Requirements File", self.path_input.text(), "Text Files (*.txt)")
        if path:
            self._run_command("install_requirements", requirements_path=path)

    def _freeze_requirements(self):
        self._run_command("freeze", on_finish=self._save_freeze_output)

    def _save_freeze_output(self):
        output = []
        for line in self.log_output.toPlainText().strip().split('\n'):
             if "pip freeze" in line or "Starting command" in line or "Finished" in line:
                 continue
             output.append(line)
        
        try:
            with open(os.path.join(self.path_input.text().strip(), "requirements.txt"), "w") as f:
                f.write("\n".join(output))
            self._update_status("requirements.txt generated successfully.", "success")
            self.discover_virtual_environments()
        except Exception as e:
            self._update_status(f"Failed to write requirements.txt: {e}", "error")

    def _activate_environment(self):
        self._run_command("activate")

    def _launch_jupyter(self):
        self._run_command("launch", tool="jupyter notebook")

    def _show_file_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item: return

        item_path = os.path.join(self.path_input.text().strip(), item.text())
        if not os.path.exists(item_path): return
        
        menu = QMenu()
        open_action = menu.addAction("📂 Open")
        copy_path_action = menu.addAction("🔗 Copy Path")
        delete_action = menu.addAction("🗑️ Delete")

        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == open_action:
            if sys.platform == "win32": os.startfile(item_path)
        elif action == copy_path_action:
            QGuiApplication.clipboard().setText(item_path)
            self._update_status("Path copied to clipboard.", "info")
        elif action == delete_action:
            reply = QMessageBox.question(self, 'Confirm Deletion', f"Permanently delete '{item.text()}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if os.path.isdir(item_path): shutil.rmtree(item_path)
                    else: os.remove(item_path)
                    self.discover_virtual_environments()
                except Exception as e:
                    self._update_status(f"Error deleting: {e}", "error")

    def discover_virtual_environments(self):
        base_path = self.path_input.text().strip()
        self.file_list.clear()

        all_widgets = [self.open_btn, self.new_venv_name_input, self.create_venv_btn, self.venv_dropdown,
                       self.delete_venv_btn, self.install_reqs_btn, self.freeze_btn, self.activate_btn, self.launch_jupyter_btn]
        env_dependent_widgets = [self.venv_dropdown, self.delete_venv_btn, self.install_reqs_btn, self.freeze_btn,
                                 self.activate_btn, self.launch_jupyter_btn]

        if not os.path.isdir(base_path):
            for widget in all_widgets: widget.setEnabled(False)
            return

        for widget in all_widgets: widget.setEnabled(True)
        
        try:
            dir_contents = sorted(os.listdir(base_path))
            for name in dir_contents:
                item = QListWidgetItem(name)
                if os.path.isdir(os.path.join(base_path, name)):
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                self.file_list.addItem(item)
        except PermissionError:
            self._update_status("Permission denied to read directory.", "error")
            return

        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        venvs = [d for d in dir_contents if os.path.isdir(os.path.join(base_path, d)) and
                 os.path.exists(os.path.join(base_path, d, script_folder, "activate"))]

        current_selection = self.venv_dropdown.currentText()
        self.venv_dropdown.clear()

        if not venvs:
            self.venv_dropdown.addItem("No environments found")
            for widget in env_dependent_widgets: widget.setEnabled(False)
        else:
            self.venv_dropdown.addItems(sorted(venvs))
            if current_selection in venvs: self.venv_dropdown.setCurrentText(current_selection)
            for widget in env_dependent_widgets: widget.setEnabled(True)
        
    def _update_file_observer(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            self.observer = Observer()
            self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
            self.observer.start()

    def _update_status(self, message, msg_type):
        self.status_label.setText(message)
        c = self.current_theme
        color_map = {"success": c['success'], "error": c['error'], "info": c['accent']}
        bg_color = color_map.get(msg_type, "transparent")
        self.status_label.setStyleSheet(f"background-color: {bg_color}; color: white; border-radius: 4px; padding: 4px;")
        if msg_type in ["success", "error", "info"]:
            QTimer.singleShot(5000, lambda: self.status_label.setStyleSheet(f"background: transparent; color: {c['text']};"))

    def _log_message(self, message):
        self.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _set_progress_bar_active(self, is_active):
        self.progress_bar.setVisible(is_active)
        self.running_indicator.setVisible(is_active)
        if is_active: self.progress_bar.setRange(0, 0)
        else: self.progress_bar.setRange(0, 100)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            title_bar_widget = self.container_layout.itemAt(0).widget()
            if title_bar_widget and title_bar_widget.rect().contains(event.pos()):
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def closeEvent(self, event):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        if self.command_thread:
            self.command_thread.stop()
        event.accept()

if __name__ == "__main__":
    sys.excepthook = global_exception_hook
    app = QApplication(sys.argv)
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())