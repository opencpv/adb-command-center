# playsetup-tui

An ADB Command Center with a Terminal User Interface (TUI) built using [Textual](https://textual.textualize.io/). This tool allows you to manage multiple Android devices, perform batch installations/uninstallations, and handle wireless debugging directly from your terminal.

## Features

- **Device Management**: Automatically detects connected ADB devices and assigns nicknames for easy identification.
- **Batch Installation**: Support for installing multiple `.apk` and `.xapk` files across multiple devices simultaneously.
- **App Browsing**: View installed 3rd-party apps on a selected device and perform batch uninstalls.
- **Wireless Debugging**: Built-in support for wireless pairing and connection.
- **Deployment History**: Keeps a persistent record of all deployment activities.
- **Live Logs**: Real-time system logs for monitoring ADB commands and responses.

## Prerequisites

- **Python 3.8+**
- **ADB (Android Debug Bridge)** installed and available in your system's `PATH`.
- **Android Device(s)** with Developer Options and USB Debugging (or Wireless Debugging) enabled.

## Installation

1. Clone the repository (or copy the project files).
2. Create a virtual environment (optional but recommended):
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the TUI:
   ```bash
   python3 main.py
   ```
2. Place any APKs you wish to install in the `apks/` directory.
3. Use the interface to select devices and APKs, then press **RUN INSTALL**.

## File Structure

- `main.py`: The entry point and main application logic.
- `requirements.txt`: Python package dependencies.
- `apks/`: Directory where `.apk` and `.xapk` files should be placed for installation.
- `registry.json`: Persistent storage for device serial codes and nicknames.
- `history.json`: Persistent storage for deployment history.


## Keybindings

| Key | Action |
|-----|--------|
| `r` | Refresh devices and APK list |
| `i` | Run installation for selected items |
| `l` | List 3rd-party apps on selected device |
| `h` | Toggle between Live Deployments and History |
| `w` | Wireless Connect |
| `p` | Wireless Pair |
| `k` | Reset ADB server |
| `q` | Quit application |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
