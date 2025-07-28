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
from PyQt6.QtCore import (Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot, QSettings, 
                          QPropertyAnimation, QEasingCurve)
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction

# --- Global Exception Handler ---
def global_exception_hook(exctype, value, tb):
    """Catches unhandled exceptions, logs them, and shows a critical error dialog."""
    error_message = f"An unexpected error occurred:\n\n{value}"
    traceback_details = "".join(traceback.format_tb(tb))
    try:
        with open("error_log.txt", "a") as f:
            f.write(f"--- {time.ctime()} ---\n")
            f.write(f"{error_message}\n")
            f.write(f"{traceback_details}\n\n")
    except Exception as e:
        # If logging fails, print to console as a last resort
        print(f"CRITICAL: Error logging failed: {e}")

    # Display a user-friendly error dialog
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Unhandled Application Error")
    error_box.setText("A critical error occurred and the application must close.")
    error_box.setInformativeText("Details have been saved to error_log.txt.")
    error_box.setDetailedText(traceback_details)
    error_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_box.exec()

    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

# --- Worker Thread for Running Commands ---
class CommandThread(QThread):
    """
    Executes shell commands in a separate thread to avoid blocking the UI.
    Emits signals for output, completion, and process start.
    """
    finished = pyqtSignal(bool, str, str)  # success, message, command_output
    process_started = pyqtSignal()
    output_received = pyqtSignal(str)

    def __init__(self, base_path, selected_env=None, command_type="jupyter", **kwargs):
        super().__init__()
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type
        self.kwargs = kwargs
        self.process = None
        self._is_running = True

    def run(self):
        """Main logic for constructing and executing the command."""
        command_output = ""
        try:
            # Determine the correct command list and execution method
            full_cmd, shell = self._build_command()
            
            if not full_cmd:
                # This case is for commands that open a new terminal (e.g., 'activate')
                # The process is launched externally, so we just report success.
                self.finished.emit(True, "Process launched in new terminal.", "")
                return

            # Start the subprocess
            self.process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Capture stderr separately
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if shell else 0,
                shell=shell
            )
            self.process_started.emit()

            # Read stdout line by line
            for line in iter(self.process.stdout.readline, ''):
                if not self._is_running:
                    break
                stripped_line = line.strip()
                self.output_received.emit(stripped_line)
                command_output += stripped_line + "\n"
            
            self.process.stdout.close()
            
            # Capture any remaining error output
            stderr_output = self.process.stderr.read().strip()
            if stderr_output:
                self.output_received.emit(f"ERROR: {stderr_output}")

            return_code = self.process.wait()

            if not self._is_running:
                 self.finished.emit(False, f"Command '{self.command_type}' was terminated.", "")
            elif return_code == 0:
                self.finished.emit(True, f"Command '{self.command_type}' completed successfully.", command_output)
            else:
                error_msg = f"Command '{self.command_type}' failed with exit code {return_code}."
                if stderr_output:
                     error_msg += f"\nDetails: {stderr_output}"
                self.finished.emit(False, error_msg, stderr_output)

        except FileNotFoundError as e:
            self.finished.emit(False, f"Error: A required file was not found. {str(e)}", "")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred: {str(e)}", "")
        finally:
            self.process = None
    
    def _build_command(self):
        """Constructs the final command string or list."""
        cmd_list = []
        shell = False
        
        # Define command prefix for Windows
        if sys.platform == "win32":
            # Using cmd.exe /c "cd ... && command" ensures the command runs in the correct directory.
            full_cmd_prefix = f'cmd.exe /c "cd /d "{self.base_path}" && '
        else:
            # Placeholder for future Unix-like OS support
            self.finished.emit(False, "Unix-like OS execution is not yet implemented.", "")
            return None, False

        # --- Command routing ---
        if self.command_type == "create_venv":
            new_env_name = self.kwargs.get("new_env_name")
            cmd_list = ['python', '-m', 'venv', new_env_name]
            full_cmd = full_cmd_prefix + ' '.join(cmd_list) + '"'
            shell = True
        
        elif self.command_type in ["get_env_details", "freeze", "pip_list"]:
            cmd_map = {
                "get_env_details": ['python', '--version'],
                "freeze": ['pip', 'freeze'],
                "pip_list": ['pip', 'list', '--format=json']
            }
            cmd_list = cmd_map[self.command_type]
            full_cmd = self._get_activated_command(cmd_list)
            shell = True
            
        else:
            # These commands require an environment to be selected
            if not self.selected_env:
                 raise ValueError("An environment must be selected for this action.")
            
            cmd_list = None
            if self.command_type == "launch":
                tool = self.kwargs.get("tool", "jupyter notebook")
                cmd_list = tool.split()
            elif self.command_type == "install_requirements":
                req_path = self.kwargs.get("requirements_path")
                if req_path.endswith(".json"):
                     # Special handling for our packages.json
                     with open(req_path, 'r') as f:
                         data = json.load(f)
                     packages = " ".join(data.get("packages", []))
                     if not packages: raise ValueError("JSON file contains no packages to install.")
                     cmd_list = ['pip', 'install'] + packages.split()
                else:
                     # Standard requirements.txt
                     cmd_list = ['pip', 'install', '-r', f'"{req_path}"']
            elif self.command_type == "activate":
                cmd_list = [] # No command, just activate in new terminal
            
            if cmd_list is None:
                self.finished.emit(False, f"Unsupported command type: {self.command_type}", "")
                return None, False

            # This command needs to open a new, interactive terminal
            full_cmd = self._get_activated_command(cmd_list, new_console=True)
            shell = True
            return full_cmd, shell # Return immediately as Popen is handled differently

        return full_cmd, shell

    def _get_activated_command(self, cmd_list, new_console=False):
        """
        Creates the full command string for running within an activated virtual environment.
        """
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        activate_script_path = os.path.join(self.base_path, self.selected_env, script_folder, "activate.bat")
        
        if not os.path.exists(activate_script_path):
            raise FileNotFoundError(f"Activation script not found: {activate_script_path}")
        
        command_str = ' '.join(cmd_list)
        base_path_norm = os.path.normpath(self.base_path)
        activate_script_norm = os.path.normpath(activate_script_path)

        if new_console:
            # Use a temporary batch file to activate the environment and then run the command in a new console.
            # This is the most reliable way to provide an interactive, activated shell.
            temp_bat_file = None
            try:
                temp_bat_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.bat', newline='\r\n')
                temp_bat_path = temp_bat_file.name
                
                # Write commands to the temporary batch file
                temp_bat_file.write('@echo off\n')
                temp_bat_file.write(f'title PyEnv Launcher - {self.selected_env}\n') # Set a useful title
                temp_bat_file.write(f'cd /d "{base_path_norm}"\n')
                temp_bat_file.write(f'call "{activate_script_norm}"\n')
                
                if command_str:
                    temp_bat_file.write(f'@echo Running: {command_str}\n')
                    temp_bat_file.write(f'{command_str}\n')
                else: # 'activate' command just opens the shell
                     temp_bat_file.write('echo.\n')
                     temp_bat_file.write('echo Environment is now active in this terminal.\n')
                     
                temp_bat_file.close() # Close the file to ensure it's written

                # Launch the batch file in a new terminal window that stays open (/k)
                subprocess.Popen(f'start "PyEnv Launcher" cmd.exe /k "{temp_bat_path}"', shell=True)
                
                # Schedule the temp file for deletion
                QTimer.singleShot(5000, lambda: os.remove(temp_bat_path))
                
                return None # Signal that the process is external
            
            except Exception as e:
                raise IOError(f"Failed to create temporary script: {e}")

        else:
            # For non-interactive commands, chain everything with '&&'
            commands_to_run = f'call "{activate_script_norm}" && {command_str}'
            return f'cmd.exe /c "{commands_to_run}"'

    def stop_process(self):
        """Stops the running command thread and terminates its subprocess."""
        self._is_running = False
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate() # Try to terminate gracefully
                self.process.wait(timeout=2) # Wait a bit
            except Exception as e:
                self.output_received.emit(f"Forcing process to kill: {e}")
                self.process.kill() # Force kill if terminate fails


# --- File System Watcher ---
class FileChangeHandler(FileSystemEventHandler):
    """Fires a callback when the watched directory content changes."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        # Trigger on creation, deletion, or movement of files/folders
        if event.event_type in ['created', 'deleted', 'moved']:
            self.callback()


# --- Dialogs ---
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

        terms_label = QLabel("<b>Terms and Conditions (MIT License):</b>")
        terms_text = QTextEdit()
        terms_text.setReadOnly(True)
        terms_text.setText(
             "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal "
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all "
            "copies or substantial portions of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
            "SOFTWARE."
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

# --- Main Application Window ---
class JupyterLauncher(QWidget):
    # Theme definitions
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
        
        # --- Window Setup ---
        self.setWindowTitle("PyEnv Launcher")
        self.setObjectName("JupyterLauncher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 800)

        # --- Instance Variables ---
        self.observer = None
        self.old_pos = None
        self.command_thread = None

        # --- UI Initialization ---
        self._setup_main_layout()
        self._setup_ui_components()
        self._apply_stylesheet()
        self._connect_signals()

        # --- Final Setup ---
        self._load_app_settings()
        self._update_file_observer()
        self.discover_virtual_environments()
        self._setup_animations()
    
    def _setup_animations(self):
        """Initializes the fade-in and fade-out animations for the window."""
        # --- Fade-In Animation (Existing code) ---
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade_in_animation.setDuration(400)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # --- Fade-Out Animation (New code) ---
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade_out_animation.setDuration(300) # A slightly faster close feels more responsive
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # IMPORTANT: When the fade-out is finished, call the real close method
        self.fade_out_animation.finished.connect(self.close)
        
    def show_with_fade(self):
        """Shows the window with a smooth fade-in effect."""
        # Start with the window being completely transparent
        self.setWindowOpacity(0.0)
        
        # Start the animation. The animation will make it fade to 1.0 (opaque)
        self.fade_in_animation.start()
        
        # Show the window. It will be invisible at first and then fade in.
        self.show()

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
        self.install_reqs_btn.setToolTip("Install packages from a requirements.txt or packages.json file.")
        
        self.export_json_btn = QPushButton("Export to packages.json")
        self.export_json_btn.setToolTip("Save primary packages to a packages.json file.")
        
        self.freeze_btn = QPushButton("Freeze to requirements.txt")
        self.freeze_btn.setToolTip("Save all installed packages into a requirements.txt file.")
        
        pkg_layout.addWidget(self.install_reqs_btn)
        pkg_layout.addWidget(self.export_json_btn)
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

    # --- Signal Connections and Styling ---
    def _connect_signals(self):
        # Title Bar
        self.about_btn.clicked.connect(self._open_about_dialog)
        self.settings_btn.clicked.connect(self._open_settings)
        title_bar = self.container_layout.itemAt(0).widget()
        control_buttons = title_bar.findChildren(QPushButton)
        control_buttons[-1].clicked.connect(self.close)
        control_buttons[-2].clicked.connect(self.showMinimized)
        
        # Path Management
        self.path_input.textChanged.connect(self._on_path_changed)
        self.recent_paths_btn.clicked.connect(self._show_recent_paths_menu)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        
        # Venv Creation & Management
        self.create_venv_btn.clicked.connect(self._create_environment)
        self.venv_dropdown.currentTextChanged.connect(self._on_venv_selection_changed)
        self.delete_venv_btn.clicked.connect(self._delete_environment)
        
        # Package & Launching
        self.install_reqs_btn.clicked.connect(self._install_requirements)
        self.freeze_btn.clicked.connect(self._freeze_requirements)
        self.export_json_btn.clicked.connect(self._export_to_json)
        self.activate_btn.clicked.connect(self._activate_environment)
        self.launch_jupyter_btn.clicked.connect(self._launch_jupyter)
        
        # File List & Logs
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        self.clear_log_btn.clicked.connect(self.log_output.clear)

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
    
    # --- Command Execution ---
    def _run_command(self, command_type, on_finish=None, **kwargs):
        if self.command_thread and self.command_thread.isRunning():
            self._update_status("A command is already running.", "error")
            return

        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()
        if not os.path.isdir(base_path):
             self._update_status("Invalid project directory selected.", "error")
             return
        
        # Check if environment is valid before proceeding
        if command_type not in ["create_venv"] and ("found" in selected_env or not selected_env):
            self._update_status("A valid environment must be selected.", "error")
            return
        
        # Create and start the thread
        self.command_thread = CommandThread(base_path, selected_env, command_type, **kwargs)
        self.command_thread.output_received.connect(self._log_message)
        self.command_thread.process_started.connect(lambda: self._set_progress_bar_active(True))
        
        # Connect the finished signal to handle results
        self.command_thread.finished.connect(
            lambda s, m, o: self._on_command_finished(s, m, o, on_finish)
        )
        
        self.command_thread.start()
        self._log_message(f"Starting command: {command_type}...")

    def _on_command_finished(self, success, message, command_output, on_finish_callback):
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")
        self._log_message(f"Finished: {message}")
        if success and on_finish_callback:
            # Pass the raw command output to the callback
            on_finish_callback(command_output)

    # --- UI Slots and Actions ---
    def _open_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings.sync()
            self.current_theme = self.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else self.LIGHT_THEME
            self._apply_stylesheet()
            self._update_status("Settings saved. Restart may be required for some changes.", "info")

    def _load_app_settings(self):
        self.current_theme = self.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else self.LIGHT_THEME
        default_path = self.settings.value("default_path", os.path.expanduser("~"))
        if not self.path_input.text():
            self.path_input.setText(default_path)
        self._add_to_recent_paths(self.path_input.text())
            
    def _on_path_changed(self):
        """Debounces path changes to avoid excessive updates while typing."""
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True)
            self._path_change_timer.timeout.connect(self._update_path_resources)
        self._path_change_timer.start(500)

    def _update_path_resources(self):
        """Updates UI elements that depend on the selected project path."""
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
            self._update_status("Provide a valid environment name with no spaces.", "error")
            return
        if os.path.exists(os.path.join(base_path, new_env_name)):
            self._update_status(f"Directory '{new_env_name}' already exists.", "error")
            return
        self._run_command("create_venv", new_env_name=new_env_name, on_finish=lambda _: self.discover_virtual_environments())
        self.new_venv_name_input.clear()

    def _delete_environment(self):
        env_name = self.venv_dropdown.currentText()
        if not env_name or "found" in env_name: return

        reply = QMessageBox.question(self, 'Confirm Deletion', 
            f"Are you sure you want to permanently delete the environment '{env_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            env_path = os.path.join(self.path_input.text().strip(), env_name)
            self._log_message(f"Attempting to delete {env_path}...")
            try:
                shutil.rmtree(env_path)
                QTimer.singleShot(250, self.discover_virtual_environments) # Give OS time to update
                self._update_status(f"Environment '{env_name}' deleted.", "success")
                self._log_message(f"Successfully deleted environment '{env_name}'.")
            except Exception as e:
                self._update_status(f"Error deleting environment: {e}", "error")
                self._log_message(f"Failed to delete {env_path}: {e}")

    def _on_venv_selection_changed(self, env_name):
        if not env_name or "found" in env_name:
            self.env_details_label.setText("Select an environment to see details.")
            return
        
        self.env_details_label.setText("Fetching details...")
        self._run_command("get_env_details", on_finish=self._update_env_details)
        
    def _update_env_details(self, python_version_output):
        env_name = self.venv_dropdown.currentText()
        if not env_name or "found" in env_name: return

        env_path = os.path.join(self.path_input.text().strip(), env_name)
        py_version = python_version_output.strip() if python_version_output else "Unknown"
        
        try:
            creation_date = time.ctime(os.path.getctime(env_path))
            details = f"Version: {py_version} | Created: {creation_date}"
            self.env_details_label.setText(details)
            self.env_details_label.setToolTip(f"Path: {env_path}\n{details}")
        except FileNotFoundError:
             self.env_details_label.setText("Environment details not available.")


    def _install_requirements(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Requirements File", self.path_input.text(), "Package Files (*.txt *.json)"
        )
        if path:
            self._run_command("install_requirements", requirements_path=path)

    def _freeze_requirements(self):
        """Runs 'pip freeze' and saves the output to requirements.txt."""
        self._run_command("freeze", on_finish=self._save_freeze_output)

    def _save_freeze_output(self, freeze_output):
        """Callback to save the raw output from the freeze command."""
        if not freeze_output:
            self._update_status("Freeze command produced no output.", "error")
            return
        
        try:
            req_path = os.path.join(self.path_input.text().strip(), "requirements.txt")
            with open(req_path, "w") as f:
                f.write(freeze_output.strip())
            self._update_status("requirements.txt generated successfully.", "success")
            self.discover_virtual_environments() # Refresh file list
        except Exception as e:
            self._update_status(f"Failed to write requirements.txt: {e}", "error")

    def _export_to_json(self):
        """Exports top-level packages to packages.json."""
        self._run_command("pip_list", on_finish=self._save_json_output)
        
    def _save_json_output(self, pip_list_output):
        """Parses 'pip list --format=json' to create a simple package file."""
        if not pip_list_output:
            self._update_status("Could not get package list.", "error")
            return

        try:
            # The output may have multiple JSON objects or other text, find the first valid one
            json_start = pip_list_output.find('[')
            json_end = pip_list_output.rfind(']') + 1
            if json_start == -1:
                 raise json.JSONDecodeError("No JSON array found in pip output.", pip_list_output, 0)
                 
            packages_data = json.loads(pip_list_output[json_start:json_end])
            
            # Filter out editable packages (like -e .) and pip/setuptools themselves
            editable_filter = ['pip', 'setuptools', 'wheel']
            top_level_packages = [
                pkg['name'] for pkg in packages_data 
                if pkg['name'] not in editable_filter
            ]

            json_content = {
                "comment": "Managed by PyEnv Launcher. Contains top-level packages for this project.",
                "packages": sorted(top_level_packages)
            }
            
            json_path = os.path.join(self.path_input.text().strip(), "packages.json")
            with open(json_path, "w") as f:
                json.dump(json_content, f, indent=4)
                
            self._update_status("packages.json exported successfully.", "success")
            self.discover_virtual_environments()
        except json.JSONDecodeError as e:
             self._update_status(f"Failed to parse package list: {e}", "error")
             self._log_message(f"ERROR: Could not decode JSON from pip output: {pip_list_output}")
        except Exception as e:
            self._update_status(f"Failed to write packages.json: {e}", "error")

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

    # --- Utility and Helper Methods ---
    def discover_virtual_environments(self):
        """Scans the project directory for venvs and updates the UI."""
        base_path = self.path_input.text().strip()
        self.file_list.clear()

        # Define all widgets that depend on a valid path or environment
        all_widgets = [self.open_btn, self.new_venv_name_input, self.create_venv_btn, self.venv_dropdown,
                       self.delete_venv_btn, self.install_reqs_btn, self.freeze_btn, self.export_json_btn,
                       self.activate_btn, self.launch_jupyter_btn]
        env_dependent_widgets = [self.delete_venv_btn, self.install_reqs_btn, self.freeze_btn,
                                 self.export_json_btn, self.activate_btn, self.launch_jupyter_btn]

        if not os.path.isdir(base_path):
            for widget in all_widgets: widget.setEnabled(False)
            return

        # Enable base widgets, env-dependent ones will be handled later
        for widget in [self.open_btn, self.new_venv_name_input, self.create_venv_btn, self.venv_dropdown]:
            widget.setEnabled(True)
        
        # Populate file list
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

        # Discover virtual environments
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        venvs = [d for d in dir_contents if os.path.isdir(os.path.join(base_path, d)) and
                 os.path.exists(os.path.join(base_path, d, script_folder, "activate"))]

        current_selection = self.venv_dropdown.currentText()
        self.venv_dropdown.clear()

        if not venvs:
            self.venv_dropdown.addItem("No environments found")
            self.venv_dropdown.setEnabled(False)
            for widget in env_dependent_widgets: widget.setEnabled(False)
        else:
            self.venv_dropdown.setEnabled(True)
            self.venv_dropdown.addItems(sorted(venvs))
            if current_selection in venvs: self.venv_dropdown.setCurrentText(current_selection)
            for widget in env_dependent_widgets: widget.setEnabled(True)
        
    def _update_file_observer(self):
        """Restarts the file system observer on the current path."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            self.observer = Observer()
            # Watch for changes and call discover_virtual_environments
            self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
            self.observer.start()

    def _update_status(self, message, msg_type):
        """Updates the status bar with a colored message that fades."""
        self.status_label.setText(message)
        c = self.current_theme
        color_map = {"success": c['success'], "error": c['error'], "info": c['accent']}
        # Use a more subtle background for info messages
        bg_color = color_map.get(msg_type, "transparent") if msg_type != "info" else c['border']
        
        self.status_label.setStyleSheet(f"background-color: {bg_color}; color: white; border-radius: 4px; padding: 4px;")
        
        # Reset the style after 5 seconds
        if msg_type in ["success", "error", "info"]:
            QTimer.singleShot(5000, lambda: self.status_label.setStyleSheet(f"background: transparent; color: {c['text']};"))

    def _log_message(self, message):
        """Appends a timestamped message to the log view."""
        self.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def _set_progress_bar_active(self, is_active):
        """Controls the visibility and state of the progress bar and indicator."""
        self.progress_bar.setVisible(is_active)
        self.running_indicator.setVisible(is_active)
        if is_active:
            self.progress_bar.setRange(0, 0) # Indeterminate mode
        else:
            self.progress_bar.setRange(0, 100)

    # --- Window Movement and Closing ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            title_bar_widget = self.container_layout.itemAt(0).widget()
            if title_bar_widget and title_bar_widget.geometry().contains(event.pos()):
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def closeEvent(self, event):
        """
        Overrides the default close event to perform a fade-out animation.
        """
        # Check if we are already in the process of closing to prevent a loop
        if hasattr(self, '_is_closing') and self._is_closing:
            # If we are, it means the animation finished and called self.close() again.
            # We let the event proceed to close the application for real.
            super().closeEvent(event)
            return

        # --- 1. Perform all necessary cleanup FIRST ---
        if self.observer:
            self.observer.stop()
            self.observer.join()
        if self.command_thread and self.command_thread.isRunning():
            self.command_thread.stop_process()
            self.command_thread.wait()

        # --- 2. Start the fade-out process ---
        self._is_closing = True # Set a flag to indicate we've started closing
        event.ignore() # IMPORTANT: Ignore the original close event
        self.fade_out_animation.start() # Start our fade-out animation

# --- Application Entry Point ---
if __name__ == "__main__":
    # Set the global exception hook to catch all unhandled errors
    sys.excepthook = global_exception_hook
    
    app = QApplication(sys.argv)
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))
    
    window = JupyterLauncher()
    window.show_with_fade()
    
    sys.exit(app.exec())