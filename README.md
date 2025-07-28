PyEnv Launcher 📘
<!-- It's highly recommended to replace this with an actual screenshot of your application -->


A modern, cross-platform graphical user interface to simplify the management of Python virtual environments and project-specific tools like Jupyter Notebook.

PyEnv Launcher provides an intuitive interface to handle common tasks associated with Python project development, eliminating the need to memorize and type repetitive commands in the terminal. Manage your project directories, create environments, install packages, and launch tools all from one place.

✨ Key Features

Project-Based Workflow: Center your work around a main project directory.

Virtual Environment Management:

Discover: Automatically detects existing virtual environments (venvs) in your project folder.

Create: Quickly create new Python virtual environments.

Delete: Safely remove environments you no longer need.

Details: View Python version and other details of a selected environment.

Package Management:

Install from File: Easily install all packages from a requirements.txt file.

Freeze: Generate a requirements.txt file from the packages installed in the selected environment.

One-Click Launchers:

Launch Jupyter: Start a Jupyter Notebook session within the context of your activated environment.

Activate Terminal: Open a new terminal/command prompt with the selected environment already activated, ready for your commands.

Integrated File Explorer:

View and interact with the contents of your project directory.

Open files/folders, copy paths, or delete items directly from the UI.

Modern UI & UX:

Themes: Switch between beautiful Dark and Light themes.

Real-time Updates: The UI automatically refreshes when files or folders change in your project directory.

Activity Log: See the output of all commands being run in the background.

System Tray Integration: Minimize the app and see process status at a glance.

Robust and User-Friendly:

Global error handling and logging to error_log.txt.

Remembers recent project paths for quick access.

🚀 Installation (For End-Users)

You can install PyEnv Launcher easily using the provided installer for Windows.

Go to the Releases page of this repository.

Download the latest PyEnvLauncher-Setup.exe file.

Run the installer and follow the on-screen instructions. The application will be installed, and a shortcut will be added to your Start Menu.

That's it! You can now find and run "PyEnv Launcher" from your Start Menu.

🛠️ How to Use

Select Project Directory:

On first launch, the application will default to your user home directory.

Click "Select Directory" or paste a path into the input field to choose your project folder. Your recent paths are saved for quick access.

Create or Select an Environment:

To create a new one: Type a name (e.g., .venv, env) in the "Create New Environment" field and click "Create".

To use an existing one: Select it from the "Manage Existing Environment" dropdown menu.

Manage Packages:

With an environment selected, click "Install from File" to choose a requirements.txt and install its contents.

Click "Freeze to requirements.txt" to save the state of your current environment.

Launch Tools:

Click "Launch Jupyter" to start a Jupyter Notebook server.

Click "Activate" to open a new command prompt with the environment ready to go.

🧑‍💻 For Developers (Building from Source)

If you want to run the application from the source code or contribute to its development, follow these steps.

Prerequisites

Python 3.8+

Git

Setup

Clone the repository:

Generated sh
git clone https://github.com/your-username/pyenv-launcher.git
cd pyenv-launcher


Create and activate a virtual environment:

Generated sh
# On Windows
python -m venv .venv
.\.venv\Scripts\activate
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Sh
IGNORE_WHEN_COPYING_END

Install the required packages:
The application uses PyQt6 and Watchdog. Install them using pip:

Generated sh
pip install PyQt6 watchdog
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Sh
IGNORE_WHEN_COPYING_END

Run the application:

Generated sh
python file.py  #<-- Replace with the actual name of your .py file
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Sh
IGNORE_WHEN_COPYING_END
🔧 Configuration

You can customize the application's theme and default project directory by clicking the Settings icon in the title bar. Settings are saved automatically and will persist between sessions.

🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

Fork the Project

Create your Feature Branch (git checkout -b feature/AmazingFeature)

Commit your Changes (git commit -m 'Add some AmazingFeature')

Push to the Branch (git push origin feature/AmazingFeature)

Open a Pull Request

📄 License

This project is licensed under the MIT License - see the LICENSE.md file for details.

🙏 Acknowledgments

PyQt6 for the powerful GUI framework.

Watchdog for file system monitoring.

The Python community for creating the incredible tools that make this possible.
