import sys
import os
import subprocess
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip,
    QMessageBox, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QGuiApplication 

# --- Command Execution Thread ---
# This class handles long-running command-line operations (like starting Jupyter) in a separate thread.
# This is crucial for keeping the user interface (UI) responsive. If these commands were run
# on the main thread, the entire application would freeze until the command completes.
class CommandThread(QThread):
    # pyqtSignal is used to send signals from this worker thread back to the main UI thread.
    # This is the safe way to communicate across threads in PyQt.
    # 'finished' signal: Emits a boolean (success/failure) and a status message string.
    finished = pyqtSignal(bool, str)
    # 'jupyter_started' signal: Emits when Jupyter has been successfully launched.
    jupyter_started = pyqtSignal()

    def __init__(self, base_path, selected_env, command_type="jupyter"):
        super().__init__()
        # Store the necessary information for the command.
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type # e.g., "jupyter", "install_jupyter", "activate"

    # The 'run' method is the entry point for the thread. When you call thread.start(), this method is executed.
    def run(self):
        try:
            # Determine the correct subfolder for scripts based on the operating system.
            # Windows uses "Scripts", while Linux and macOS use "bin".
            script_folder = "Scripts" if sys.platform == "win32" else "bin"
            # Construct the full path to the virtual environment's activation script.
            activate_script = os.path.join(self.base_path, self.selected_env, script_folder, "activate")

            # Determine the command to be executed based on the 'command_type'.
            if self.command_type == "jupyter":
                cmd = 'jupyter notebook'
            elif self.command_type == "install_jupyter":
                cmd = 'pip install jupyter'
            else: # For "activate"
                cmd = None

            # --- OS-Specific Command Execution ---
            # The current implementation is for Windows.
            if sys.platform == "win32":
                # On Windows, the activation script for command prompt is a .bat file.
                activate_script += ".bat"
                # This command string first changes the directory ('cd'), then runs the activate script.
                # The '&&' operator chains commands, so the next one runs only if the previous succeeds.
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}"'
                if cmd:
                    # If there's a command to run (like 'jupyter notebook'), append it.
                    full_cmd += f' && {cmd}'
                
                # 'subprocess.Popen' is used to run the command in a new process.
                # 'start cmd /k' opens a new Windows command prompt that remains open (/k) after the command finishes.
                # This is useful for seeing output and errors.
                # 'creationflags=subprocess.CREATE_NEW_CONSOLE' ensures it's a completely new window.
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: 
                # If the OS is not Windows, emit a failure signal as it's not implemented.
                self.finished.emit(False, "Unix-like OS execution is not yet implemented.")
                return

            # Give the system a moment to open the new terminal and start the process.
            time.sleep(2)

            # Emit the 'finished' signal with a success message based on the command type.
            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook successfully launched in a new terminal!")
                # Also emit the specific signal that Jupyter has started.
                self.jupyter_started.emit()
            elif self.command_type == "install_jupyter":
                self.finished.emit(True, "Jupyter installation process has been started.")
            else:
                self.finished.emit(True, "Virtual environment activated in a new terminal.")

        # --- Error Handling ---
        # Catch specific errors to provide more helpful messages.
        except FileNotFoundError:
            self.finished.emit(False, "Error: The 'activate' script could not be found.")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred: {str(e)}")


# --- File System Change Handler ---
# This class uses the 'watchdog' library to monitor the project directory for changes.
# When a file or folder is created, deleted, or moved, it triggers a callback function.
class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        # The 'callback' is a function from the main window that should be called when a change is detected.
        # In this app, it's used to refresh the virtual environment list.
        self.callback = callback

    # This method is called by the watchdog observer for any file system event.
    def on_any_event(self, event):
        # We are only interested in events that change the directory structure.
        if event.event_type in ['created', 'deleted', 'moved']:
            self.callback()


# --- Main Application Window ---
class JupyterLauncher(QWidget):
    # --- Theming and Styling ---
    # Centralizing color and font definitions makes it easy to change the app's look and feel.
    COLOR_BACKGROUND = "#0d1117"
    COLOR_PRIMARY = "#000000"
    COLOR_BORDER = "#30363d"
    COLOR_BORDER_WINDOW = "#87CEEB" # A sky blue for the main window border
    COLOR_TEXT = "#c9d1d9"
    COLOR_TEXT_HEADER = "#f0f6fc"
    COLOR_TEXT_SECONDARY = "#8b949e"
    COLOR_ACCENT = "#2f81f7"
    COLOR_SUCCESS = "#238636"
    COLOR_ERROR = "#da3633"
    FONT_MAIN = "Segoe UI" # A common, modern font on Windows.

    def __init__(self):
        super().__init__()
        # --- Window Setup ---
        self.setWindowTitle("Notebook Nexus")
        self.setObjectName("JupyterLauncher") # This ID is used for top-level styling in CSS.
        
        # These flags create a frameless, transparent window. The main content will be drawn
        # on a 'container' widget inside, allowing for a custom title bar and rounded corners.
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(550, 610)

        # Initialize instance variables.
        self.observer = None  # To hold the watchdog file system observer.
        self.old_pos = None   # To hold the mouse position for dragging the frameless window.

        # --- UI Construction ---
        # Break down the setup into logical methods for better organization.
        self._setup_main_layout()
        self._setup_ui_components()
        self._apply_stylesheet()
        self._connect_signals()

        # --- Initial State Configuration ---
        self._set_default_path()
        self._update_file_observer() # Start monitoring the default path.
        self.discover_virtual_environments() # Find venvs in the default path.

    # Sets up the main container that holds all other UI elements.
    # This is necessary for the custom border and background.
    def _setup_main_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.container = QWidget(self)
        self.container.setObjectName("container") # ID for CSS styling.
        self.main_layout.addWidget(self.container)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2) # Small margin for the border.
        self.container_layout.setSpacing(0)
        
    # Creates all the visible widgets and adds them to the layout.
    def _setup_ui_components(self):
        # Create the custom title bar.
        title_bar = self._create_title_bar()
        self.container_layout.addWidget(title_bar)

        # A scroll area ensures the content is accessible even if the window is small.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame) # No default border.
        self.container_layout.addWidget(scroll_area)

        content_widget = QWidget() # A widget to hold the actual content inside the scroll area.
        scroll_area.setWidget(content_widget)

        # This layout will hold all the main functional parts of the app.
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(12)

        # Add each section by calling its creation method.
        content_layout.addLayout(self._create_path_section())
        content_layout.addLayout(self._create_venv_section())
        content_layout.addLayout(self._create_status_section())
        content_layout.addLayout(self._create_files_section())
        content_layout.addStretch() # Pushes the footer to the bottom.
        content_layout.addLayout(self._create_footer_section())

    # Creates the custom title bar with a title and window controls.
    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("titleBar") # ID for CSS styling.
        title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(15, 0, 5, 0)

        title = QLabel("📘  Stellarium-Sync")
        title.setObjectName("titleLabel")

        # This label will be a green dot to show when Jupyter is running.
        self.running_indicator = QLabel("●")
        self.running_indicator.setObjectName("runningIndicator")
        self.running_indicator.setVisible(False) # Initially hidden.

        # Standard window control buttons.
        minimize_btn = QPushButton("—")
        close_btn = QPushButton("✕")
        for btn in [minimize_btn, close_btn]:
            btn.setObjectName("controlBtn")
            btn.setFixedSize(30, 30)

        layout.addWidget(title)
        layout.addStretch() # Pushes controls to the right.
        layout.addWidget(self.running_indicator)
        layout.addWidget(minimize_btn)
        layout.addWidget(close_btn)
        return title_bar

    # Creates the widgets for selecting the project path.
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

    # Creates the widgets for managing the virtual environment and launching Jupyter.
    def _create_venv_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Virtual Environment"))
        self.venv_dropdown = QComboBox()
        layout.addWidget(self.venv_dropdown)

        btn_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate")
        self.install_btn = QPushButton("Install Jupyter")
        self.launch_btn = QPushButton("Launch Jupyter")
        self.launch_btn.setObjectName("launchBtn") # Special ID for success button styling.
        btn_layout.addWidget(self.activate_btn)
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.launch_btn)
        layout.addLayout(btn_layout)
        return layout

    # Creates the status label and progress bar area.
    def _create_status_section(self):
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.status_label = QLabel("Welcome to Notebook Nexus!")
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
        # Enable custom context menus (for right-clicking on files).
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
   
        # QSizeGrip provides a standard resize handle for the bottom-right corner.
        sizegrip = QSizeGrip(self.container)
        sizegrip.setFixedSize(16, 16)
        
        # Use stretches to center the copyright label.
        footer_layout.addStretch() 
        footer_layout.addWidget(copyright_label) 
        footer_layout.addStretch() 
        footer_layout.addWidget(sizegrip)
        return footer_layout

    # Connects widget signals (like button clicks) to their corresponding slots (handler methods).
    def _connect_signals(self):
        # Path and environment controls
        self.path_input.textChanged.connect(self._on_path_changed)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        
        # Action buttons
        self.activate_btn.clicked.connect(self._activate_environment)
        self.install_btn.clicked.connect(self._install_jupyter)
        self.launch_btn.clicked.connect(self._launch_jupyter)
        
        # File list right-click menu
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        # Custom title bar buttons
        title_bar = self.container_layout.itemAt(0).widget()
        # Find the buttons by their object name. This is less fragile than relying on order.
        control_buttons = title_bar.findChildren(QPushButton, "controlBtn")

        if len(control_buttons) >= 2:
            # Assuming the order is minimize, then close.
            control_buttons[1].clicked.connect(self.close)
            control_buttons[0].clicked.connect(self.showMinimized)

    # Applies all the CSS styling to the application widgets.
    # Using a single stylesheet makes it easy to manage the application's appearance.
    def _apply_stylesheet(self):
        # f-strings are used to insert the color variables defined earlier.
        self.setStyleSheet(f"""
            #JupyterLauncher {{
                background-color: transparent;
            }}
            #container {{
                background-color: {self.COLOR_PRIMARY};
                border: 2px solid {self.COLOR_BORDER_WINDOW};
                border-radius: 15px; /* Rounded corners for the main window */
            }}
            QWidget {{
                font-family: "{self.FONT_MAIN}";
                color: {self.COLOR_TEXT};
                font-size: 9pt;
            }}
            #titleBar {{
                background-color: {self.COLOR_BACKGROUND};
                border-top-left-radius: 13px; /* Match container's rounding */
                border-top-right-radius: 13px;
            }}
            #titleLabel {{
                color: {self.COLOR_TEXT_HEADER};
                font-weight: bold;
                font-size: 11pt;
            }}
            #controlBtn {{
                background: transparent; border: none; font-size: 12pt;
            }}
            #controlBtn:hover {{ background: {self.COLOR_BORDER}; border-radius: 4px; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ 
                background: transparent; 
                border: none; 
            }}
            QLabel {{ font-weight: bold; background: transparent;}}
            QLineEdit, QComboBox {{
                background-color: {self.COLOR_BACKGROUND};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px; padding: 7px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {self.COLOR_ACCENT}; }}
            QComboBox::drop-down {{ border: none; }}

            /* Styling for the dropdown menu itself */
            QComboBox QAbstractItemView {{
                background-color: {self.COLOR_BACKGROUND};
                border: 1px solid {self.COLOR_BORDER};
                selection-background-color: {self.COLOR_ACCENT};
                color: {self.COLOR_TEXT};
                outline: 0px; /* Removes the default focus outline */
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px;
            }}

            QPushButton {{
                background-color: {self.COLOR_BORDER};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px; padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ border-color: #8b949e; background-color: {self.COLOR_BORDER}; }}
            QPushButton:pressed {{ background-color: #21262d; }}
            
            /* Special styling for the main launch button */
            #launchBtn {{
                background-color: {self.COLOR_SUCCESS};
                border-color: #318a44;
            }}
            #launchBtn:hover {{ background-color: #318a44; }}

            #statusLabel {{
                background-color: transparent; border-radius: 6px; padding: 8px;
                font-weight: normal; min-height: 18px;
            }}
            #runningIndicator {{
                color: {self.COLOR_SUCCESS}; font-size: 16pt;
                font-weight: bold; padding-bottom: 4px; /* Align vertically */
            }}
            #copyrightLabel {{
                font-size: 8pt;
                font-weight: normal;
                color: {self.COLOR_TEXT_SECONDARY};
            }}
            QProgressBar {{
                border-radius: 4px; background-color: {self.COLOR_BORDER};
                height: 4px;
            }}
            QProgressBar::chunk {{ background-color: {self.COLOR_ACCENT}; border-radius: 4px; }}

            QListWidget {{
                background-color: {self.COLOR_BACKGROUND};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px; padding: 4px;
            }}
            QListWidget::item {{ padding: 6px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: {self.COLOR_BORDER}; }}
            QListWidget::item:selected {{ background-color: {self.COLOR_ACCENT}; color: white; }}
            
            /* Styling for the right-click context menu */
            QMenu {{
                background-color: {self.COLOR_PRIMARY}; 
                border: 1px solid {self.COLOR_BORDER};
            }}
            QMenu::item:selected {{ 
                background-color: {self.COLOR_ACCENT}; 
            }}
            
            QMenu::item {{
                padding: 5px 10px 5px 10px;
            }}
        """)

    # --- Action Handlers / Slots ---

    # A generic function to start the CommandThread for different actions.
    def _run_command(self, command_type):
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()
        # Basic validation before running a command.
        if not os.path.isdir(base_path) or "found" in selected_env or "Invalid" in selected_env:
            self._update_status("Invalid directory or environment selected.", "error")
            return

        # User-friendly messages for each action.
        messages = {
            "jupyter": "Launching Jupyter Notebook...",
            "install_jupyter": "Starting Jupyter installation...",
            "activate": "Activating environment in new terminal..."
        }
        self._update_status(messages[command_type], "info")
        self._set_progress_bar_active(True) # Show the indeterminate progress bar.

        # Create and start the command thread.
        self.command_thread = CommandThread(base_path, selected_env, command_type)
        self.command_thread.finished.connect(self._on_command_finished)
        if command_type == "jupyter":
            self.command_thread.jupyter_started.connect(self._on_jupyter_started)
        self.command_thread.start()

    # Public-facing methods that call the generic runner.
    def _launch_jupyter(self): self._run_command("jupyter")
    def _activate_environment(self): self._run_command("activate")
    def _install_jupyter(self): self._run_command("install_jupyter")

    # This slot is connected to the path_input's textChanged signal.
    # It uses a QTimer to "debounce" the input, meaning it will only trigger the update
    # after the user has stopped typing for 500ms. This prevents excessive rescanning.
    @pyqtSlot()
    def _on_path_changed(self):
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True) # Only fire once per timer start.
            self._path_change_timer.timeout.connect(self.discover_virtual_environments)
            self._path_change_timer.timeout.connect(self._update_file_observer)
        self._path_change_timer.start(500) # Restart the timer every time the text changes.

    # Opens a system dialog to choose a directory.
    @pyqtSlot()
    def _browse_path(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.path_input.text())
        if selected_dir:
            self.path_input.setText(selected_dir)

    # Opens the current directory in the system's default file manager.
    @pyqtSlot()
    def _open_in_explorer(self):
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            os.startfile(path) # This is a Windows-specific command.
        else:
            self._update_status("Directory not found.", "error")

    # Shows a context menu when the user right-clicks on the file list.
    @pyqtSlot(QPoint)
    def _show_file_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item:
            return

        base_path = self.path_input.text().strip()
        item_name = item.text()
        item_path = os.path.join(base_path, item_name)

        if not os.path.exists(item_path):
            return

        menu = QMenu()
        is_dir = os.path.isdir(item_path)

        # --- Open Action ---
        open_emoji = "📂" if is_dir else "🗳"
        open_action = menu.addAction(f"{open_emoji} Open")
        
        menu.addSeparator()

        # --- Copy Path Action ---
        copy_path_action = menu.addAction("🔗 Copy Path")

        menu.addSeparator()

        # Add the action with both the icon and the text
        delete_icon = ""
        delete_action = menu.addAction("🔐 Delete")

        # --- Show the menu ---
        global_position = self.file_list.mapToGlobal(position)
        action = menu.exec(global_position)

        # --- Process the selected action ---
        if action == open_action:
            os.startfile(item_path)

        elif action == copy_path_action:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(item_path)
            self._update_status("Path copied to clipboard.", "info")

        elif action == delete_action:
            confirm_msg = f"Are you sure you want to permanently delete '{item_name}'?"
            reply = QMessageBox.question(self, 'Confirm Deletion', confirm_msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if is_dir:
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

                    self._update_status(f"Successfully deleted '{item_name}'.", "success")
                    self.discover_virtual_environments()

                except Exception as e:
                    self._update_status(f"Error deleting item: {e}", "error")

    # Scans the current project directory for virtual environments and updates the UI.
    def discover_virtual_environments(self):
        base_path = self.path_input.text().strip()
        is_path_valid = os.path.isdir(base_path)

        # Refresh the file list view.
        self.file_list.clear()
        if is_path_valid:
            try:
                for item in sorted(os.listdir(base_path)):
                    self.file_list.addItem(item)
            except OSError: # Handle cases like permission denied.
                is_path_valid = False

        # Enable or disable buttons based on whether the path is valid.
        for btn in [self.open_btn, self.venv_dropdown, self.activate_btn, self.install_btn, self.launch_btn]:
            btn.setEnabled(is_path_valid)
        if not is_path_valid:
            self._update_status("Invalid or inaccessible directory.", "error")
            return

        # --- Virtual Environment Detection Logic ---
        # A simple but effective way to find a venv is to check for the existence of its 'activate' script.
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        venvs = [d for d in os.listdir(base_path)
                 if os.path.isdir(os.path.join(base_path, d)) and
                 os.path.exists(os.path.join(base_path, d, script_folder, "activate"))]

        current_selection = self.venv_dropdown.currentText()
        self.venv_dropdown.clear()

        if not venvs:
            self.venv_dropdown.addItem("No environments found")
            self.venv_dropdown.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.launch_btn.setEnabled(False)
            self._update_status("Ready. No virtual environments found.", "info")
        else:
            self.venv_dropdown.addItems(sorted(venvs))
            # Restore the previous selection if it's still valid.
            if current_selection in venvs:
                self.venv_dropdown.setCurrentText(current_selection)
            self.venv_dropdown.setEnabled(True)
            self.activate_btn.setEnabled(True)
            self.launch_btn.setEnabled(True)
            self._update_status("Ready to launch.", "info")

    # Restarts the watchdog file observer to monitor the current directory.
    def _update_file_observer(self):
        # Stop the old observer if it exists.
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        path = self.path_input.text().strip()
        if os.path.isdir(path):
            self.observer = Observer()
            # Schedule the handler to call 'discover_virtual_environments' on changes.
            self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
            self.observer.start()

    # This slot is connected to the CommandThread's 'finished' signal.
    def _on_command_finished(self, success, message):
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")

    # This slot is connected to the CommandThread's 'jupyter_started' signal.
    def _on_jupyter_started(self):
        self.running_indicator.setVisible(True)

    # Updates the status label with a colored background for feedback.
    def _update_status(self, message, msg_type):
        color_map = {
            "success": self.COLOR_SUCCESS, "error": self.COLOR_ERROR, "info": self.COLOR_ACCENT
        }
        bg_color = color_map.get(msg_type, "transparent")

        self.status_label.setText(message)
        # Apply temporary styling for feedback.
        self.status_label.setStyleSheet(f"""
            #statusLabel {{
                background-color: {bg_color};
                color: white; border-radius: 6px; padding: 8px; font-weight: bold;
            }}
        """)
        # After 4 seconds, revert the status bar to its normal, non-colored state.
        if msg_type in ["success", "error"]:
            QTimer.singleShot(4000, lambda: self.status_label.setStyleSheet(f"""
                #statusLabel {{ background: transparent; color: {self.COLOR_TEXT}; font-weight: normal; }}
            """))

    # Controls the visibility and state of the progress bar.
    def _set_progress_bar_active(self, is_active):
        if is_active:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # This makes it an indeterminate (busy) indicator.
        else:
            self.progress_bar.setRange(0, 100) # Reset to a normal range.
            self.progress_bar.setVisible(False)

    # Sets a sensible default path on startup.
    def _set_default_path(self):
        # Use a specific development path if it exists, otherwise default to the user's home directory.
        dev_path = "P:/Codes/Machine Learning"
        path = dev_path if os.path.isdir(dev_path) else os.path.expanduser("~")
        self.path_input.setText(path)

    # --- Window Movement Handlers (for Frameless Window) ---

    # When the left mouse button is pressed on the title bar, store the initial position.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if the mouse is over the title bar widget.
            if self.container_layout.itemAt(0).widget().underMouse():
                self.old_pos = event.globalPosition().toPoint()

    # While the mouse is moving (and the button is held), move the window.
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    # When the mouse button is released, stop tracking the position.
    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # This event is triggered when the user tries to close the window.
    def closeEvent(self, event):
        # It's important to gracefully stop the file observer thread before the application exits.
        if self.observer:
            self.observer.stop()
            self.observer.join() # Wait for the thread to finish.
        event.accept() # Allow the window to close.

# --- Application Entry Point ---
if __name__ == "__main__":
    # Standard PyQt application setup.
    app = QApplication(sys.argv)
    # Set a default font for the entire application.
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))
    # Create an instance of our main window.
    window = JupyterLauncher()
    window.show()
    # Start the application's event loop.
    sys.exit(app.exec())