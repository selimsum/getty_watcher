import customtkinter as ctk
import threading
import sys
import os
import time
import datetime
import requests
import re
import tkinter as tk
from tkinter import filedialog
import tkinter.messagebox
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
APP_VERSION = "2.2"
APP_DESCRIPTION = "Monitors Getty Images keywords and downloads newly discovered images and videos."
SIDE_PANE_WIDTH = 340

SAFE_WORD_REGEX = re.compile(r'[^\w\s]')
SAFE_ID_REGEX = re.compile(r'[^\w\s-]')

# Fix for Playwright in PyInstaller: Force use of local browsers
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")

try:
    import ctypes
    # Change ID to force refresh
    myappid = 'gettywatcher.v2.2' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

class RedirectText:
    def __init__(self, text_widget):
        self.output = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def write(self, string):
        if not string:
            return
        try:
            self.output.after(0, self._append, string)
        except Exception:
            pass
             
        if self.original_stdout:
            self.original_stdout.write(string)
             
    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()

    def _append(self, string):
        try:
            self.output.insert("end", string)
            self.output.see("end")
        except Exception:
            pass

class KeywordsFrame(ctk.CTkFrame):
    def __init__(self, parent, state_manager, check_callback, stop_callback):
        super().__init__(parent)
        self.state_manager = state_manager
        self.check_callback = check_callback
        self.stop_callback = stop_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header (Simple Title)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=(20, 20), pady=(12, 8), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="Watched Keywords", 
            font=("Arial", 16, "bold"), 
            anchor="w"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        # 2. Scrollable List (Cards Container)
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
        for row in self.keyword_widgets.values():
            for widget in row["widgets"]:
                try:
                    widget.destroy()
                except Exception:
                    pass
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
            self.empty_label.grid(row=0, column=0, sticky="ew", pady=30)
            return

        for row_index, kw in enumerate(keywords):
            self._create_keyword_row(kw, row_index)

    def _create_keyword_row(self, kw, row_index):
        # Create a container card for the keyword
        card = ctk.CTkFrame(
            self.keyword_scroll,
            corner_radius=6,
            border_width=1,
            border_color=("gray85", "gray25")
        )
        card.grid(row=row_index, column=0, sticky="ew", padx=5, pady=4)
        
        # Configure layout columns inside the card
        # Col 0: Keyword label (weight=1, sticky="w")
        # Col 1: Status label (weight=0, sticky="w", padx=(10, 20))
        # Col 2: Date frame (weight=0, sticky="e", padx=(10, 15))
        # Col 3: Media type dropdown (weight=0, sticky="e")
        # Col 4: Check button (weight=0, sticky="e", padx=(0, 6))
        # Col 5: Delete button (weight=0, sticky="e", padx=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)
        card.grid_columnconfigure(2, weight=0)
        card.grid_columnconfigure(3, weight=0)
        card.grid_columnconfigure(4, weight=0)
        card.grid_columnconfigure(5, weight=0)
        
        # Keyword Label
        keyword_label = ctk.CTkLabel(
            card,
            text=kw,
            anchor="w",
            font=("Arial", 13, "bold"),
            justify="left"
        )
        keyword_label.grid(row=0, column=0, sticky="ew", padx=(15, 10), pady=8)
        
        # Status Label
        settings = self.state_manager.get_keyword_settings(kw)
        last_checked = settings.get("last_checked", "Never")
        last_new_count = settings.get("last_new_count", 0)
        
        status_text = f"Last checked: {last_checked}  •  {last_new_count} new"
        status_label = ctk.CTkLabel(
            card,
            text=status_text,
            anchor="w",
            text_color="gray",
            font=("Arial", 11)
        )
        status_label.grid(row=0, column=1, sticky="w", padx=(10, 20), pady=8)
        
        # Date Frame (Label + Entry)
        date_frame = ctk.CTkFrame(card, fg_color="transparent")
        date_frame.grid(row=0, column=2, sticky="e", padx=(10, 15), pady=8)
        date_frame.grid_columnconfigure(0, weight=0)
        date_frame.grid_columnconfigure(1, weight=0)
        
        date_label = ctk.CTkLabel(
            date_frame,
            text="From Date:",
            font=("Arial", 11, "bold"),
            anchor="e"
        )
        date_label.grid(row=0, column=0, sticky="e", padx=(0, 6))
        
        cutoff = settings.get("cutoff_date", "")
        date_ent = ctk.CTkEntry(
            date_frame,
            width=100,
            placeholder_text="DD.MM.YYYY",
            height=28
        )
        date_ent.insert(0, cutoff)
        date_ent.grid(row=0, column=1, sticky="w")
        
        date_ent.bind("<FocusOut>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))
        date_ent.bind("<Return>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))
        
        # Media Type Dropdown
        current_media = settings.get("media_type", "images")
        media_type_dropdown = ctk.CTkOptionMenu(
            card,
            values=["Images", "Videos", "Both"],
            width=90,
            height=28,
            font=("Arial", 11),
            command=lambda val, k=kw: self.save_media_type(k, val)
        )
        media_type_dropdown.set(current_media.capitalize())
        media_type_dropdown.grid(row=0, column=3, sticky="e", padx=(0, 10), pady=8)
        
        # Action Buttons
        check_button = ctk.CTkButton(
            card,
            text="Check",
            width=70,
            height=28,
            command=lambda k=kw: self.check_callback(k)
        )
        check_button.grid(row=0, column=4, sticky="e", padx=(0, 6), pady=8)
        
        delete_button = ctk.CTkButton(
            card,
            text="Delete",
            width=70,
            height=28,
            fg_color="red",
            hover_color="darkred",
            command=lambda k=kw: self.remove_keyword(k)
        )
        delete_button.grid(row=0, column=5, sticky="e", padx=(0, 15), pady=8)
        
        # Store widgets for updates/cleanup
        # Since 'card' is the parent frame containing all these widgets, destroying it clears everything.
        self.keyword_widgets[kw] = {
            "widgets": [card],
            "status_label": status_label,
            "cutoff_date": date_ent,
        }

    def update_keyword_row(self, keyword):
        row = self.keyword_widgets.get(keyword)
        if row is None:
            self.refresh_keywords()
            return

        settings = self.state_manager.get_keyword_settings(keyword)
        last_checked = settings.get("last_checked", "Never")
        last_new_count = settings.get("last_new_count", 0)
        
        status_text = f"Last checked: {last_checked}  •  {last_new_count} new"
        row["status_label"].configure(text=status_text)

        cutoff = settings.get("cutoff_date", "")
        cutoff_entry = row["cutoff_date"]
        if cutoff_entry.focus_get() != cutoff_entry and cutoff_entry.get() != cutoff:
            cutoff_entry.delete(0, "end")
            cutoff_entry.insert(0, cutoff)

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

    def save_media_type(self, keyword, value):
        media_type = value.lower()
        self.state_manager.set_keyword_setting(keyword, "media_type", media_type)
        print(f"Set media_type for {keyword} to {media_type}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x600")
        
        self._setup_icon()
        
        self.state_manager = StateManager()
        self.scraper = GettyScraper(use_cookies_fn=lambda: self.state_manager.get_setting("use_firefox_cookies") is not False)
        self.is_checking = False
        self.stop_requested = False
        self.toaster = ToastNotifier() if ToastNotifier is not None else None
        self.logs_visible = True
        self.side_pane_visible = True
        self.active_side_view = "logs"
        self.last_check_text = tk.StringVar(value="Last check: Never")
        self.new_images_text = tk.StringVar(value="New images: 0")
        self.status_text = tk.StringVar(value="Status: Idle")
        self.save_location_text = tk.StringVar(value=f"Save folder: {self._display_download_dir()}")
        self.settings_path_var = tk.StringVar(value=self._display_download_dir())
        self.settings_notifications_var = tk.BooleanVar(value=self.state_manager.get_setting("notifications_enabled") is not False)
        self.settings_firefox_cookies_var = tk.BooleanVar(value=self.state_manager.get_setting("use_firefox_cookies") is not False)
        self.settings_feedback_text = tk.StringVar(value="")

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
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(1, weight=0, minsize=SIDE_PANE_WIDTH)

        self.keywords_view = KeywordsFrame(self.main_container, self.state_manager, self.check_single_keyword, self.stop_check)
        self.keywords_view.grid(row=0, column=0, sticky="nsew")

        self.side_pane = ctk.CTkFrame(self.main_container, width=SIDE_PANE_WIDTH, corner_radius=0)
        self.side_pane.grid_propagate(False)
        self.side_pane.grid(row=0, column=1, sticky="nsew")
        self.side_pane.grid_columnconfigure(0, weight=1)
        self.side_pane.grid_rowconfigure(0, weight=1)
        
        self.log_view = ctk.CTkFrame(self.side_pane, corner_radius=0)
        self.log_view.grid_columnconfigure(0, weight=1)
        self.log_view.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.log_view, text="Application Logs", anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        self.log_textbox = ctk.CTkTextbox(self.log_view, font=("Consolas", 10), width=SIDE_PANE_WIDTH - 20)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        self.settings_view = self._build_settings_view(self.side_pane)
        self.about_view = self._build_about_view(self.side_pane)
        self._show_side_view("logs")

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
        finished_at = datetime.datetime.now().strftime("%d.%m %H:%M")
        self.after(0, lambda count=total_new, timestamp=finished_at: self._finish_check_ui(count, timestamp))
        self.log(f"Check complete. {total_new} new items found.")

    def _finish_check_ui(self, total_new, finished_at):
        self.keywords_view.check_all_button.configure(state="normal")
        self.keywords_view.stop_button.configure(state="disabled")
        self.status_text.set("Status: Idle")
        self.last_check_text.set(f"Last check: {finished_at}")
        self.new_images_text.set(f"New images: {total_new}")

    def _process_keyword(self, kw):
        self.log(f"Scraping: {kw}...")
        settings = self.state_manager.get_keyword_settings(kw)
        cutoff_date_str = settings.get("cutoff_date", "").strip()
        last_id = settings.get("last_id")
        media_type = settings.get("media_type", "images")
        
        cutoff_date = self._parse_date(cutoff_date_str)
        found_images = self.scraper.check_keyword(kw, cutoff_date, should_stop=lambda: self.stop_requested, media_type=media_type)
        
        new_images = []
        seen_for_kw = set(self.state_manager.get_seen_images(kw))
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
            if max_date_found:
                new_cutoff = max_date_found.strftime("%d.%m.%Y")
                if new_cutoff != cutoff_date_str:
                    self.state_manager.set_keyword_setting(kw, "cutoff_date", new_cutoff)
            if newest_id != last_id:
                self.state_manager.set_keyword_setting(kw, "last_id", newest_id)

        # Update Last Checked
        self.state_manager.set_keyword_setting(kw, "last_checked", datetime.datetime.now().strftime("%d.%m %H:%M"))
        self.state_manager.set_keyword_setting(kw, "last_new_count", len(new_images))
        self.after(0, lambda keyword=kw: self.keywords_view.update_keyword_row(keyword))
        
        if new_images:
            downloaded_count = self._batch_download(kw, new_images)
            if downloaded_count:
                self.notify_download_complete(kw, downloaded_count)
        
        return len(new_images)

    def notify_download_complete(self, keyword, count):
        if self.toaster is None:
            return
        if self.state_manager.get_setting("notifications_enabled") is False:
            self.log("Windows notification skipped because notifications are disabled.")
            return

        self.after(0, lambda: self._show_download_toast(keyword, count))

    def _show_download_toast(self, keyword, count):
        title = "Getty Images Watcher"
        settings = self.state_manager.get_keyword_settings(keyword)
        media_type = settings.get("media_type", "images")
        if media_type == "videos":
            plural = "video" if count == 1 else "videos"
        else:
            plural = "image" if count == 1 else "images"
        message = f"{count} {plural} downloaded for {keyword}"
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
        self.log(f"Batch downloading {len(images)} items for {kw}...")
        settings = self.state_manager.get_keyword_settings(kw)
        media_type = settings.get("media_type", "images")
        url_map = self.scraper.get_full_res_urls_batch(
            [img['url'] for img in images],
            should_stop=lambda: self.stop_requested,
            media_type=media_type,
        )
        downloaded_count = 0
        
        # Calculate download directory once per keyword batch
        safe_kw = SAFE_WORD_REGEX.sub('', kw).strip()
        base_dir = self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR
        download_dir = os.path.join(self._absolute_download_dir(base_dir), safe_kw)
        os.makedirs(download_dir, exist_ok=True)

        for i, img in enumerate(images):
            if self.stop_requested:
                break
            full_url = url_map.get(img['url'])
            if full_url:
                if self.process_download_with_url(kw, img, full_url, i+1, len(images), download_dir=download_dir, media_type=media_type):
                    downloaded_count += 1
            else:
                self.log(f"Failed to resolve URL for {img['id']}")

        self.log(f"Download complete for {kw}. {downloaded_count} files saved.")
        return downloaded_count

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

    def _build_settings_view(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Settings", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=16, pady=(18, 10), sticky="w")
        ctk.CTkLabel(frame, text="Download location", anchor="w").grid(row=1, column=0, padx=16, pady=(8, 4), sticky="w")

        path_entry = ctk.CTkEntry(frame, textvariable=self.settings_path_var)
        path_entry.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        path_buttons = ctk.CTkFrame(frame, fg_color="transparent")
        path_buttons.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="ew")
        path_buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(path_buttons, text="Browse...", command=self.browse_download_folder).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(path_buttons, text="Open Folder", command=lambda: self.open_download_folder(self.settings_path_var.get())).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        ctk.CTkCheckBox(
            frame,
            text="Show system notifications",
            variable=self.settings_notifications_var,
        ).grid(row=4, column=0, padx=16, pady=(4, 6), sticky="w")

        ctk.CTkCheckBox(
            frame,
            text="Use Firefox cookies (bypass page limit)",
            variable=self.settings_firefox_cookies_var,
        ).grid(row=5, column=0, padx=16, pady=(0, 12), sticky="w")

        ctk.CTkLabel(frame, textvariable=self.settings_feedback_text, anchor="w", text_color="gray", wraplength=SIDE_PANE_WIDTH - 40).grid(row=6, column=0, padx=16, pady=(0, 12), sticky="ew")

        action_buttons = ctk.CTkFrame(frame, fg_color="transparent")
        action_buttons.grid(row=7, column=0, padx=16, pady=(4, 18), sticky="ew")
        action_buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(action_buttons, text="Reset", command=self.reset_settings_defaults).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(action_buttons, text="Save", command=self.save_settings).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        return frame

    def _build_about_view(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=0)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="About", font=("Arial", 18, "bold")).grid(row=0, column=0, padx=16, pady=(18, 12), sticky="w")
        ctk.CTkLabel(frame, text=APP_NAME, font=("Arial", 16, "bold")).grid(row=1, column=0, padx=16, pady=(4, 2), sticky="w")
        ctk.CTkLabel(frame, text=f"Version {APP_VERSION}", text_color="gray").grid(row=2, column=0, padx=16, pady=(0, 12), sticky="w")
        ctk.CTkLabel(frame, text=APP_DESCRIPTION, wraplength=SIDE_PANE_WIDTH - 40, justify="left").grid(row=3, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkLabel(frame, text="License: MIT", text_color="gray").grid(row=4, column=0, padx=16, pady=(14, 4), sticky="w")
        ctk.CTkLabel(frame, text=f"Python {sys.version.split()[0]}", text_color="gray").grid(row=5, column=0, padx=16, pady=4, sticky="w")

        return frame

    def _show_side_view(self, view_name):
        for view in (self.log_view, self.settings_view, self.about_view):
            view.grid_remove()

        views = {
            "logs": self.log_view,
            "settings": self.settings_view,
            "about": self.about_view,
        }
        views[view_name].grid(row=0, column=0, sticky="nsew")
        self.active_side_view = view_name
        self.side_pane.grid()
        self.main_container.grid_columnconfigure(1, weight=0, minsize=SIDE_PANE_WIDTH)
        self.side_pane_visible = True
        self.logs_visible = view_name == "logs"
        self.toolbar_logs_btn.configure(text="Hide Logs" if view_name == "logs" else "Show Logs")

    def browse_download_folder(self):
        chosen = filedialog.askdirectory(
            parent=self,
            initialdir=self._absolute_download_dir(self.settings_path_var.get()),
        )
        if chosen:
            self.settings_path_var.set(chosen)
            self.settings_feedback_text.set("")

    def reset_settings_defaults(self):
        self.settings_path_var.set(DEFAULT_DOWNLOAD_DIR)
        self.settings_feedback_text.set("Default download folder selected.")

    def save_settings(self):
        selected = self.settings_path_var.get().strip() or DEFAULT_DOWNLOAD_DIR
        try:
            os.makedirs(self._absolute_download_dir(selected), exist_ok=True)
        except Exception as e:
            self.settings_feedback_text.set(f"Could not use this folder: {e}")
            return

        self.state_manager.set_setting("download_dir", selected)
        self.state_manager.set_setting("notifications_enabled", bool(self.settings_notifications_var.get()))
        self.state_manager.set_setting("use_firefox_cookies", bool(self.settings_firefox_cookies_var.get()))
        self._refresh_save_location()
        self.settings_feedback_text.set("Settings saved.")

    def toggle_logs(self):
        if self.side_pane_visible and self.active_side_view == "logs":
            self.side_pane.grid_remove()
            self.main_container.grid_columnconfigure(1, weight=0, minsize=0)
            self.toolbar_logs_btn.configure(text="Show Logs")
            self.side_pane_visible = False
            self.logs_visible = False
        else:
            self._show_side_view("logs")
            self.side_pane.grid()
            self.main_container.grid_columnconfigure(1, weight=0, minsize=SIDE_PANE_WIDTH)
            self.toolbar_logs_btn.configure(text="Hide Logs")
            self.side_pane_visible = True
            self.logs_visible = True

    def show_settings(self):
        self.settings_path_var.set(self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR)
        self.settings_notifications_var.set(self.state_manager.get_setting("notifications_enabled") is not False)
        self.settings_firefox_cookies_var.set(self.state_manager.get_setting("use_firefox_cookies") is not False)
        self.settings_feedback_text.set("")
        self._show_side_view("settings")

    def show_about(self):
        self._show_side_view("about")

    def open_download_folder(self, path=None):
        import webbrowser
        target = self._absolute_download_dir(path or self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR)
        try:
            os.makedirs(target, exist_ok=True)
            webbrowser.open(target)
        except Exception as e:
            tkinter.messagebox.showerror(APP_NAME, f"Could not open folder:\n{e}")

    def _absolute_download_dir(self, path):
        path = path.strip() if path else DEFAULT_DOWNLOAD_DIR
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), path))

    def _display_download_dir(self):
        return self.state_manager.get_setting("download_dir") or DEFAULT_DOWNLOAD_DIR

    def _refresh_save_location(self):
        self.save_location_text.set(f"Save folder: {self._display_download_dir()}")

    def process_download_with_url(self, keyword, img_data, full_url, index=None, total=None, download_dir=None, media_type="images"):
        filename, computed_download_dir = self._get_download_path(keyword, img_data, download_dir=download_dir, media_type=media_type)
        filepath = os.path.join(computed_download_dir, filename)
        
        if os.path.exists(filepath):
            self.log(f"File already exists: {filename}. Skipping.")
            return False

        if self._download_file(full_url, filepath):
            msg = f"Saved [{index}/{total}]: {filename}" if index else f"Saved: {filename}"
            self.log(msg)
            return True

        return False

    def _get_download_path(self, keyword, img_data, download_dir=None, media_type="images"):
        if download_dir is None:
            safe_kw = SAFE_WORD_REGEX.sub('', keyword).strip()
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
        
        safe_title = SAFE_WORD_REGEX.sub('', img_data['title']).strip()
        img_id = SAFE_ID_REGEX.sub('', str(img_data['id'])).strip()
        ext = ".mp4" if media_type == "videos" else ".jpg"
        
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
            resp = requests.get(url, headers=headers, timeout=60, stream=True)
            if resp.status_code == 429:
                resp.close()
                self.log("Rate limit hit! Pausing for 60s...")
                time.sleep(60)
                resp = requests.get(url, headers=headers, timeout=60, stream=True)
            
            if resp.status_code == 200:
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            self.log(f"Download failed: HTTP {resp.status_code}")
        except Exception as e:
            self.log(f"Download Error: {e}")
        finally:
            if 'resp' in locals():
                resp.close()
        return False

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = App()
    app.mainloop()

