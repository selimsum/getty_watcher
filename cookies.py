"""
Extracts cookies from Firefox profiles for use with Playwright.

Firefox stores cookies in a SQLite database (cookies.sqlite) inside the
user's profile directory.  When Firefox is running the file is locked,
so we copy it to a temporary location before reading.
"""

import configparser
import os
import platform
import shutil
import sqlite3
import tempfile
from typing import List, Dict, Optional


def _find_firefox_profiles_dir() -> Optional[str]:
    """Return the path to the Firefox profiles directory, or None."""
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "Mozilla", "Firefox", "Profiles")
    elif system == "Darwin":
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")
    else:
        # Linux / other
        home = os.path.expanduser("~")
        # Snap-based Firefox (Ubuntu)
        snap = os.path.join(home, "snap", "firefox", "common", ".mozilla", "firefox")
        if os.path.isdir(snap):
            return snap
        return os.path.join(home, ".mozilla", "firefox")


def _get_all_profile_paths() -> List[str]:
    """
    Parse profiles.ini and return all profile directory paths,
    ordered by preference: Install-default first, then Default=1,
    then remaining profiles.
    """
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        ini_path = os.path.join(appdata, "Mozilla", "Firefox", "profiles.ini")
    elif system == "Darwin":
        home = os.path.expanduser("~")
        ini_path = os.path.join(home, "Library", "Application Support", "Firefox", "profiles.ini")
    else:
        home = os.path.expanduser("~")
        snap = os.path.join(home, "snap", "firefox", "common", ".mozilla", "firefox", "profiles.ini")
        if os.path.isfile(snap):
            ini_path = snap
        else:
            ini_path = os.path.join(home, ".mozilla", "firefox", "profiles.ini")

    if not os.path.isfile(ini_path):
        return []

    config = configparser.ConfigParser()
    try:
        config.read(ini_path, encoding="utf-8")
    except Exception:
        return []

    ini_dir = os.path.dirname(ini_path)

    def _resolve_path(raw_path: str, is_relative: str) -> str:
        if is_relative == "1":
            return os.path.normpath(os.path.join(ini_dir, raw_path.replace("/", os.sep)))
        return raw_path

    profile_paths: Dict[str, str] = {}
    default_from_profile = None
    default_from_install = None

    for section in config.sections():
        if section.startswith("Profile"):
            try:
                path = config.get(section, "Path")
                is_rel = config.get(section, "IsRelative", fallback="1")
                abs_path = _resolve_path(path, is_rel)
                name = config.get(section, "Name", fallback=section)
                profile_paths[name] = abs_path
                if config.get(section, "Default", fallback="0") == "1":
                    default_from_profile = abs_path
            except Exception:
                continue
        elif section.startswith("Install"):
            try:
                raw = config.get(section, "Default")
                default_from_install = _resolve_path(raw, "1")
            except Exception:
                continue

    # Build ordered list: preferred profiles first
    ordered = []
    seen = set()
    for candidate in [default_from_install, default_from_profile]:
        if candidate and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    for p in profile_paths.values():
        if p not in seen:
            ordered.append(p)
            seen.add(p)

    return ordered


def _read_cookies_from_db(db_path: str, domains: List[str]) -> List[Dict]:
    """Read cookies for the given domains from a single cookies.sqlite file."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(tmp_fd)
    try:
        shutil.copy2(db_path, tmp_path)
        for suffix in ("-wal", "-shm"):
            src = db_path + suffix
            if os.path.isfile(src):
                shutil.copy2(src, tmp_path + suffix)

        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where_parts = []
        params = []
        for d in domains:
            clean = d.lstrip(".")
            where_parts.append("(host = ? OR host = ? OR host = ?)")
            params.extend([clean, "." + clean, "%." + clean])

        query = f"""
            SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            WHERE {" OR ".join(where_parts)}
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        cookies = []
        for row in rows:
            same_site_map = {0: "None", 1: "Lax", 2: "Strict"}
            cookie = {
                "name": row["name"],
                "value": row["value"],
                "domain": row["host"],
                "path": row["path"],
                "expires": float(row["expiry"]) if row["expiry"] else -1,
                "secure": bool(row["isSecure"]),
                "httpOnly": bool(row["isHttpOnly"]),
                "sameSite": same_site_map.get(row["sameSite"], "None"),
            }
            cookies.append(cookie)

        return cookies
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(tmp_path + suffix)
            except OSError:
                pass


def get_firefox_cookies(domains: List[str]) -> List[Dict]:
    """
    Read cookies for the given domains from Firefox profiles.
    Searches all available profiles and returns cookies from the first
    profile that contains matching cookies.

    Returns a list of dicts in Playwright's ``BrowserContext.add_cookies``
    format.

    Raises ``FileNotFoundError`` if no Firefox profile or cookies file is
    found.
    """
    profiles = _get_all_profile_paths()
    if not profiles:
        raise FileNotFoundError("Could not locate any Firefox profile.")

    for profile_path in profiles:
        cookies_db = os.path.join(profile_path, "cookies.sqlite")
        if not os.path.isfile(cookies_db):
            continue

        cookies = _read_cookies_from_db(cookies_db, domains)
        if cookies:
            print(f"[Cookies] Found {len(cookies)} cookies in profile: {os.path.basename(profile_path)}")
            return cookies

    # No cookies found in any profile - return empty list (not an error)
    return []


def get_gettyimages_cookies() -> List[Dict]:
    """Convenience: fetch cookies for gettyimages.com."""
    return get_firefox_cookies(["gettyimages.com", "www.gettyimages.com"])


if __name__ == "__main__":
    cookies = get_gettyimages_cookies()
    print(f"Found {len(cookies)} Getty Images cookies:")
    for c in cookies:
        print(f"  {c['name']} = {c['value'][:30]}... (domain={c['domain']})")
