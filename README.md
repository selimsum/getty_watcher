# Getty Images Watcher

A desktop application built with Python and CustomTkinter that monitors Getty Images for new content based on specific keywords. It automatically downloads new images discovered after a specified cutoff date.

## Features

- **Keyword Monitoring**: Track multiple keywords simultaneously.
- **Automated Downloads**: Automatically downloads new high-resolution images to local folders.
- **Date Filtering**: Set a "From Date" for each keyword to only fetch images newer than that date.
- **Visual Logs**: Real-time log view within the application to track scraping progress.
- **Modern UI**: Built using `customtkinter` for a sleek, modern desktop experience.
- **Notification Support**: Windows toast notifications for new findings.
- **Stealth Scraping**: Uses Playwright with stealth plugins to avoid detection.

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows OS (for toast notifications and EXE support)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/getty_watcher.git
   cd getty_watcher
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

## Usage

Run the application:
```bash
python main.py
```

1. Add keywords you want to monitor in the input field.
2. Set a "From Date" (DD.MM.YYYY) if you want to filter results.
3. Click **Check All** or **Check** for individual keywords to start the process.
4. Images will be saved in the `downloads/` directory, categorized by keyword.

## Building the Executable

To build a standalone `.exe` file:
```bash
python build_app.py
```
The resulting executable will be in the `dist/` folder.

## Project Structure

- `main.py`: The entry point and UI logic.
- `scraper.py`: Core logic for interacting with Getty Images using Playwright.
- `model.py`: State management for keywords and seen images.
- `build_app.py`: PyInstaller build script.
- `icon.png` / `icon.ico`: Application icons.
- `win10toast/`: Local patched version of the toast notification library.

## License

[MIT License](LICENSE)
