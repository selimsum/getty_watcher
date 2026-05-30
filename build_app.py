import PyInstaller.__main__

# Define the arguments for PyInstaller
args = [
    'main.py',                          # Script to convert
    '--name=GettyWatcher',              # Name of the executable
    '--onefile',                        # Single executable file
    '--windowed',                       # No console window
    '--icon=icon.ico',                  # Icon file
    '--add-data=icon.png;.',            # Include icon.png in root
    '--add-data=icon.ico;.',            # Include icon.ico in root
    '--add-data=win10toast;win10toast',  # Include local patched win10toast
    '--collect-all=customtkinter',      # Collect customtkinter resources
    '--collect-all=playwright_stealth',  # Collect stealth JS files
    '--hidden-import=PIL.Image',        # Ensure PIL is imported
    '--hidden-import=PIL.ImageTk',      # Ensure PIL.ImageTk is imported
    '--hidden-import=win10toast',       # Ensure win10toast is imported
    '--hidden-import=playwright',
    '--hidden-import=playwright_stealth',
    '--hidden-import=pkg_resources',    # pkg_resources if present
    '--clean',                          # Clean cache
    '--noconfirm',                      # Overwrite output
]

# Run PyInstaller
print(f"Building executable with args: {args}")
PyInstaller.__main__.run(args)
