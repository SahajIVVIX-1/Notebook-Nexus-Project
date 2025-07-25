Of course! Here is a detailed and professionally designed `README.md` file for your PyEnv Launcher project. It includes a project overview, features, setup instructions, and a step-by-step guide for deployment to an `.exe` file.

---

# 📘 PyEnv Launcher

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![UI Framework](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

A sleek and modern GUI application designed to simplify the management and launching of Jupyter Notebook within Python virtual environments. Built with PyQt6, this tool provides an intuitive interface to browse project directories, auto-detect virtual environments, and launch Jupyter with a single click.

The application features a custom-designed, GitHub-inspired dark theme, ensuring a comfortable and productive user experience. It runs long-running tasks in the background to keep the UI responsive and includes robust error handling to prevent unexpected crashes.


*(You can replace this with your own screenshot)*

## ✨ Key Features

*   **Modern, Themed UI:** A visually appealing and user-friendly interface with a dark theme.
*   **Auto-Discovery:** Automatically scans the selected project directory and populates a list of available Python virtual environments.
*   **One-Click Actions:**
    *   **Launch Jupyter:** Start a Jupyter Notebook server within the selected virtual environment.
    *   **Activate Environment:** Open a new terminal with the selected virtual environment activated.
    *   **Install Jupyter:** A convenient button to run `pip install jupyter` in the selected environment.
*   **Responsive Interface:** Utilizes `QThread` to run command-line operations in the background, preventing the UI from freezing.
*   **Real-time Directory Monitoring:** Uses the `watchdog` library to monitor the project directory for changes (like new folders or deleted environments) and updates the UI automatically.
*   **Built-in File Browser:**
    *   View the contents of your project directory directly within the app.
    *   Right-click context menu to **Open** files/folders, **Copy Path**, or **Delete** items (with a confirmation dialog).
*   **Custom Frameless Window:** A clean, borderless window design with custom controls and support for dragging and resizing.
*   **Robust Error Handling:** A global exception hook logs any unhandled errors to `error_log.txt` and displays a user-friendly message, ensuring application stability.
*   **Cross-Platform (Windows Focus):** The current implementation is optimized for Windows but is structured for future extension to macOS and Linux.

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

*   **Python 3.9 or newer**
*   **pip** (Python package installer)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/SahajIVVIX-1/PyEnv-Launcher-Project.git
    cd pyenv-launcher
    ```

2.  **Create a `requirements.txt` file:**
    Your project uses external libraries that need to be installed. Create a file named `requirements.txt` in the root of your project directory with the following content:
    ```
    PyQt6
    watchdog
    ```

3.  **Install dependencies:**
    It's recommended to use a virtual environment for this project.
    ```bash
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

    # Install the required packages
    pip install -r requirements.txt
    ```

### Usage

To run the application, simply execute the main Python script:

```bash
python your_script_name.py
```
*(Replace `your_script_name.py` with the actual name of your file)*

## 📦 Deployment: Creating a Standalone `.exe`

You can package the application into a single standalone executable (`.exe`) for easy distribution on Windows. We will use **PyInstaller** for this process.

### Step 1: Install PyInstaller

If you don't have it installed, open your terminal or command prompt and run:

```bash
pip install pyinstaller
```

### Step 2: Prepare Assets (Optional)

If you want your `.exe` file to have a custom icon, create or download an icon file (`.ico` format). Place it in your project's root directory (e.g., `icon.ico`).

### Step 3: Run the PyInstaller Command

Navigate to your project's root directory in the terminal and run the following command. This command is tailored for a GUI application like this one.

```bash
pyinstaller --name "PyEnv Launcher" --onefile --windowed --icon="icon.ico" your_script_name.py
```

*   **`--name "PyEnv Launcher"`**: Sets the name of your executable.
*   **`--onefile`**: Bundles everything into a single `.exe` file.
*   **`--windowed`** (or `--noconsole`): **Crucial for GUI apps.** This prevents a console window from opening in the background when you run your application.
*   **`--icon="icon.ico"`**: (Optional) Sets the custom icon for your application.
*   **`your_script_name.py`**: The name of your main Python script.

### Step 4: Locate Your Executable

PyInstaller will create a few folders in your project directory. Your final standalone executable will be located in the **`dist`** folder.

You can now share the **`PyEnv Launcher.exe`** file from the `dist` directory with other Windows users. They won't need to have Python or any libraries installed to run it.

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

## Acknowledgments

*   [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - The UI framework that made this possible.
*   [Watchdog](https://github.com/gorakhargosh/watchdog) - For seamless file system monitoring.
*   [PyInstaller](https://pyinstaller.org/) - For straightforward application packaging.
