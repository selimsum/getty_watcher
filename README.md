# Getty Images Watcher

A desktop application that monitors [Getty Images](https://www.gettyimages.com) editorial search results for user-defined keywords and automatically downloads newly discovered images. Built with Python, CustomTkinter, and Playwright.

![Version](https://img.shields.io/badge/version-2.2-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## Features

- **Keyword Monitoring** — Add unlimited search keywords and check them individually or all at once.
- **Smart Deduplication** — Tracks seen image IDs per keyword so you only download genuinely new content.
- **Cutoff Date Filter** — Set a "From Date" per keyword to skip images older than a specific date. Automatically advances after each check.
- **Full-Resolution Downloads** — Resolves and saves the highest available image resolution directly from Getty's detail pages.
- **Firefox Cookie Injection** — Optionally reads your `gettyimages.com` cookies from Firefox's local profile to bypass page-view limits and reduce bot-detection.
- **Stealth Scraping** — Uses `playwright-stealth` with a Firefox headless browser to minimize fingerprinting.
- **Windows Toast Notifications** — Native desktop notifications when a download batch completes (via a vendored `win10toast` library).
- **Persistent State** — All keywords, settings, and seen-image history are saved to `data.json`.

---

## Architecture

```
main.py          Entry point + CustomTkinter GUI
scraper.py       Playwright-driven scraping and full-res URL resolution
model.py         StateManager — keywords, seen images, settings (JSON-backed)
cookies.py       Firefox cookie extraction (cross-platform profile discovery)
build_app.py     PyInstaller build script
win10toast/      Vendored & patched Windows toast library
```

---

## Requirements

| Dependency | Purpose |
|---|---|
| `playwright` | Headless Firefox browser automation |
| `playwright-stealth` | Anti-detection stealth patches |
| `customtkinter` | Modern themed Tkinter UI |
| `requests` | HTTP downloads with streaming |
| `Pillow` | Icon/image handling |
| `win10toast` *(Windows only)* | Native toast notifications |
| `pywin32` *(Windows only)* | Windows API bindings for toast library |

All versions are pinned in `requirements.txt`.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/selimsum/getty_watcher.git
cd getty_watcher
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

The app auto-installs Firefox on first run if missing, but you can do it manually:

```bash
python -m playwright install firefox
```

---

## Usage

### Run from source

```bash
python main.py
```

### Build a standalone executable (Windows)

```bash
pip install pyinstaller
python build_app.py
```

The resulting `GettyWatcher.exe` will be in the `dist/` folder.

> **Note:** Playwright browser binaries must be installed on the target machine at  
> `%LOCALAPPDATA%\ms-playwright`. The app sets `PLAYWRIGHT_BROWSERS_PATH` to this location automatically.

---

## How It Works

1. **Add keywords** in the left panel and optionally set a "From Date" (`DD.MM.YYYY`) per keyword.
2. Click **Check** on a single keyword or **Check All** to scan every keyword.
3. The scraper opens Getty's editorial image search sorted by newest, paginating until it hits the cutoff date or the last seen image ID.
4. New images (not in the seen-history) are resolved to full-resolution URLs in a batch, then downloaded to `<download_dir>/<keyword>/`.
5. Seen image IDs and the cutoff date are persisted so the next check picks up exactly where the last one left off.

### File naming convention

Downloaded files follow the pattern:

```
YYYY.MM.DD <Image Title> <GettyID>.jpg
```

Example: `2026.06.01 Champions League Final 1498765432.jpg`

---

## Settings

Access via the **Settings** button in the toolbar:

| Setting | Description |
|---|---|
| **Download location** | Folder where images are saved (relative or absolute path). |
| **Show system notifications** | Enable/disable Windows toast notifications after downloads. |
| **Use Firefox cookies** | Reads `gettyimages.com` cookies from your Firefox profile to bypass page limits. Requires Firefox to be installed and logged in to Getty Images. |

---

## Firefox Cookies Setup

To enable cookie-based bypass:

1. Log in to [gettyimages.com](https://www.gettyimages.com) in Firefox.
2. In the app's Settings, ensure **Use Firefox cookies** is checked.
3. The app reads `cookies.sqlite` from your Firefox profile directory:
   - **Windows:** `%APPDATA%\Mozilla\Firefox\Profiles\`
   - **macOS:** `~/Library/Application Support/Firefox/Profiles/`
   - **Linux:** `~/.mozilla/firefox/` (or Snap path)

> Firefox can remain running — the app copies the database to a temp file to avoid lock conflicts.

---

## Project Structure

```
getty_watcher/
├── main.py               # GUI + orchestration
├── scraper.py            # GettyScraper (Playwright + stealth)
├── model.py              # StateManager (JSON persistence)
├── cookies.py            # Firefox cookie extraction
├── build_app.py          # PyInstaller build configuration
├── requirements.txt      # Pinned dependencies
├── data.json             # Runtime state (auto-generated)
├── icon.png / icon.ico   # Application branding
├── win10toast/           # Vendored toast library
├── tests/                # Unit tests
│   ├── test_main.py
│   ├── test_model.py
│   └── test_scraper.py
└── .github/workflows/
    └── build.yml         # CI build pipeline
```

---

## Testing

```bash
python -m pytest
```

---

## License

This project is licensed under the [MIT License](LICENSE).
