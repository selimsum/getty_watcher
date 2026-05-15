import json
import os
import threading

DATA_FILE = "data.json"
MAX_HISTORY = 10000 # Keep history to allow backfilling/skipping known images




class StateManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = self._load_data()

    def _load_data(self):
        default_data = {
            "keywords": [], 
            "seen_images": {},
            "settings": {
                "auto_download": False,
                "cutoff_date": "" # format: YYYY-MM-DD
            }
        }
        if not os.path.exists(DATA_FILE):
            return default_data
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Migrate old data format if needed
                if "settings" not in data:
                    data["settings"] = default_data["settings"]
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
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving data: {e}")

    def get_keywords(self):
        return self.data.get("keywords", [])

    def add_keyword(self, keyword):
        if keyword not in self.data["keywords"]:
            self.data["keywords"].append(keyword)
            self.data.setdefault("seen_images", {}).setdefault(keyword, [])
            self.save_data()

    def remove_keyword(self, keyword):
        if keyword in self.data["keywords"]:
            self.data["keywords"].remove(keyword)
            self.save_data()

    def get_seen_images(self, keyword):
        return self.data.setdefault("seen_images", {}).get(keyword, [])

    def mark_image_seen(self, keyword, image_id):
        seen = self.data.setdefault("seen_images", {}).setdefault(keyword, [])
        if image_id not in seen:
            seen.append(image_id)
            self.save_data()
            
    def update_seen_images(self, keyword, new_ids):
        """Bulk update to avoid too many writes"""
        seen = self.data.setdefault("seen_images", {}).setdefault(keyword, [])
        changed = False
        
        for img_id in new_ids:
            if img_id not in seen:
                seen.append(img_id)
                changed = True
        
        if changed:
            if len(seen) > MAX_HISTORY:
                self.data["seen_images"][keyword] = seen[-MAX_HISTORY:]
            self.save_data()


