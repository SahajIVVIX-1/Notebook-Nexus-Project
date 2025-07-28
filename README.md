# PyEnv Launcher - The Ultimate Project Control Center

![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Framework](https://img.shields.io/badge/Framework-PyQt6-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

PyEnv Launcher is a comprehensive desktop GUI toolkit designed to streamline the Python development workflow. It moves beyond a simple script runner, providing a centralized, elegant interface for managing project directories, virtual environments (venv and conda), package dependencies, and Git version control, all from a single, visually appealing application.

This tool was born from the need to eliminate the constant context-switching between file explorers, terminals, and IDEs, allowing developers and data scientists to focus on what matters: building great software.

---

## Screenshot

*A picture is worth a thousand commands. Here is the modern two-column layout in action.*

<a href="https://ibb.co/FkWnsZyJ"><img src="https://i.ibb.co/7xzbgMZV/Dark-UI.png" alt="Dark-UI" border="0"></a><br /><a target='_blank' href='https://usefulwebtool.com/fr/clavier-mathematique'></a><br />

---

## Core Features

PyEnv Launcher is packed with features designed to enhance productivity and provide critical project insights at a glance.

### 🏛️ Project & Path Management
- **Centralized Path Control:** Set a project directory and instantly access all relevant files and tools.
- **Recent Projects Menu:** A quick-access dropdown menu to jump between your most recent projects.
- **One-Click "New Project":** Create a standardized, professional project structure (`data`, `notebooks`, `src`, `.gitignore`) with a single click.
- **File System Integration:** Open your project directory directly in your system's file explorer (`Explorer`, `Finder`, etc.).

### 🐍 Advanced Environment Management
- **Automatic Discovery:** Scans your project directory and system to find all available **venv** and **Conda** environments automatically.
- **Environment Creation & Deletion:** Create new, clean virtual environments or safely delete old ones directly from the UI.
- **At-a-Glance Details:** Selecting an environment instantly displays its Python version and creation date.
- **Activate in Terminal:** Launch a new terminal/console window with the selected environment already activated, ready for your commands.
- **One-Click Tool Launcher:** Directly launch tools like Jupyter Notebook within the context of your chosen environment.

### 📦 Interactive Package Management
- **Live Package Listing:** View all installed packages and their versions for the selected environment in a clean, filterable table.
- **Vulnerability Check (Outdated Packages):** The "Check for Updates" button scans for outdated packages using `pip` and highlights them visually in the table.
- **One-Click Upgrade:** Select an outdated package and click "Upgrade" to install the latest version.
- **Safe Uninstall:** Select any package and click "Uninstall" (with a confirmation dialog) to remove it.
- **Dependency Exporting:**
    - **`Freeze to requirements.txt`**: Generates a classic `requirements.txt` file.
    - **`Export to packages.json`**: Creates a `packages.json` file, perfect for custom install scripts.
    - **`Install from File`**: Install dependencies from a `requirements.txt` or `packages.json` file.

### 🌳 Integrated Git Controls
- **Live Git Status:** Automatically detects if a directory is a Git repository and displays the current **branch name** and **status** (Clean or Dirty).
- **Git Actions:**
    - **`Git Pull`**: Fetch and merge the latest changes from the remote repository.
    - **`Git Commit`**: A comprehensive commit workflow that checks for changes, prompts for a detailed commit message, stages all changes, and then commits.

### 🛠️ Build Tool Support
- **Automatic Detection:** The "Build Tools" section (with `Poetry Install` and `PDM Sync` buttons) automatically appears only if a `pyproject.toml` file is found in the project root.

### ✨ Modern User Experience
- **Elegant Theming:** Choose between a beautiful, GitHub-inspired **Dark Theme** and a clean **Light Theme**. Your choice is saved across sessions.
- **Two-Column Layout:** A modern, IDE-like interface with controls on the left and project files/logs on the right.
- **Custom-Styled Interface:** From the frameless window and draggable title bar to the custom-themed scrollbars, every element is styled for a cohesive experience.
- **Activity Log:** See a timestamped log of all actions, command outputs, and errors in a dedicated panel.

---

## 💾 Download the Standalone Application

For users who prefer a ready-to-run application without setting up a Python environment, a standalone executable is available.

To download it, please visit the **[Latest Release](link/to/your/releases)** page of this GitHub repository.

Within the release notes for the latest version, you will find a direct download link to the compiled application hosted on the **Internet Archive (archive.org)**. This ensures stable, long-term preservation and access to the software.

---

## 🚀 Running From Source

If you are a developer and wish to run the application from its source code, follow these steps.

### Prerequisites
- Python 3.11 or newer
- `pip` (Python's package installer)

### Installation Steps
1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/pyenv-launcher.git
    cd pyenv-launcher
    ```

2.  **Install the required dependencies:**
    The application relies on `PyQt6` for the interface and `watchdog` for monitoring file system changes.
    ```sh
    pip install PyQt6 watchdog
    ```

3.  **Run the application:**
    Execute the main Python script to launch the GUI.
    ```sh
    python main.py 
    ```
    *(Note: The main script may be named `JupyterLauncher.py` or similar in your project)*

---

## ⚙️ Configuration

Application settings can be configured via the "Settings" dialog (gear icon in the title bar):
- **Theme:** Switch between "Dark" and "Light" mode.
- **Default Project Directory:** Set the initial directory the application opens to on startup.

These settings are automatically saved to your user's local configuration directory and persist between sessions.

---

## 📜 License

The source code of this project is licensed under the **MIT License**. See the `LICENSE` file for more details.

The application itself is distributed with an **End-User License Agreement (EULA)**, which can be viewed in the "About" dialog within the software.

---

## 🤝 Contributing

Contributions are welcome! If you have ideas for new features, bug fixes, or improvements, please feel free to:
1.  Open an issue to discuss the change.
2.  Fork the repository and create a new branch.
3.  Submit a pull request with your improvements.
