import sys
import os
import subprocess
import time
import shutil
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip,
    QMessageBox, QStyle, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QGuiApplication

# --- Global Exception Handler ---
# This function serves as a global safety net for the entire application.
# If any part of the code raises an exception that is not caught locally (an "unhandled" exception),
# this function will be automatically called by the Python interpreter.
# Its purpose is to prevent the application from crashing silently. Instead, it logs
# the error details to a file for later debugging and displays a user-friendly
# error message, so the user knows something went wrong.
def global_exception_hook(exctype, value, tb):
    """
    Handles any uncaught exception by logging the traceback to a file
    and showing a critical error message to the user.
    
    Args:
        exctype: The type of the exception (e.g., ValueError, TypeError).
        value: The exception instance (the error message itself).
        tb: A traceback object containing the call stack at the point of the error.
    """
    # Format the error message and traceback into readable strings.
    error_message = f"An unexpected error occurred:\n\n{value}"
    traceback_details = "".join(traceback.format_tb(tb))

    # Attempt to log the error to a file named 'error_log.txt'.
    # This provides a persistent record of errors for debugging.
    try:
        with open("error_log.txt", "a") as f:
            f.write(f"--- {time.ctime()} ---\n")
            f.write(f"{error_message}\n")
            f.write(f"{traceback_details}\n\n")
    except Exception as e:
        # If logging itself fails (e.g., due to file permissions),
        # print the error to the console. We still want to show the original error.
        print(f"Error logging failed: {e}")

    # Create and display a message box to inform the user about the error.
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Unhandled Application Error")
    error_box.setText(error_message)
    # The detailed traceback is hidden by default but can be viewed by the user.
    error_box.setDetailedText(traceback_details)
    error_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_box.exec()

    # Call the default Python exception hook to ensure standard behavior (like printing to stderr).
    sys.__excepthook__(exctype, value, tb)
    # Exit the application since it's in an unstable state.
    sys.exit(1)


# --- Command Execution Thread ---
# This QThread subclass is designed to run command-line operations (like starting Jupyter)
# in the background, separate from the main GUI thread. This is crucial for keeping
# the application responsive. If these commands were run on the main thread, the UI
# would freeze until the command completes.
class CommandThread(QThread):
    # pyqtSignal is used to safely communicate from this worker thread back to the main GUI thread.
    # 'finished' signal: Emits a boolean (success/fail) and a string (message) when the task is done.
    finished = pyqtSignal(bool, str)
    # 'jupyter_started': Emits a signal specifically when the Jupyter launch command has been issued.
    jupyter_started = pyqtSignal()

    def __init__(self, base_path, selected_env=None, command_type="jupyter", **kwargs):
        super().__init__()
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type
        # Store any additional arguments, like the path to a requirements file.
        self.kwargs = kwargs

    # The 'run' method contains the code that will be executed in the separate thread.
    def run(self):
        try:
            cmd = None
            full_cmd = f'cd /d "{self.base_path}"'
            
            # --- Command construction logic ---
            if self.command_type == "create_venv":
                new_env_name = self.kwargs.get("new_env_name")
                if not new_env_name:
                    raise ValueError("New environment name not provided.")
                # This command runs directly without activating another environment.
                cmd = f'python -m venv {new_env_name}'
                full_cmd += f' && {cmd}'
            else:
                # For all other commands, we need to activate an existing environment.
                if not self.selected_env:
                     raise ValueError("An environment must be selected for this operation.")
                script_folder = "Scripts" if sys.platform == "win32" else "bin"
                activate_script = os.path.join(self.base_path, self.selected_env, script_folder, "activate")
                if sys.platform == "win32":
                    activate_script += ".bat"
                if not os.path.exists(activate_script):
                    raise FileNotFoundError(f"Activation script not found at: {activate_script}")
                
                full_cmd += f' && "{activate_script}"'

                if self.command_type == "jupyter":
                    cmd = 'jupyter notebook'
                elif self.command_type == "install_jupyter":
                    cmd = 'pip install jupyter'
                elif self.command_type == "install_requirements":
                    requirements_path = self.kwargs.get("requirements_path")
                    if not requirements_path:
                        raise ValueError("Requirements file path not provided.")
                    cmd = f'pip install -r "{requirements_path}"'
                
                if cmd:
                    full_cmd += f' && {cmd}'

            # Platform-specific execution logic.
            if sys.platform == "win32":
                # Use `subprocess.Popen` to launch a new, independent command prompt window.
                # `start cmd /k`: Starts a new cmd window and keeps it open after the command finishes.
                # `creationflags=subprocess.CREATE_NEW_CONSOLE`: Ensures it runs in a completely new console.
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                self.finished.emit(False, "Unix-like OS execution is not yet implemented.")
                return

            time.sleep(2) # A short delay to allow the new terminal to initialize.

            # Emit the appropriate 'finished' signal based on the command that was run.
            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook successfully launched in a new terminal!")
                self.jupyter_started.emit()
            elif self.command_type == "install_jupyter":
                self.finished.emit(True, "Jupyter installation process has been started.")
            elif self.command_type == "install_requirements":
                self.finished.emit(True, "Library installation process has been started.")
            elif self.command_type == "create_venv":
                env_name = self.kwargs.get("new_env_name")
                self.finished.emit(True, f"Virtual environment '{env_name}' created successfully!")
            else: # 'activate'
                self.finished.emit(True, "Virtual environment activated in a new terminal.")

        except FileNotFoundError as e:
            self.finished.emit(False, f"Error: A required file was not found. {str(e)}")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred in the command thread: {str(e)}")


# --- File System Change Handler ---
# This class, derived from watchdog's FileSystemEventHandler, is responsible for
# reacting to changes in the file system (creations, deletions, moves).
# When such an event occurs in the monitored directory, it calls a callback function.
class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        # The callback is a function from the main window that should be run
        # when a file system change is detected (e.g., to refresh the file list).
        self.callback = callback

    # This method is called by the watchdog observer for any file system event.
    def on_any_event(self, event):
        try:
            # We only care about events that change the directory structure.
            if event.event_type in ['created', 'deleted', 'moved']:
                # Execute the callback function (e.g., self.discover_virtual_environments).
                self.callback()
        except Exception as e:
            # If the callback function itself raises an error, print it for debugging.
            # It's difficult to show this error in the UI, so console is the best option.
            print(f"Error in FileChangeHandler callback: {e}")


# --- Main Application Window ---
# This is the main class for the application's user interface.
# It inherits from QWidget and orchestrates all UI elements and their interactions.
class JupyterLauncher(QWidget):
    # Define class-level constants for colors and fonts. This makes styling
    # consistent and easy to modify.
    COLOR_BACKGROUND = "#0d1117"
    COLOR_PRIMARY = "#000000"
    COLOR_BORDER = "#30363d"
    COLOR_BORDER_WINDOW = "#87CEEB"
    COLOR_TEXT = "#c9d1d9"
    COLOR_TEXT_HEADER = "#f0f6fc"
    COLOR_TEXT_SECONDARY = "#8b949e"
    COLOR_ACCENT = "#2f81f7"
    COLOR_SUCCESS = "#238636"
    COLOR_ERROR = "#da3633"
    FONT_MAIN = "Segoe UI"

    def __init__(self):
        super().__init__()
        # Use a try-except block to catch any critical errors during initialization.
        # If the UI can't be set up, the app is unusable.
        try:
            # --- Window Setup ---
            self.setWindowTitle("PyEnv Launcher")
            self.setObjectName("JupyterLauncher") # Used for top-level styling.
            # These flags create a borderless, transparent window, allowing for a custom-shaped UI.
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.resize(550, 720) # Increased height for the new section

            # Initialize variables for the file system observer and window dragging.
            self.observer = None
            self.old_pos = None

            # --- UI Construction ---
            # Call helper methods to build the UI, apply styles, and connect signals.
            self._setup_main_layout()
            self._setup_ui_components()
            self._apply_stylesheet()
            self._connect_signals()

            # --- Initial State Configuration ---
            # Set the initial state of the application after the UI is built.
            self._set_default_path()
            self._update_file_observer()
            self.discover_virtual_environments()

        except Exception as e:
            # If a critical error occurs during __init__, show a message and re-raise
            # the exception so the global hook can log it before exiting.
            QMessageBox.critical(
                None,
                "Application Startup Error",
                f"A critical error occurred during initialization and the application cannot start.\n\n"
                f"Error: {e}\n\n"
                f"Please check the error_log.txt for more details."
            )
            raise

    # This method sets up the main container widget that gives the window its
    # rounded corners and border. The actual content will be placed inside this container.
    def _setup_main_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the transparent window.
        self.main_layout.setSpacing(0)
        self.container = QWidget(self)
        self.container.setObjectName("container") # This ID is used in CSS for styling.
        self.main_layout.addWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2) # Small margin for the border effect.
        self.container_layout.setSpacing(0)

    # This method orchestrates the creation of all UI widgets by calling other helper methods.
    def _setup_ui_components(self):
        # Create the custom title bar for window controls.
        title_bar = self._create_title_bar()
        self.container_layout.addWidget(title_bar)
        
        # A scroll area is used to ensure the UI is usable even on small screens.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.container_layout.addWidget(scroll_area)
        
        # A content widget is placed inside the scroll area to hold all other layouts.
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(15) # Increased spacing for sections
        
        # Add all the content sections to the main layout.
        content_layout.addLayout(self._create_path_section())
        # --- NEW: Section for creating environments ---
        content_layout.addLayout(self._create_new_venv_section())
        content_layout.addWidget(self._create_separator())
        content_layout.addLayout(self._create_manage_venv_section())
        content_layout.addLayout(self._create_status_section())
        content_layout.addLayout(self._create_files_section())
        content_layout.addStretch() # Pushes the footer to the bottom.
        content_layout.addLayout(self._create_footer_section())

    # Creates a horizontal line separator widget.
    def _create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {self.COLOR_BORDER};")
        return line

    # Creates the custom title bar with a title and window control buttons.
    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(15, 0, 5, 0)
        title = QLabel("📘  PyEnv Launcher")
        title.setObjectName("titleLabel")
        # This label will be shown as a green dot when Jupyter is running.
        self.running_indicator = QLabel("●")
        self.running_indicator.setObjectName("runningIndicator")
        self.running_indicator.setVisible(False)
        minimize_btn = QPushButton("—")
        close_btn = QPushButton("✕")
        for btn in [minimize_btn, close_btn]:
            btn.setObjectName("controlBtn")
            btn.setFixedSize(30, 30)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.running_indicator)
        layout.addWidget(minimize_btn)
        layout.addWidget(close_btn)
        return title_bar

    # Creates the UI elements for selecting the project directory.
    def _create_path_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Project Directory"))
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter or browse to your project path")
        layout.addWidget(self.path_input)
        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Select Directory")
        self.open_btn = QPushButton("Open Path")
        btn_layout.addWidget(self.browse_btn)
        btn_layout.addWidget(self.open_btn)
        layout.addLayout(btn_layout)
        return layout

    # --- NEW: Creates the section for creating a new venv ---
    def _create_new_venv_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Create New Environment"))
        creation_layout = QHBoxLayout()
        self.new_venv_name_input = QLineEdit()
        self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.create_venv_btn = QPushButton("Create")
        self.create_venv_btn.setObjectName("createBtn")
        creation_layout.addWidget(self.new_venv_name_input)
        creation_layout.addWidget(self.create_venv_btn)
        layout.addLayout(creation_layout)
        return layout

    # Creates the UI elements for managing the virtual environment. (Renamed from _create_venv_section)
    def _create_manage_venv_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Manage Existing Environment"))
        self.venv_dropdown = QComboBox()
        layout.addWidget(self.venv_dropdown)
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        self.install_reqs_btn = QPushButton("Install from File (e.g., requirements.txt)")
        actions_layout.addWidget(self.install_reqs_btn)
        btn_row_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate")
        self.install_btn = QPushButton("Install Jupyter")
        self.launch_btn = QPushButton("Launch Jupyter")
        self.launch_btn.setObjectName("launchBtn")
        btn_row_layout.addWidget(self.activate_btn)
        btn_row_layout.addWidget(self.install_btn)
        btn_row_layout.addWidget(self.launch_btn)
        actions_layout.addLayout(btn_row_layout)
        layout.addLayout(actions_layout)
        return layout

    # Creates the status label and progress bar.
    def _create_status_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.status_label = QLabel("Welcome to PyEnv Launcher!")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False) # Initially hidden.
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        return layout

    # Creates the list widget to display directory contents.
    def _create_files_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Directory Contents"))
        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.file_list)
        return layout

    # Creates the footer with a copyright notice and a window resize handle.
    def _create_footer_section(self):
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 5, 0, 0)
        copyright_label = QLabel("Copyright © 2025 Chakhdi.local® – All Rights Reserved")
        copyright_label.setObjectName("copyrightLabel")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sizegrip = QSizeGrip(self.container)
        sizegrip.setFixedSize(16, 16)
        footer_layout.addStretch()
        footer_layout.addWidget(copyright_label)
        footer_layout.addStretch()
        footer_layout.addWidget(sizegrip)
        return footer_layout

    # Connects UI element signals to their corresponding handler methods (slots).
    def _connect_signals(self):
        self.path_input.textChanged.connect(self._on_path_changed)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        # --- NEW: Connect create venv button ---
        self.create_venv_btn.clicked.connect(self._create_environment)
        self.activate_btn.clicked.connect(self._activate_environment)
        self.install_btn.clicked.connect(self._install_jupyter)
        self.install_reqs_btn.clicked.connect(self._install_requirements)
        self.launch_btn.clicked.connect(self._launch_jupyter)
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        
        # Connect the custom title bar buttons.
        title_bar = self.container_layout.itemAt(0).widget()
        control_buttons = title_bar.findChildren(QPushButton, "controlBtn")
        if len(control_buttons) >= 2:
            control_buttons[1].clicked.connect(self.close) # Close button
            control_buttons[0].clicked.connect(self.showMinimized) # Minimize button

    # Applies all the CSS styling to the application widgets.
    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            #JupyterLauncher {{ background-color: transparent; }}
            #container {{ background-color: {self.COLOR_PRIMARY}; border: 2px solid {self.COLOR_BORDER_WINDOW}; border-radius: 15px; }}
            QWidget {{ font-family: "{self.FONT_MAIN}"; color: {self.COLOR_TEXT}; font-size: 9pt; }}
            #titleBar {{ background-color: {self.COLOR_BACKGROUND}; border-top-left-radius: 13px; border-top-right-radius: 13px; }}
            #titleLabel {{ color: {self.COLOR_TEXT_HEADER}; font-weight: bold; font-size: 11pt; }}
            #controlBtn {{ background: transparent; border: none; font-size: 12pt; }}
            #controlBtn:hover {{ background: {self.COLOR_BORDER}; border-radius: 4px; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
            QLabel {{ font-weight: bold; background: transparent;}}
            QLineEdit, QComboBox {{ background-color: {self.COLOR_BACKGROUND}; border: 1px solid {self.COLOR_BORDER}; border-radius: 6px; padding: 7px; }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {self.COLOR_ACCENT}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ background-color: {self.COLOR_BACKGROUND}; border: 1px solid {self.COLOR_BORDER}; selection-background-color: {self.COLOR_ACCENT}; color: {self.COLOR_TEXT}; outline: 0px; }}
            QComboBox QAbstractItemView::item {{ padding: 6px; }}
            QPushButton {{ background-color: {self.COLOR_BORDER}; border: 1px solid {self.COLOR_BORDER}; border-radius: 6px; padding: 8px; font-weight: bold; }}
            QPushButton:hover {{ border-color: #8b949e; background-color: {self.COLOR_BORDER}; }}
            QPushButton:pressed {{ background-color: #21262d; }}
            #launchBtn {{ background-color: {self.COLOR_SUCCESS}; border-color: #318a44; }}
            #launchBtn:hover {{ background-color: #318a44; }}
            #createBtn {{ background-color: {self.COLOR_ACCENT}; border-color: #3e8bf7; }} /* Style for create button */
            #createBtn:hover {{ background-color: #3e8bf7; }}
            #statusLabel {{ background-color: transparent; border-radius: 6px; padding: 8px; font-weight: normal; min-height: 18px; }}
            #runningIndicator {{ color: {self.COLOR_SUCCESS}; font-size: 16pt; font-weight: bold; padding-bottom: 4px; }}
            #copyrightLabel {{ font-size: 8pt; font-weight: normal; color: {self.COLOR_TEXT_SECONDARY}; }}
            QProgressBar {{ border-radius: 4px; background-color: {self.COLOR_BORDER}; height: 4px; }}
            QProgressBar::chunk {{ background-color: {self.COLOR_ACCENT}; border-radius: 4px; }}
            QListWidget {{ background-color: {self.COLOR_BACKGROUND}; border: 1px solid {self.COLOR_BORDER}; border-radius: 6px; padding: 4px; }}
            QListWidget::item {{ padding: 6px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: {self.COLOR_BORDER}; }}
            QListWidget::item:selected {{ background-color: {self.COLOR_ACCENT}; color: white; }}
            QMenu {{ background-color: {self.COLOR_PRIMARY}; border: 1px solid {self.COLOR_BORDER}; }}
            QMenu::item:selected {{ background-color: {self.COLOR_ACCENT}; }}
            QMenu::item {{ padding: 5px 10px 5px 10px; }}
        """)

    # This is a generic method to start a command in the background thread.
    def _run_command(self, command_type, **kwargs):
        try:
            base_path = self.path_input.text().strip()
            selected_env = self.venv_dropdown.currentText()
            # Validate that the path and environment are valid before proceeding.
            if not os.path.isdir(base_path):
                 self._update_status("Invalid directory selected.", "error")
                 return
            if command_type != "create_venv" and ("found" in selected_env or "Invalid" in selected_env):
                self._update_status("Invalid environment selected.", "error")
                return

            # Show user feedback that the process is starting.
            messages = {
                "jupyter": "Launching Jupyter Notebook...",
                "install_jupyter": "Starting Jupyter installation...",
                "activate": "Activating environment...",
                "install_requirements": "Starting library installation...",
                "create_venv": f"Creating new environment '{kwargs.get('new_env_name')}'..."
            }
            self._update_status(messages.get(command_type, "Starting command..."), "info")
            self._set_progress_bar_active(True)

            # Create and start the command thread, passing any extra arguments.
            self.command_thread = CommandThread(base_path, selected_env, command_type, **kwargs)
            self.command_thread.finished.connect(self._on_command_finished)
            if command_type == "jupyter":
                self.command_thread.jupyter_started.connect(self._on_jupyter_started)
            self.command_thread.start()
        except Exception as e:
            self._update_status(f"Failed to start command: {e}", "error")
            self._set_progress_bar_active(False)

    # --- Convenience methods that call _run_command with a specific type ---
    def _launch_jupyter(self): self._run_command("jupyter")
    def _activate_environment(self): self._run_command("activate")
    def _install_jupyter(self): self._run_command("install_jupyter")

    # Method to handle creating a new virtual environment.
    @pyqtSlot()
    def _create_environment(self):
        try:
            base_path = self.path_input.text().strip()
            new_env_name = self.new_venv_name_input.text().strip()

            # --- Validation ---
            if not os.path.isdir(base_path):
                self._update_status("Please select a valid project directory first.", "error")
                return
            if not new_env_name:
                self._update_status("Please provide a name for the new environment.", "error")
                return
            if ' ' in new_env_name:
                self._update_status("Environment name cannot contain spaces.", "error")
                return
            
            potential_path = os.path.join(base_path, new_env_name)
            if os.path.exists(potential_path):
                self._update_status(f"A file or directory named '{new_env_name}' already exists.", "error")
                return
            
            # If validation passes, run the command.
            self._run_command("create_venv", new_env_name=new_env_name)
            self.new_venv_name_input.clear() # Clear the input field
        except Exception as e:
            self._update_status(f"Error preparing to create environment: {e}", "error")

    # Method to handle installing libraries from a file.
    @pyqtSlot()
    def _install_requirements(self):
        try:
            base_path = self.path_input.text().strip()
            if not os.path.isdir(base_path):
                self._update_status("Please select a valid project directory first.", "error")
                return
            
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Requirements File", base_path, "Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                self._run_command("install_requirements", requirements_path=file_path)
        except Exception as e:
            self._update_status(f"Error preparing to install requirements: {e}", "error")


    # This slot is called whenever the text in the path input changes.
    @pyqtSlot()
    def _on_path_changed(self):
        try:
            # A QTimer is used to "debounce" the input. This means the update action
            # will only run after the user has stopped typing for 500ms, preventing
            # excessive updates while the user is still typing a path.
            if not hasattr(self, '_path_change_timer'):
                self._path_change_timer = QTimer()
                self._path_change_timer.setSingleShot(True)
                self.discover_virtual_environments()
                self._update_file_observer()
            self._path_change_timer.start(500)
        except Exception as e:
            self._update_status(f"Error processing path change: {e}", "error")

    # This slot opens a system dialog for the user to select a directory.
    @pyqtSlot()
    def _browse_path(self):
        try:
            current_path = self.path_input.text()
            if not os.path.isdir(current_path):
                current_path = os.path.expanduser("~") # Default to home directory.
            selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", current_path)
            if selected_dir:
                self.path_input.setText(selected_dir)
        except Exception as e:
            self._update_status(f"Could not open directory browser: {e}", "error")

    # This slot opens the selected directory in the system's default file explorer.
    @pyqtSlot()
    def _open_in_explorer(self):
        try:
            path = self.path_input.text().strip()
            if os.path.isdir(path):
                # This code handles opening the file explorer on Windows, macOS, and Linux.
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin":  # macOS
                    subprocess.Popen(["open", path])
                else:  # Linux
                    subprocess.Popen(["xdg-open", path])
            else:
                self._update_status("Directory not found.", "error")
        except Exception as e:
            self._update_status(f"Could not open path: {e}", "error")

    # This slot is triggered by a right-click on the file list widget.
    @pyqtSlot(QPoint)
    def _show_file_context_menu(self, position):
        try:
            item = self.file_list.itemAt(position)
            if not item: return

            base_path = self.path_input.text().strip()
            item_path = os.path.join(base_path, item.text())

            if not os.path.exists(item_path): return

            # Create a QMenu to show the context-sensitive options.
            menu = QMenu()
            is_dir = os.path.isdir(item_path)

            # Add actions to the menu.
            open_emoji = "📂" if is_dir else "🗳"
            open_action = menu.addAction(f"{open_emoji} Open")
            menu.addSeparator()
            copy_path_action = menu.addAction("🔗 Copy Path")
            menu.addSeparator()
            delete_action = menu.addAction("🗑️ Delete")

            # Show the menu at the cursor's position and get the chosen action.
            global_position = self.file_list.mapToGlobal(position)
            action = menu.exec(global_position)

            # Execute code based on which action the user selected.
            if action == open_action:
                self._open_in_explorer_context(item_path)
            elif action == copy_path_action:
                self._copy_path_context(item_path)
            elif action == delete_action:
                self._delete_item_context(item_path, item.text(), is_dir)

        except Exception as e:
            self._update_status(f"Error showing context menu: {e}", "error")

    # --- Helper methods for the context menu actions, each with error handling ---

    def _open_in_explorer_context(self, path):
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self._update_status(f"Error opening '{os.path.basename(path)}': {e}", "error")

    def _copy_path_context(self, path):
        try:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(path)
            self._update_status("Path copied to clipboard.", "info")
        except Exception as e:
            self._update_status(f"Error copying path: {e}", "error")

    def _delete_item_context(self, item_path, item_name, is_dir):
        try:
            # Show a confirmation dialog to prevent accidental deletion.
            confirm_msg = f"Are you sure you want to permanently delete '{item_name}'?"
            reply = QMessageBox.question(self, 'Confirm Deletion', confirm_msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Use the appropriate function for deleting files vs. directories.
                if is_dir:
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                self._update_status(f"Successfully deleted '{item_name}'.", "success")
                # Refresh the UI to reflect the deletion.
                self.discover_virtual_environments()
        except PermissionError:
            self._update_status(f"Permission denied to delete '{item_name}'.", "error")
        except Exception as e:
            self._update_status(f"Error deleting '{item_name}': {e}", "error")

    # This method scans the selected directory for virtual environments and updates the UI.
    def discover_virtual_environments(self):
        try:
            base_path = self.path_input.text().strip()
            self.file_list.clear()
            
            self.path_dependent_widgets = [
                self.open_btn, self.new_venv_name_input, self.create_venv_btn,
                self.venv_dropdown, self.activate_btn, self.install_btn, 
                self.launch_btn, self.install_reqs_btn
            ]
            self.env_dependent_widgets = [
                self.venv_dropdown, self.activate_btn, self.install_btn, 
                self.launch_btn, self.install_reqs_btn
            ]

            if not os.path.isdir(base_path):
                self._update_status("Invalid or inaccessible directory.", "error")
                for widget in self.path_dependent_widgets:
                    widget.setEnabled(False)
                return

            try:
                dir_contents = sorted(os.listdir(base_path))
                self.file_list.addItems(dir_contents)
            except PermissionError:
                self._update_status("Permission denied to read directory contents.", "error")
                return

            for widget in self.path_dependent_widgets:
                widget.setEnabled(True)

            script_folder = "Scripts" if sys.platform == "win32" else "bin"
            venvs = [d for d in dir_contents
                     if os.path.isdir(os.path.join(base_path, d)) and
                     os.path.exists(os.path.join(base_path, d, script_folder, "activate"))]

            current_selection = self.venv_dropdown.currentText()
            self.venv_dropdown.clear()

            if not venvs:
                self.venv_dropdown.addItem("No environments found")
                for widget in self.env_dependent_widgets:
                    widget.setEnabled(False)
                self._update_status("Ready. No virtual environments found", "info")
            else:
                self.venv_dropdown.addItems(sorted(venvs))
                if current_selection in venvs:
                    self.venv_dropdown.setCurrentText(current_selection)
                for widget in self.env_dependent_widgets:
                    widget.setEnabled(True)
                self._update_status("Ready to launch", "info")

        except Exception as e:
            self._update_status(f"Error discovering environments: {e}", "error")

    # Manages the file system observer to watch for directory changes.
    def _update_file_observer(self):
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            path = self.path_input.text().strip()
            if os.path.isdir(path):
                self.observer = Observer()
                self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
                self.observer.start()
        except Exception as e:
            self._update_status(f"Could not start file watcher: {e}", "error")

    # This slot is connected to the 'finished' signal of the CommandThread.
    def _on_command_finished(self, success, message):
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")
        # --- NEW: Refresh env list after successful creation ---
        if success and hasattr(self, 'command_thread') and self.command_thread.command_type == "create_venv":
            # Give the filesystem a moment to catch up before scanning
            QTimer.singleShot(500, self.discover_virtual_environments)


    # This slot is connected to the 'jupyter_started' signal.
    def _on_jupyter_started(self):
        self.running_indicator.setVisible(True)

    # Updates the status label with a message and a colored background.
    def _update_status(self, message, msg_type):
        try:
            color_map = {"success": self.COLOR_SUCCESS, "error": self.COLOR_ERROR, "info": self.COLOR_ACCENT}
            bg_color = color_map.get(msg_type, "transparent")
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"#statusLabel {{ background-color: {bg_color}; color: white; border-radius: 6px; padding: 8px; font-weight: bold; }}")
            if msg_type in ["success", "error"]:
                QTimer.singleShot(4000, lambda: self.status_label.setStyleSheet(f"#statusLabel {{ background: transparent; color: {self.COLOR_TEXT}; font-weight: normal; }}"))
        except Exception as e:
            print(f"Failed to update status label: {e}")

    # Controls the visibility and animation of the progress bar.
    def _set_progress_bar_active(self, is_active):
        try:
            if is_active:
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0) # Indeterminate (spinning) mode.
            else:
                self.progress_bar.setRange(0, 100) # Reset to determinate mode.
                self.progress_bar.setVisible(False)
        except Exception as e:
            print(f"Failed to set progress bar state: {e}")

    # Sets a default path on application startup.
    def _set_default_path(self):
        try:
            # Tries a specific development path first, falls back to the user's home directory.
            dev_path = "P:/Codes/Machine Learning"
            path = dev_path if os.path.isdir(dev_path) else os.path.expanduser("~")
            self.path_input.setText(path)
        except Exception as e:
            self._update_status(f"Could not set default path: {e}", "error")
            self.path_input.setText(os.path.expanduser("~"))

    # --- Window Movement and Closing Event Handlers ---

    # Captures the initial mouse position when clicking on the title bar to start a drag.
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                title_bar_widget = self.container_layout.itemAt(0).widget()
                if title_bar_widget and title_bar_widget.underMouse():
                    self.old_pos = event.globalPosition().toPoint()
        except Exception as e:
            print(f"Error in mousePressEvent: {e}")

    # Moves the window based on the mouse's movement while the button is held down.
    def mouseMoveEvent(self, event):
        try:
            if self.old_pos:
                delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self.old_pos = event.globalPosition().toPoint()
        except Exception as e:
            print(f"Error in mouseMoveEvent: {e}")

    # Resets the drag position when the mouse button is released.
    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # Gracefully stops the file observer thread when the application is closed.
    def closeEvent(self, event):
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join() # Wait for the thread to finish.
            event.accept() # Allow the window to close.
        except Exception as e:
            print(f"Error during shutdown: {e}")
            event.accept()

# --- Application Entry Point ---
# This block of code is executed only when the script is run directly.
if __name__ == "__main__":
    # Crucially, set the global exception hook *before* the QApplication is created.
    # This ensures it can catch errors that might occur during the app's initialization.
    sys.excepthook = global_exception_hook

    app = QApplication(sys.argv)
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))

    # The JupyterLauncher's __init__ is already wrapped in a try-except block,
    # and any unhandled exception will be caught by the global hook.
    window = JupyterLauncher()
    window.show()

    # Start the application's event loop.
    sys.exit(app.exec())