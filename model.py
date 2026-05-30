import json
import os
import threading

DATA_FILE = "data.json"
MAX_HISTORY = 300 # Keep history to allow backfilling/skipping known images
DEFAULT_DOWNLOAD_DIR = "downloads"




class StateManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = self._load_data()
        self._seen_sets = {kw: set(images) for kw, images in self.data.get("seen_images", {}).items()}

    def _load_data(self):
        default_data = {
            "keywords": [], 
            "seen_images": {},
            "settings": {
                "auto_download": False,
                "cutoff_date": "", # format: YYYY-MM-DD
                "download_dir": DEFAULT_DOWNLOAD_DIR,
                "notifications_enabled": True
            }
        }
        if not os.path.exists(DATA_FILE):
            return default_data
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Migrate old data format if needed
                if "settings" not in data:
                    data["settings"] = default_data["settings"].copy()
                else:
                    for key, value in default_data["settings"].items():
                        data["settings"].setdefault(key, value)
                return data
        except Exception as e:
            print(f"Error loading data: {e}")
            return default_data

    def get_setting(self, key):
        return self.data.get("settings", {}).get(key)

    def set_setting(self, key, value):
        if "settings" not in self.data:
            self.data["settings"] = {}
        self.data["settings"][key] = value
        self.save_data()

    def get_keyword_settings(self, keyword):
        return self.data.setdefault("keyword_settings", {}).get(keyword, {})

    def set_keyword_setting(self, keyword, key, value):
        self.data.setdefault("keyword_settings", {}).setdefault(keyword, {})[key] = value
        self.save_data()

    def save_data(self):
        with self.lock:
            try:
                self._prune_seen_images()
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving data: {e}")

    def _prune_seen_images(self):
        active_keywords = set(self.data.get("keywords", []))
        seen_images = self.data.setdefault("seen_images", {})

        for keyword in list(seen_images):
            if active_keywords and keyword not in active_keywords:
                del seen_images[keyword]
                self._seen_sets.pop(keyword, None)
                continue

            seen = seen_images[keyword]
            if isinstance(seen, list) and len(seen) > MAX_HISTORY:
                seen_images[keyword] = seen[-MAX_HISTORY:]
                self._seen_sets[keyword] = set(seen_images[keyword])

    def get_keywords(self):
        return self.data.get("keywords", [])

    def add_keyword(self, keyword):
        if keyword not in self.data["keywords"]:
            self.data["keywords"].append(keyword)
            self.data.setdefault("seen_images", {}).setdefault(keyword, [])
            self._seen_sets.setdefault(keyword, set())
            self.save_data()

    def remove_keyword(self, keyword):
        if keyword in self.data["keywords"]:
            self.data["keywords"].remove(keyword)
            self._seen_sets.pop(keyword, None)
            self.save_data()

    def get_seen_images(self, keyword):
        return self.data.setdefault("seen_images", {}).get(keyword, [])

    def mark_image_seen(self, keyword, image_id):
        seen = self.data.setdefault("seen_images", {}).setdefault(keyword, [])
        if keyword not in self._seen_sets:
            self._seen_sets[keyword] = set(seen)
        seen_set = self._seen_sets[keyword]
        if image_id not in seen_set:
            seen.append(image_id)
            seen_set.add(image_id)
            self.save_data()
            
    def update_seen_images(self, keyword, new_ids):
        """Bulk update to avoid too many writes"""
        seen = self.data.setdefault("seen_images", {}).setdefault(keyword, [])
        if keyword not in self._seen_sets:
            self._seen_sets[keyword] = set(seen)
        seen_set = self._seen_sets[keyword]
        changed = False
        
        for img_id in new_ids:
            if img_id not in seen_set:
                seen.append(img_id)
                seen_set.add(img_id)
                changed = True
        
        if changed:
            if len(seen) > MAX_HISTORY:
                self.data["seen_images"][keyword] = seen[-MAX_HISTORY:]
                self._seen_sets[keyword] = set(self.data["seen_images"][keyword])
            self.save_data()


