import customtkinter as ctk
import threading
import sys
import os
import webbrowser
import time
import datetime
import requests
import re
from tkinter import messagebox
from PIL import Image, ImageTk
try:
    from win10toast import ToastNotifier
except Exception as e:
    ToastNotifier = None
    TOAST_IMPORT_ERROR = e
else:
    TOAST_IMPORT_ERROR = None
from model import StateManager
from scraper import GettyScraper

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
    def __init__(self, parent, state_manager, check_callback, stop_callback, toggle_logs_callback):
        super().__init__(parent)
        self.state_manager = state_manager
        self.check_callback = check_callback
        self.stop_callback = stop_callback
        self.toggle_logs_callback = toggle_logs_callback
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)
        
        fonts = ("Arial", 12, "bold")
        ctk.CTkLabel(self.header_frame, text="Keyword", font=fonts, anchor="w").grid(row=0, column=0, sticky="ew", padx=5)
        ctk.CTkLabel(self.header_frame, text="Last Check", font=fonts, width=120, anchor="w").grid(row=0, column=1, padx=5)
        ctk.CTkLabel(self.header_frame, text="From Date", font=fonts, width=100, anchor="w").grid(row=0, column=2, padx=5)
        ctk.CTkLabel(self.header_frame, text="Action", font=fonts, width=80, anchor="center").grid(row=0, column=3, padx=5)
        ctk.CTkLabel(self.header_frame, text="", width=40).grid(row=0, column=4, padx=5)

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
        self.stop_button.grid(row=0, column=3, padx=(0, 20))

        self.toggle_logs_btn = ctk.CTkButton(self.controls_frame, text="Logs >", width=60, command=self.toggle_logs_callback)
        self.toggle_logs_btn.grid(row=0, column=4)

        self.keyword_widgets = {}
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

        for kw in self.state_manager.get_keywords():
            frame = ctk.CTkFrame(self.keyword_scroll)
            frame.pack(fill="x", pady=2)
            frame.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(frame, text=kw, anchor="w", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=5)
            
            settings = self.state_manager.get_keyword_settings(kw)
            last_checked = settings.get("last_checked", "Never")
            ctk.CTkLabel(frame, text=last_checked, width=120, anchor="w", text_color="gray").grid(row=0, column=1, padx=5)
            
            cutoff = settings.get("cutoff_date", "")
            date_ent = ctk.CTkEntry(frame, width=100, placeholder_text="DD.MM.YYYY")
            date_ent.insert(0, cutoff)
            date_ent.grid(row=0, column=2, padx=5)
            
            date_ent.bind("<FocusOut>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))
            date_ent.bind("<Return>", lambda e, k=kw, ent=date_ent: self.save_date(k, ent))

            ctk.CTkButton(frame, text="Check", width=80, command=lambda k=kw: self.check_callback(k)).grid(row=0, column=3, padx=5)
            ctk.CTkButton(frame, text="X", width=30, fg_color="red", hover_color="darkred", command=lambda k=kw: self.remove_keyword(k)).grid(row=0, column=4, padx=5)

            self.keyword_widgets[kw] = frame

    def save_date(self, keyword, entry_widget):
        val = entry_widget.get().strip()
        self.state_manager.set_keyword_setting(keyword, "cutoff_date", val)
        print(f"Set cutoff_date for {keyword} to {val}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Getty Images Watcher")
        self.geometry("1100x600")
        
        self._setup_icon()
        
        self.state_manager = StateManager()
        self.scraper = GettyScraper()
        self.is_checking = False
        self.stop_requested = False
        self.toaster = ToastNotifier() if ToastNotifier is not None else None
        self.logs_visible = True

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
        self.grid_rowconfigure(0, weight=1)
        
        self.main_container = ctk.CTkFrame(self, corner_radius=0)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=3)
        self.main_container.grid_columnconfigure(1, weight=1)

        self.keywords_view = KeywordsFrame(self.main_container, self.state_manager, self.check_single_keyword, self.stop_check, self.toggle_logs)
        self.keywords_view.grid(row=0, column=0, sticky="nsew")

        self.log_frame = ctk.CTkFrame(self.main_container, width=300, corner_radius=0)
        self.log_frame.grid(row=0, column=1, sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.log_frame, text="Application Logs", anchor="w", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(10, 2))
        self.log_textbox = ctk.CTkTextbox(self.log_frame, font=("Consolas", 10), width=280)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)




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
        self.keywords_view.check_all_button.configure(state="disabled")
        self.keywords_view.stop_button.configure(state="normal")
        
        threading.Thread(target=self.run_check, args=(target_kw,), daemon=True).start()

    def stop_check(self):
        if self.is_checking:
            self.stop_requested = True
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
        
        if new_images:
            self._batch_download(kw, new_images)
            self.notify_new_images(kw, len(new_images))
        
        return len(new_images)

    def notify_new_images(self, keyword, count):
        if self.toaster is None:
            return

        title = "Getty Images Watcher"
        plural = "image" if count == 1 else "images"
        message = f"{count} new {plural} found for {keyword}"
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if not os.path.exists(icon_path):
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
        url_map = self.scraper.get_full_res_urls_batch([img['url'] for img in images])
        
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
            self.keywords_view.toggle_logs_btn.configure(text="< Logs")
            self.logs_visible = False
        else:
            self.log_frame.grid()
            self.main_container.grid_columnconfigure(1, weight=1)
            self.keywords_view.toggle_logs_btn.configure(text="Logs >")
            self.logs_visible = True

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
        download_dir = os.path.join("downloads", safe_kw)
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

