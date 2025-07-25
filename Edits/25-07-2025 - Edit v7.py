import sys
import os
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot
from PyQt6.QtGui import QFont, QIcon

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
            script_folder = "Scripts" if sys.platform == "win32" else "bin"
            activate_script = os.path.join(self.base_path, self.selected_env, script_folder, "activate")

            if self.command_type == "jupyter":
                cmd = 'jupyter notebook'
            elif self.command_type == "install_jupyter":
                cmd = 'pip install jupyter'
            else: 
                cmd = None

            if sys.platform == "win32":
                activate_script += ".bat"
                full_cmd = f'cd /d "{self.base_path}" && "{activate_script}"'
                if cmd:
                    full_cmd += f' && {cmd}'
                subprocess.Popen(f'start cmd /k "{full_cmd}"', shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else: 
                self.finished.emit(False, "Unix-like OS execution is not yet implemented.")
                return

            time.sleep(2)

            if self.command_type == "jupyter":
                self.finished.emit(True, "Jupyter Notebook successfully launched in a new terminal!")
                self.jupyter_started.emit()
            elif self.command_type == "install_jupyter":
                self.finished.emit(True, "Jupyter installation process has been started.")
            else:
                self.finished.emit(True, "Virtual environment activated in a new terminal.")

        except FileNotFoundError:
            self.finished.emit(False, "Error: The 'activate' script could not be found.")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred: {str(e)}")


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_any_event(self, event):
        if event.event_type in ['created', 'deleted', 'moved']:
            self.callback()


class JupyterLauncher(QWidget):
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
        self.setWindowTitle("Notebook Nexus")
        self.setObjectName("JupyterLauncher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(550, 610)

        self.observer = None 
        self.old_pos = None  

        self._setup_main_layout()
        self._setup_ui_components()
        self._apply_stylesheet()
        self._connect_signals()

        self._set_default_path()
        self._update_file_observer()
        self.discover_virtual_environments()

    def _setup_main_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

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
        content_layout.setSpacing(12)

        content_layout.addLayout(self._create_path_section())
        content_layout.addLayout(self._create_venv_section())
        content_layout.addLayout(self._create_status_section())
        content_layout.addLayout(self._create_files_section())
        content_layout.addStretch()
        content_layout.addLayout(self._create_footer_section())

    def _create_title_bar(self):
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
        self.launch_btn.setObjectName("launchBtn")
        btn_layout.addWidget(self.activate_btn)
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.launch_btn)
        layout.addLayout(btn_layout)
        return layout

    def _create_status_section(self):
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
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(QLabel("Directory Contents"))
        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.file_list)
        return layout
        
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

    def _connect_signals(self):
        self.path_input.textChanged.connect(self._on_path_changed)
        self.browse_btn.clicked.connect(self._browse_path)
        self.open_btn.clicked.connect(self._open_in_explorer)
        self.activate_btn.clicked.connect(self._activate_environment)
        self.install_btn.clicked.connect(self._install_jupyter)
        self.launch_btn.clicked.connect(self._launch_jupyter)
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)

        title_bar = self.container_layout.itemAt(0).widget()
        control_buttons = title_bar.findChildren(QPushButton, "controlBtn")

        if len(control_buttons) >= 2:
            control_buttons[1].clicked.connect(self.close)
            control_buttons[0].clicked.connect(self.showMinimized)

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            #JupyterLauncher {{
                background-color: transparent;
            }}
            #container {{
                background-color: {self.COLOR_PRIMARY};
                border: 2px solid {self.COLOR_BORDER_WINDOW};
                border-radius: 15px;
            }}
            QWidget {{
                font-family: "{self.FONT_MAIN}";
                color: {self.COLOR_TEXT};
                font-size: 9pt;
            }}
            #titleBar {{
                background-color: {self.COLOR_BACKGROUND};
                border-top-left-radius: 13px;
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

            QComboBox QAbstractItemView {{
                background-color: {self.COLOR_BACKGROUND};
                border: 1px solid {self.COLOR_BORDER};
                selection-background-color: {self.COLOR_ACCENT};
                color: {self.COLOR_TEXT};
                outline: 0px;
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

    def _run_command(self, command_type):
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
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True)
            self._path_change_timer.timeout.connect(self.discover_virtual_environments)
            self._path_change_timer.timeout.connect(self._update_file_observer)
        self._path_change_timer.start(500)

    @pyqtSlot()
    def _browse_path(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.path_input.text())
        if selected_dir:
            self.path_input.setText(selected_dir)

    @pyqtSlot()
    def _open_in_explorer(self):
        path = self.path_input.text().strip()
        if os.path.isdir(path):
            os.startfile(path)
        else:
            self._update_status("Directory not found.", "error")

    @pyqtSlot(QPoint)
    def _show_file_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item: return

        item_path = os.path.join(self.path_input.text().strip(), item.text())

        emoji = "📁 " if os.path.isdir(item_path) else "📄 "

        menu = QMenu()
        
        open_action = menu.addAction(f"{emoji}Open")
            
        action = menu.exec(self.file_list.mapToGlobal(position))

        if action == open_action and os.path.exists(item_path):
            os.startfile(item_path)

    def discover_virtual_environments(self):
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
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        path = self.path_input.text().strip()
        if os.path.isdir(path):
            self.observer = Observer()
            self.observer.schedule(FileChangeHandler(self.discover_virtual_environments), path, recursive=False)
            self.observer.start()

    def _on_command_finished(self, success, message):
        self._set_progress_bar_active(False)
        self._update_status(message, "success" if success else "error")

    def _on_jupyter_started(self):
        self.running_indicator.setVisible(True)

    def _update_status(self, message, msg_type):
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
        if is_active:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)

    def _set_default_path(self):
        dev_path = "P:/Codes/Machine Learning"
        path = dev_path if os.path.isdir(dev_path) else os.path.expanduser("~")
        self.path_input.setText(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.container_layout.itemAt(0).widget().underMouse():
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
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont(JupyterLauncher.FONT_MAIN, 9))
    window = JupyterLauncher()
    window.show()
    sys.exit(app.exec())