<p align="center">
  <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/book-open-reader.svg" width="100" alt="logo">
</p>

<h1 align="center">📘 PyEnv Launcher</h1>

<p align="center">
  <em>A modern GUI to simplify Python virtual environment and project management.</em>
</p>

<p align="center">
    <img src="https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white" alt="Python Version">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
    <img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white" alt="Platform">
    <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <!-- 
    IMPORTANT: REPLACE THIS GIF WITH A SCREENSHOT/GIF OF YOUR ACTUAL APPLICATION!
    A good GIF is the best way to showcase your project.
  -->
  <img src="https://i.imgur.com/gYf2mJj.gif" alt="PyEnv Launcher Demo">
</p>

> Forget memorizing `pip`, `venv`, and `jupyter` commands. PyEnv Launcher brings your entire project workflow—from environment creation to launching tools—into one clean, intuitive, and beautiful interface.

---

## ✨ Key Features

| Category                  | Feature                                                                                             |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| **🌐 Environment Mgmt**   | **Auto-Discover** existing venvs, **Create** new ones, and **Delete** them with a single click.         |
| **📦 Package Mgmt**       | **Install dependencies** from `requirements.txt` or **Freeze** your current environment into a file.  |
| **🚀 One-Click Launchers** | **Launch Jupyter Notebook** or **Activate a Terminal** directly in your selected environment's context. |
| **📂 Integrated Explorer**| View your project's directory, open files, copy paths, and manage contents without leaving the app. |
| **🎨 Modern UI/UX**       | Switch between **Dark & Light themes**, get real-time status updates, and view a detailed activity log. |
| **⚙️ Smart & Robust**     | Remembers **recent paths**, provides global error handling, and runs processes in the background.    |

---

## 🚀 Getting Started (Installation)

Installing PyEnv Launcher is simple.

1.  Navigate to the [**Releases Page**](https://github.com/your-username/pyenv-launcher/releases).
2.  Download the latest `PyEnvLauncher-Setup.exe` file.
3.  Run the installer. It will handle everything and add a shortcut to your Start Menu.

You can now search for `PyEnv Launcher` in the Start Menu and run it!

---

## 🛠️ How to Use

1.  **📍 Select Project Directory**: Use the **`Select Directory`** button to choose your main project folder.
2.  **🌿 Choose Environment**:
    -   Create a new one by typing a name and clicking **`Create`**.
    -   Or, select an existing one from the dropdown menu.
3.  **📦 Manage Packages**:
    -   Click **`Install from File`** to populate your venv from a `requirements.txt`.
    -   Click **`Freeze to requirements.txt`** to save your package list.
4.  **⚡ Launch Tools**:
    -   Click **`Launch Jupyter`** to start a notebook server.
    -   Click **`Activate`** to open a new terminal with the venv ready to go.

---

## 🧑‍💻 For Developers (Building from Source)

Want to run the latest version from source or contribute?

#### Prerequisites
*   Python 3.8+
*   Git

#### Setup
1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/pyenv-launcher.git
    cd pyenv-launcher
    ```

2.  **Create and activate a virtual environment:**
    ```sh
    # Windows
    python -m venv .venv
    .\.venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```sh
    pip install PyQt6 watchdog
    ```

4.  **Run the application:**
    ```python
    python your_script_name.py
    ```

---

### 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

### 📄 License

Distributed under the MIT License. See `LICENSE.md` for more information.

### 🙏 Acknowledgments

A special thank you to the developers and communities behind these incredible tools:

*   [PyQt6](https://riverbankcomputing.com/software/pyqt/)
*   [Watchdog](https://github.com/gorakhargosh/watchdog)
*   [Shields.io](https://shields.io) for the cool badges.
