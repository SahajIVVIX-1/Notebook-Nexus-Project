import sys
import os
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot
from PyQt6.QtGui import QFont, QIcon

# It's recommended to generate a resource file for icons.
# For now, ensure you have 'icons/folder.png' and 'icons/file.png' or the code will run without them.

class CommandThread(QThread):
    """Executes shell commands in a separate thread to keep the UI responsive."""
    finished = pyqtSignal(bool, str)
    jupyter_started = pyqtSignal()

    def __init__(self, base_path, selected_env, command_type="jupyter"):
        super().__init__()
        self.base_path = base_path
        self.selected_env = selected_env
        self.command_type = command_type

    def run(self):
        try:
            # Platform-specific script path
            script_folder = "Scripts" if sys.platform == "win32" else "bin"
            activate_script = os.path.join(self.base_path, self.selected_env, script_folder, "activate")
            
            # Construct the command
            if self.command_type == "jupyter":
                cmd = 'jupyter notebook'
            elif self.command_type == "install_jupyter":
                cmd = 'pip install jupyter'
            else: # "activate"
                cmd = None

            # Execute the command in a new terminal
            if sys.platform == "win32":
                activate_script += ".bat"
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}"'
                if cmd:
                    full_cmd += f' && {cmd}'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: # macOS/Linux (basic implementation)
                self.finished.emit(False, "Unix-like OS execution requires terminal-specific commands.")
                return

            time.sleep(2)  # Give the new terminal a moment to launch

            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook launched!")
                self.jupyter_started.emit()
            elif self.command_type == "install_jupyter":
                self.finished.emit(True, "Jupyter installation started.")
            else:
                self.finished.emit(True, "Virtual environment activated.")

        except FileNotFoundError:
            self.finished.emit(False, "Error: 'activate' script not found.")
        except Exception as e:
            self.finished.emit(False, f"An error occurred: {str(e)}")


class FileChangeHandler(FileSystemEventHandler):
    """Notifies the main thread when a file system event occurs."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        if event.event_type in ['created', 'deleted', 'moved']:
            self.callback()


class JupyterLauncher(QWidget):
    """A sleek, modern launcher for Jupyter Notebook environments."""
    # --- Color Palette & Fonts ---
    COLOR_BACKGROUND = "#0d1117"
    COLOR_PRIMARY = "#161b22"
    COLOR_BORDER = "#30363d"
    COLOR_TEXT = "#c9d1d9"
    COLOR_TEXT_HEADER = "#f0f6fc"
    COLOR_TEXT_SECONDARY = "#8b949e"
    COLOR_ACCENT = "#2f81f7"
    COLOR_SUCCESS = "#238636"
    COLOR_ERROR = "#da3633"
    FONT_MAIN = "Segoe UI"

    def __init__(self):
        super().__init__()
        # --- Window Setup ---
        self.setWindowTitle("Notebook Nexus")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(550, 650)

        # --- State ---
        self.observer = None
        self.old_pos = None

        # --- UI Construction ---
        self._setup_main_layout()
        self._setup_ui_components()
        self._apply_stylesheet()
        self._connect_signals()

        # --- Initial State ---
        self._set_default_path()
        self._update_file_observer()
        self.discover_virtual_environments()

    def _setup_main_layout(self):
        """Initializes the main container and layout for a custom frameless window."""
        self.container = QWidget(self)
        self.container.setObjectName("container")
        
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.addWidget(self.container)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

    def _setup_ui_components(self):
        """Creates and arranges all UI widgets."""
        title_bar = self._create_title_bar()
        self.main_layout.addWidget(title_bar)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.main_layout.addWidget(scroll_area)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(12)

        content_layout.addLayout(self._create_path_section())
        content_layout.addLayout(self._create_venv_section())
        content_layout.addLayout(self._create_status_section())
        content_layout.addLayout(self._create_files_section())
        content_layout.addStretch()

    def _create_title_bar(self):
        """Builds the custom draggable title bar with controls."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(15, 0, 5, 0)

        title = QLabel("📘  Notebook Nexus")
        title.setObjectName("titleLabel")

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

    def _create_path_section(self):
        """Builds the project directory selection UI."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Project Directory"))
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter or browse to your project path")
        layout.addWidget(self.path_input)
        
        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.open_btn = QPushButton("Open in Explorer")
        btn_layout.addWidget(self.browse_btn)
        btn_layout.addWidget(self.open_btn)
        layout.addLayout(btn_layout)
        return layout
        
    def _create_venv_section(self):
        """Builds the virtual environment selection and action buttons."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Virtual Environment"))
        self.venv_dropdown = QComboBox()
        layout.addWidget(self.venv_dropdown)
        
        btn_layout = QHBoxLayout()
        self.activate_btn = QPushButton("Activate")
        self.install_btn = QPushButton("Install Jupyter")
        self.launch_btn = QPushButton("Launch Jupyter")
        self.launch_btn.setObjectName("launchBtn")
        btn_layout.addWidget(self.activate_btn)
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.launch_btn)
        layout.addLayout(btn_layout)
        return layout

    def _create_status_section(self):
        """Builds the status label and progress bar."""
        layout = QVBoxLayout()
        layout.setSpacing(4)
        self.status_label = QLabel("Welcome to Notebook Nexus!")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        return layout

    def _create_files_section(self):
        """Builds the directory contents list and live sync toggle."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Directory Contents"))
        header_layout.addStretch()
        
        sync_label = QLabel("Live Sync:")
        sync_label.setObjectName("syncLabel")
        header_layout.addWidget(sync_label)
        
        self.monitor_toggle = QPushButton()
        self.monitor_toggle.setCheckable(True)
        self.monitor_toggle.setChecked(True)
        self.monitor_toggle.setObjectName("toggleBtn")
        header_layout.addWidget(self.monitor_toggle)
        layout.addLayout(header_layout)

        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.file_list)
        return layout

    def _connect_signals(self):
        """Connects widget signals to appropriate slots."""
        self.path_input.textChanged.connect(self._on_path_changed)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        self.activate_btn.clicked.connect(self._activate_environment)
        self.install_btn.clicked.connect(self._install_jupyter)
        self.launch_btn.clicked.connect(self._launch_jupyter)
        self.monitor_toggle.clicked.connect(self._update_file_observer)
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        # Correct way to find the title bar and its children
        title_bar = self.main_layout.itemAt(0).widget()
        control_buttons = title_bar.findChildren(QPushButton, "controlBtn")
        
        # Assuming close is the second button and minimize is the first
        if len(control_buttons) >= 2:
            control_buttons[1].clicked.connect(self.close)
            control_buttons[0].clicked.connect(self.showMinimized)

        
    def _apply_stylesheet(self):
        """Sets the application-wide stylesheet."""
        self.setStyleSheet(f"""
            QWidget {{
                font-family: "{self.FONT_MAIN}";
                color: {self.COLOR_TEXT};
                font-size: 9pt;
            }}
            QWidget#container {{
                background-color: {self.COLOR_PRIMARY};
                border: 1px solid {self.COLOR_BORDER}; /* Add a border */
                border-radius: 8px; /* Apply rounded corners to the whole container */
            }}
            #titleBar {{
                background-color: {self.COLOR_BACKGROUND};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
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
            QScrollArea {{ background: transparent; border: none; }}
            QLabel {{ font-weight: bold; }}
            QLineEdit, QComboBox {{
                background-color: {self.COLOR_BACKGROUND};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px; padding: 7px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {self.COLOR_ACCENT}; }}
            QComboBox::drop-down {{ border: none; }}
            
            QPushButton {{
                background-color: {self.COLOR_BORDER};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px; padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ border-color: #8b949e; background-color: {self.COLOR_BORDER}; }}
            QPushButton:pressed {{ background-color: #21262d; }}
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
                font-weight: bold; padding-bottom: 4px;
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
            QMenu {{
                background-color: {self.COLOR_PRIMARY}; border: 1px solid {self.COLOR_BORDER};
            }}
            QMenu::item:selected {{ background-color: {self.COLOR_ACCENT}; }}

            #syncLabel {{
                font-weight: normal;
                color: {self.COLOR_TEXT_SECONDARY};
            }}
            #toggleBtn {{
                background-color: {self.COLOR_BORDER};
                border-radius: 10px;
                width: 36px;
                height: 20px;
                border: none;
            }}
            #toggleBtn::indicator {{
                background-color: {self.COLOR_TEXT_SECONDARY};
                border-radius: 8px;
                width: 16px;
                height: 16px;
                margin: 2px;
            }}
            #toggleBtn:checked {{
                background-color: {self.COLOR_ACCENT};
            }}
            #toggleBtn:checked::indicator {{
                margin-left: 18px;
                background-color: white;
            }}
        """)

    # --- Actions and Slots ---
    def _run_command(self, command_type):
        """A centralized method to run commands via CommandThread."""
        base_path = self.path_input.text().strip()
        selected_env = self.venv_dropdown.currentText()
        if not os.path.isdir(base_path) or "found" in selected_env or "Invalid" in selected_env:
            self._update_status("Invalid directory or environment selected.", "error")
            return

        messages = {
            "jupyter": "Launching Jupyter Notebook...",
            "install_jupyter": "Starting Jupyter installation...",
            "activate": "Activating environment in new terminal..."
        }
        self._update_status(messages[command_type], "info")
        self._set_progress_bar_active(True)

        self.command_thread = CommandThread(base_path, selected_env, command_type)
        self.command_thread.finished.connect(self._on_command_finished)
        if command_type == "jupyter":
            self.command_thread.jupyter_started.connect(self._on_jupyter_started)
        self.command_thread.start()

    def _launch_jupyter(self): self._run_command("jupyter")
    def _activate_environment(self): self._run_command("activate")
    def _install_jupyter(self): self._run_command("install_jupyter")

    @pyqtSlot()
    def _on_path_changed(self):
        """Handles text changes in the path input with a debounce timer."""
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True)
            self._path_change_timer.timeout.connect(self.discover_virtual_environments)
            self._path_change_timer.timeout.connect(self._update_file_observer)
        self._path_change_timer.start(500)

    @pyqtSlot()
    def _browse_path(self):
        """Opens a dialog to select a project directory."""
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.path_input.text())
        if selected_dir:
            self.path_input.setText(selected_dir)

    @pyqtSlot()
    def _open_in_explorer(self):
        """Opens the current directory in the native file explorer."""
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            os.startfile(path)
        else:
            self._update_status("Directory not found.", "error")

    @pyqtSlot(QPoint)
    def _show_file_context_menu(self, position):
        """Shows a context menu for items in the file list."""
        item = self.file_list.itemAt(position)
        if not item: return

        item_path = os.path.join(self.path_input.text().strip(), item.text())
        
        menu = QMenu()
        open_action = menu.addAction("Open")
        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == open_action and os.path.exists(item_path):
            os.startfile(item_path)
            
    # --- State & UI Updaters ---

    def discover_virtual_environments(self):
        """Scans the directory for Python virtual environments and updates the UI."""
        base_path = self.path_input.text().strip()
        is_path_valid = os.path.isdir(base_path)

        self.file_list.clear()
        if is_path_valid:
            try:
                for item in sorted(os.listdir(base_path)):
                    self.file_list.addItem(item)
            except OSError:
                is_path_valid = False

        for btn in [self.open_btn, self.venv_dropdown, self.activate_btn, self.install_btn, self.launch_btn]:
            btn.setEnabled(is_path_valid)
        if not is_path_valid:
            self._update_status("Invalid or inaccessible directory.", "error")
            return
            
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
            if current_selection in venvs:
                self.venv_dropdown.setCurrentText(current_selection)
            self.venv_dropdown.setEnabled(True)
            self.activate_btn.setEnabled(True)
            self.launch_btn.setEnabled(True)
            self._update_status("Ready to launch.", "info")

    def _update_file_observer(self):
        """Starts or stops the file system observer based on UI state."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        if self.monitor_toggle.isChecked():
            path = self.path_input.text().strip()
            if os.path.isdir(path):
                self.observer = Observer()
                self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
                self.observer.start()

    def _on_command_finished(self, success, message):
        """Handles the result of a command thread."""
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")

    def _on_jupyter_started(self):
        """Updates UI when Jupyter is confirmed to be running."""
        self.running_indicator.setVisible(True)

    def _update_status(self, message, msg_type):
        """Updates the status label with a message and color."""
        color_map = {
            "success": self.COLOR_SUCCESS, "error": self.COLOR_ERROR, "info": self.COLOR_ACCENT
        }
        bg_color = color_map.get(msg_type, "transparent")
        
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"""
            #statusLabel {{
                background-color: {bg_color};
                color: white; border-radius: 6px; padding: 8px; font-weight: bold;
            }}
        """)
        if msg_type in ["success", "error"]:
            QTimer.singleShot(4000, lambda: self.status_label.setStyleSheet(f"""
                #statusLabel {{ background: transparent; color: {self.COLOR_TEXT}; font-weight: normal; }}
            """))

    def _set_progress_bar_active(self, is_active):
        """Shows/hides and animates the progress bar."""
        if is_active:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)

    def _set_default_path(self):
        """Sets an initial project path."""
        dev_path = "P:/Codes/Machine Learning"
        path = dev_path if os.path.isdir(dev_path) else os.path.expanduser("~")
        self.path_input.setText(path)

    # --- Window Events ---
    def mousePressEvent(self, event):
        """Captures mouse press events for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.main_layout.itemAt(0).widget().underMouse():
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Handles window dragging."""
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseReleaseEvent(self, event):
        """Resets dragging state on mouse release."""
        self.old_pos = None

    def closeEvent(self, event):
        """Ensures the file observer is stopped on exit."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())