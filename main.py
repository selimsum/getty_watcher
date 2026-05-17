import customtkinter as ctk
import threading
import tkinter as tk
import sys
import os
import webbrowser
import time
import datetime
import requests
import re
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
try:
    from win10toast import ToastNotifier
except Exception as e:
    ToastNotifier = None
    TOAST_IMPORT_ERROR = e
else:
    TOAST_IMPORT_ERROR = None
from model import DEFAULT_DOWNLOAD_DIR, StateManager
from scraper import GettyScraper

APP_NAME = "Getty Images Watcher"
APP_VERSION = "2.1"
APP_DESCRIPTION = "Monitors Getty Images keywords and downloads newly discovered images."

# Fix for Playwright in PyInstaller: Force use of local browsers
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

try:
    import ctypes
    # Change ID to force refresh
    myappid = 'gettywatcher.v2.1' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

class RedirectText:
    def __init__(self, text_widget):
        self.output = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def write(self, string):
        try:
            self.output.insert("end", string)
            self.output.see("end")
        except Exception:
            pass
             
        if self.original_stdout:
            self.original_stdout.write(string)
             
    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()

class KeywordsFrame(ctk.CTkFrame):
    def __init__(self, parent, state_manager, check_callback, stop_callback):
        super().__init__(parent)
        self.state_manager = state_manager
        self.check_callback = check_callback
        self.stop_callback = stop_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        fonts = ("Arial", 12, "bold")
        ctk.CTkLabel(self.header_frame, text="Keyword", font=fonts, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkLabel(self.header_frame, text="Last Check", font=fonts, width=120, anchor="w").grid(row=0, column=1, padx=5)
        ctk.CTkLabel(self.header_frame, text="New", font=fonts, width=60, anchor="w").grid(row=0, column=2, padx=5)
        ctk.CTkLabel(self.header_frame, text="From Date", font=fonts, width=100, anchor="w").grid(row=0, column=3, padx=5)
        ctk.CTkLabel(self.header_frame, text="Action", font=fonts, width=80, anchor="center").grid(row=0, column=4, padx=5)
        ctk.CTkLabel(self.header_frame, text="", width=60).grid(row=0, column=5, padx=5)

        # 2. Scrollable List
        self.keyword_scroll = ctk.CTkScrollableFrame(self, label_text="")
        self.keyword_scroll.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.keyword_scroll.grid_columnconfigure(0, weight=1)
        
        # 3. Controls
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.controls_frame.grid_columnconfigure(0, weight=1)

        self.new_keyword_entry = ctk.CTkEntry(self.controls_frame, placeholder_text="New Keyword")
        self.new_keyword_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.new_keyword_entry.bind("<Return>", self.add_keyword)

        self.add_keyword_button = ctk.CTkButton(self.controls_frame, text="Add", width=60, command=self.add_keyword)
        self.add_keyword_button.grid(row=0, column=1, padx=(0, 20))

        self.check_all_button = ctk.CTkButton(self.controls_frame, text="Check All", fg_color="green", hover_color="darkgreen", width=100, command=lambda: self.check_callback(None))
        self.check_all_button.grid(row=0, column=2, padx=(0, 10))

        self.stop_button = ctk.CTkButton(self.controls_frame, text="Stop", fg_color="red", hover_color="darkred", state="disabled", width=60, command=self.stop_callback)
        self.stop_button.grid(row=0, column=3)

        self.keyword_widgets = {}
        self.empty_label = None
        self.refresh_keywords()

    def add_keyword(self, event=None):
        keyword = self.new_keyword_entry.get().strip()
        if keyword:
            self.state_manager.add_keyword(keyword)
            self.new_keyword_entry.delete(0, "end")
            self.refresh_keywords()

    def remove_keyword(self, keyword):
        self.state_manager.remove_keyword(keyword)
        self.refresh_keywords()

    def refresh_keywords(self):
        for widget in self.keyword_widgets.values():
            widget.destroy()
        self.keyword_widgets.clear()
        if self.empty_label is not None:
            self.empty_label.destroy()
            self.empty_label = None

        keywords = self.state_manager.get_keywords()
        if not keywords:
            self.empty_label = ctk.CTkLabel(
                self.keyword_scroll,
                text="No keywords yet. Add one below to start watching Getty Images.",
                text_color="gray",
            )
            self.empty_label.pack(fill="x", pady=30)
            return

        for kw in keywords:
            frame = ctk.CTkFrame(self.keyword_scroll)
            frame.pack(fill="x", pady=2)
            frame.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(frame, text=kw, anchor="w", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=5)
            
            settings = self.state_manager.get_keyword_settings(kw)
            last_checked = settings.get("last_checked", "Never")
            ctk.CTkLabel(frame, text=last_checked, width=120, anchor="w", text_color="gray").grid(row=0, column=1, padx=5)

            last_new_count = settings.get("last_new_count", 0)
            ctk.CTkLabel(frame, text=str(last_new_count), width=60, anchor="w", text_color="gray").grid(row=0, column=2, padx=5)
            
            cutoff = settings.get("cutoff_date", "")
            date_ent = ctk.CTkEntry(frame, width=100, placeholder_text="DD.MM.YYYY")
            date_ent.insert(0, cutoff)
            date_ent.grid(row=0, column=3, padx=5)
            
            date_ent.bind("<FocusOut>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))
            date_ent.bind("<Return>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))

            ctk.CTkButton(frame, text="Check", width=80, command=lambda k=kw: self.check_callback(k)).grid(row=0, column=4, padx=5)
            ctk.CTkButton(frame, text="Delete", width=60, fg_color="red", hover_color="darkred", command=lambda k=kw: self.remove_keyword(k)).grid(row=0, column=5, padx=5)

            self.keyword_widgets[kw] = frame

    def save_date(self, keyword, entry_widget):
        val = entry_widget.get().strip()
        if val:
            try:
                datetime.datetime.strptime(val, "%d.%m.%Y")
            except ValueError:
                entry_widget.configure(border_color="red")
                print(f"Invalid cutoff_date for {keyword}: {val}. Use DD.MM.YYYY.")
                return
        entry_widget.configure(border_color=("gray65", "gray25"))
        self.state_manager.set_keyword_setting(keyword, "cutoff_date", val)
        print(f"Set cutoff_date for {keyword} to {val}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x600")
        
        self._setup_icon()
        
        self.state_manager = StateManager()
        self.scraper = GettyScraper()
        self.is_checking = False
        self.stop_requested = False
        self.toaster = ToastNotifier() if ToastNotifier is not None else None
        self.logs_visible = True
        self.last_check_text = tk.StringVar(value="Last check: Never")
        self.new_images_text = tk.StringVar(value="New images: 0")
        self.status_text = tk.StringVar(value="Status: Idle")
        self.save_location_text = tk.StringVar(value=f"Save folder: {self._display_download_dir()}")

        self._setup_layout()
        
        # Redirect stdout/stderr
        self.redirector = RedirectText(self.log_textbox)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        if TOAST_IMPORT_ERROR is not None:
            self.log(f"Windows notifications unavailable: {TOAST_IMPORT_ERROR}")

    def _setup_icon(self):
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
            ico_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            img = Image.open(icon_path)
            if not os.path.exists(ico_path):
                img.save(ico_path, format='ICO')
            self.after(200, lambda: self.apply_window_icon(ico_path, img))
        except Exception as e:
            print(f"Could not load icon: {e}")

    def _setup_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.toolbar = ctk.CTkFrame(self, corner_radius=0)
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.toolbar, text=APP_NAME, font=("Arial", 16, "bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkLabel(self.toolbar, textvariable=self.status_text, text_color="gray").grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.toolbar_logs_btn = ctk.CTkButton(self.toolbar, text="Hide Logs", width=90, command=self.toggle_logs)
        self.toolbar_logs_btn.grid(row=0, column=2, padx=(0, 8), pady=10)
        ctk.CTkButton(self.toolbar, text="Settings", width=90, command=self.show_settings).grid(row=0, column=3, padx=(0, 8), pady=10)
        ctk.CTkButton(self.toolbar, text="About", width=80, command=self.show_about).grid(row=0, column=4, padx=(0, 20), pady=10)
        
        self.main_container = ctk.CTkFrame(self, corner_radius=0)
        self.main_container.grid(row=1, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=3)
        self.main_container.grid_columnconfigure(1, weight=1)

        self.keywords_view = KeywordsFrame(self.main_container, self.state_manager, self.check_single_keyword, self.stop_check)
        self.keywords_view.grid(row=0, column=0, sticky="nsew")

        self.log_frame = ctk.CTkFrame(self.main_container, width=300, corner_radius=0)
        self.log_frame.grid(row=0, column=1, sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.log_frame, text="Application Logs", anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(10, 2))
        self.log_textbox = ctk.CTkTextbox(self.log_frame, font=("Consolas", 10), width=280)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.status_bar = ctk.CTkFrame(self, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.status_bar.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(self.status_bar, textvariable=self.last_check_text, anchor="w").grid(row=0, column=0, padx=20, pady=6, sticky="w")
        ctk.CTkLabel(self.status_bar, textvariable=self.new_images_text, anchor="w").grid(row=0, column=1, padx=20, pady=6, sticky="w")
        ctk.CTkLabel(self.status_bar, textvariable=self.save_location_text, anchor="e").grid(row=0, column=2, padx=20, pady=6, sticky="e")




    # Removed UI methods: show_results, show_keywords, add_result_to_ui, open_full_size, _fetch_and_open_full, clear_results

    def apply_window_icon(self, ico_path, pil_img):
        try:
             # Set iconbitmap (standard for Windows title bars)
             self.iconbitmap(ico_path)
             
             # Also set iconphoto for taskbar/other windows as backup
             icon_img = ImageTk.PhotoImage(pil_img)
             self.iconphoto(False, icon_img) # False = apply to this window, True = apply to all future
        except Exception as e:
             print(f"Error applying icon: {e}")

    def check_single_keyword(self, keyword):
        self.start_check_thread(check_all=(keyword is None), single_target=keyword)

    def start_check_thread(self, check_all=True, single_target=None):
        if self.is_checking:
            print("Already checking...")
            return
        
        target_kw = single_target if not check_all else None
        if not check_all and not target_kw:
            return

        self.is_checking = True
        self.stop_requested = False
        self.status_text.set("Status: Checking")
        self.keywords_view.check_all_button.configure(state="disabled")
        self.keywords_view.stop_button.configure(state="normal")
        
        threading.Thread(target=self.run_check, args=(target_kw,), daemon=True).start()

    def stop_check(self):
        if self.is_checking:
            self.stop_requested = True
            self.status_text.set("Status: Stopping")
            self.log("Stopping check process...")
            self.keywords_view.stop_button.configure(state="disabled")

    def log(self, message):
         print(message)

    def run_check(self, single_keyword=None):
        self.log(f"Checking {'ALL' if not single_keyword else single_keyword}...")
        keywords = [single_keyword] if single_keyword else self.state_manager.get_keywords()
        total_new = 0

        for kw in keywords:
            if self.stop_requested:
                self.log("Check stopped by user.")
                break
            
            total_new += self._process_keyword(kw)
        
        self.is_checking = False
        self.stop_requested = False
        self.keywords_view.check_all_button.configure(state="normal")
        self.keywords_view.stop_button.configure(state="disabled")
        self.status_text.set("Status: Idle")
        self.last_check_text.set(f"Last check: {datetime.datetime.now().strftime('%d.%m %H:%M')}")
        self.new_images_text.set(f"New images: {total_new}")
        self.log(f"Check complete. {total_new} new images found.")

    def _process_keyword(self, kw):
        self.log(f"Scraping: {kw}...")
        settings = self.state_manager.get_keyword_settings(kw)
        cutoff_date_str = settings.get("cutoff_date", "").strip()
        last_id = settings.get("last_id")
        
        cutoff_date = self._parse_date(cutoff_date_str)
        found_images = self.scraper.check_keyword(kw, cutoff_date, should_stop=lambda: self.stop_requested)
        
        new_images = []
        seen_for_kw = self.state_manager.get_seen_images(kw)
        max_date_found = cutoff_date 

        for img in found_images:
            img_date = self._parse_iso_date(img.get('date'))
            if img_date and (max_date_found is None or img_date > max_date_found):
                max_date_found = img_date
            
            if (last_id and img['id'] == last_id) or (img['id'] in seen_for_kw):
                continue

            if cutoff_date and img_date and img_date < cutoff_date:
                continue 
            
            new_images.append(img)

        if new_images:
            self.state_manager.update_seen_images(kw, [img['id'] for img in new_images])
            
            # Update settings
            newest_id = new_images[0]['id']
            updated = False
            if max_date_found:
                new_cutoff = max_date_found.strftime("%d.%m.%Y")
                if new_cutoff != cutoff_date_str:
                    self.state_manager.set_keyword_setting(kw, "cutoff_date", new_cutoff)
                    updated = True
            if newest_id != last_id:
                self.state_manager.set_keyword_setting(kw, "last_id", newest_id)
                updated = True
            
            if updated:
                self.after(0, self.keywords_view.refresh_keywords)

        # Update Last Checked
        self.state_manager.set_keyword_setting(kw, "last_checked", datetime.datetime.now().strftime("%d.%m %H:%M"))
        self.state_manager.set_keyword_setting(kw, "last_new_count", len(new_images))
        self.after(0, self.keywords_view.refresh_keywords)
        
        if new_images:
            self._batch_download(kw, new_images)
            self.notify_new_images(kw, len(new_images))
        
        return len(new_images)

    def notify_new_images(self, keyword, count):
        if self.toaster is None:
            return
        if self.state_manager.get_setting("notifications_enabled") is False:
            self.log("Windows notification skipped because notifications are disabled.")
            return

        title = "Getty Images Watcher"
        plural = "image" if count == 1 else "images"
        message = f"{count} new {plural} found for {keyword}"
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if not os.path.exists(icon_path):
            self.log("Windows notification icon not found; showing notification without an icon.")
            icon_path = None

        try:
            shown = self.toaster.show_toast(
                title,
                message,
                icon_path=icon_path,
                duration=8,
                threaded=True,
            )
            if not shown:
                self.log("Windows notification skipped because another notification is still active.")
        except Exception as e:
            self.log(f"Windows notification failed: {e}")

    def _batch_download(self, kw, images):
        self.log(f"Batch downloading {len(images)} images for {kw}...")
        url_map = self.scraper.get_full_res_urls_batch(
            [img['url'] for img in images],
            should_stop=lambda: self.stop_requested,
        )
        
        for i, img in enumerate(images):
            if self.stop_requested:
                break
            full_url = url_map.get(img['url'])
            if full_url:
                self.process_download_with_url(kw, img, full_url, i+1, len(images))
            else:
                self.log(f"Failed to resolve URL for {img['id']}")

    def _parse_date(self, date_str):
        if not date_str: return None
        try:
            return datetime.datetime.strptime(date_str, "%d.%m.%Y")
        except Exception:
            return None

    def _parse_iso_date(self, date_str):
        if not date_str: return None
        try:
            return datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return None

    def toggle_logs(self):
        if self.logs_visible:
            self.log_frame.grid_remove()
            self.main_container.grid_columnconfigure(1, weight=0)
            self.toolbar_logs_btn.configure(text="Show Logs")
            self.logs_visible = False
        else:
            self.log_frame.grid()
            self.main_container.grid_columnconfigure(1, weight=1)
            self.toolbar_logs_btn.configure(text="Hide Logs")
            self.logs_visible = True

    def show_settings(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("620x270")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dialog, text="Settings", font=("Arial", 18, "bold")).grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 10), sticky="w")
        ctk.CTkLabel(dialog, text="Download location", anchor="w").grid(row=1, column=0, columnspan=3, padx=20, pady=(5, 4), sticky="w")

        path_var = tk.StringVar(value=self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR)
        notifications_var = tk.BooleanVar(value=self.state_manager.get_setting("notifications_enabled") is not False)
        path_entry = ctk.CTkEntry(dialog, textvariable=path_var)
        path_entry.grid(row=2, column=0, padx=(20, 8), pady=4, sticky="ew")

        def browse():
            chosen = filedialog.askdirectory(parent=dialog, initialdir=self._absolute_download_dir(path_var.get()))
            if chosen:
                path_var.set(chosen)

        ctk.CTkButton(dialog, text="Browse...", width=90, command=browse).grid(row=2, column=1, padx=(0, 8), pady=4)
        ctk.CTkButton(dialog, text="Open Folder", width=110, command=lambda: self.open_download_folder(path_var.get())).grid(row=2, column=2, padx=(0, 20), pady=4)

        feedback = ctk.CTkLabel(dialog, text="", anchor="w", text_color="gray")
        feedback.grid(row=3, column=0, columnspan=3, padx=20, pady=(4, 10), sticky="w")

        notifications_checkbox = ctk.CTkCheckBox(
            dialog,
            text="Show system notifications when new images are found",
            variable=notifications_var,
        )
        notifications_checkbox.grid(row=4, column=0, columnspan=3, padx=20, pady=(4, 10), sticky="w")

        def reset_default():
            path_var.set(DEFAULT_DOWNLOAD_DIR)
            feedback.configure(text="Default download folder selected.")

        def save():
            selected = path_var.get().strip() or DEFAULT_DOWNLOAD_DIR
            try:
                os.makedirs(self._absolute_download_dir(selected), exist_ok=True)
            except Exception as e:
                feedback.configure(text=f"Could not use this folder: {e}", text_color="red")
                return

            self.state_manager.set_setting("download_dir", selected)
            self.state_manager.set_setting("notifications_enabled", bool(notifications_var.get()))
            self._refresh_save_location()
            feedback.configure(text="Settings saved.", text_color="green")

        ctk.CTkButton(dialog, text="Reset to Default", width=130, command=reset_default).grid(row=5, column=0, padx=20, pady=(10, 20), sticky="w")
        ctk.CTkButton(dialog, text="Save", width=90, command=save).grid(row=5, column=1, padx=(0, 8), pady=(10, 20), sticky="e")
        ctk.CTkButton(dialog, text="Close", width=90, command=dialog.destroy).grid(row=5, column=2, padx=(0, 20), pady=(10, 20), sticky="e")

    def show_about(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("About")
        dialog.geometry("460x300")
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dialog, text=APP_NAME, font=("Arial", 20, "bold")).grid(row=0, column=0, padx=24, pady=(24, 4), sticky="w")
        ctk.CTkLabel(dialog, text=f"Version {APP_VERSION}", text_color="gray").grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")
        ctk.CTkLabel(dialog, text=APP_DESCRIPTION, wraplength=400, justify="left").grid(row=2, column=0, padx=24, pady=4, sticky="w")
        ctk.CTkLabel(dialog, text="License: MIT", text_color="gray").grid(row=3, column=0, padx=24, pady=(12, 4), sticky="w")
        ctk.CTkLabel(dialog, text=f"Python {sys.version.split()[0]}", text_color="gray").grid(row=4, column=0, padx=24, pady=4, sticky="w")

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.grid(row=5, column=0, padx=24, pady=(20, 24), sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(button_frame, text="Open README", command=self.open_readme).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(button_frame, text="Close", width=90, command=dialog.destroy).grid(row=0, column=1, sticky="e")

    def open_readme(self):
        readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "README.md"))
        if os.path.exists(readme_path):
            webbrowser.open(readme_path)
        else:
            messagebox.showinfo(APP_NAME, "README.md was not found.")

    def open_download_folder(self, path=None):
        target = self._absolute_download_dir(path or self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR)
        try:
            os.makedirs(target, exist_ok=True)
            webbrowser.open(target)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open folder:\n{e}")

    def _absolute_download_dir(self, path):
        path = path.strip() if path else DEFAULT_DOWNLOAD_DIR
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), path))

    def _display_download_dir(self):
        return self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR

    def _refresh_save_location(self):
        self.save_location_text.set(f"Save folder: {self._display_download_dir()}")

    def process_download_with_url(self, keyword, img_data, full_url, index=None, total=None):
        filename, download_dir = self._get_download_path(keyword, img_data)
        filepath = os.path.join(download_dir, filename)
        
        if os.path.exists(filepath):
            self.log(f"File already exists: {filename}. Skipping.")
            return

        if self._download_file(full_url, filepath):
            msg = f"Saved [{index}/{total}]: {filename}" if index else f"Saved: {filename}"
            self.log(msg)

    def _get_download_path(self, keyword, img_data):
        safe_kw = re.sub(r'[^\w\s]', '', keyword).strip()
        base_dir = self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR
        download_dir = os.path.join(self._absolute_download_dir(base_dir), safe_kw)
        os.makedirs(download_dir, exist_ok=True)
        
        date_str = img_data.get('date', '')
        formatted_date = "0000.00.00"
        if date_str:
            try:
                dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                formatted_date = dt.strftime("%Y.%m.%d")
            except Exception:
                pass
        
        safe_title = re.sub(r'[^\w\s]', '', img_data['title']).strip()
        img_id = img_data['id']
        ext = ".jpg"
        
        fixed_len = len(formatted_date) + 2 + len(img_id) + len(ext)
        max_title_len = 250 - fixed_len
        if len(safe_title) > max_title_len:
            safe_title = safe_title[:max_title_len].strip()
            
        filename = f"{formatted_date} {safe_title} {img_id}{ext}"
        return filename, download_dir

    def _download_file(self, url, filepath):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Referer": "https://www.gettyimages.com/"
        }
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 429:
                self.log("Rate limit hit! Pausing for 60s...")
                time.sleep(60)
                resp = requests.get(url, headers=headers)
            
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return True
            self.log(f"Download failed: HTTP {resp.status_code}")
        except Exception as e:
            self.log(f"Download Error: {e}")
        return False

    def apply_window_icon(self, ico_path, pil_img):
        try:
             self.iconbitmap(ico_path)
             icon_img = ImageTk.PhotoImage(pil_img)
             self.iconphoto(False, icon_img)
        except Exception as e:
             print(f"Error applying icon: {e}")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()

