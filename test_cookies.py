import pytest
from unittest.mock import patch

import os
import cookies

@patch("platform.system", return_value="Windows")
@patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"})
def test_find_firefox_profiles_dir_windows(mock_system):
    expected = os.path.join("C:\\Users\\Test\\AppData\\Roaming", "Mozilla", "Firefox", "Profiles")
    assert cookies._find_firefox_profiles_dir() == expected

@patch("platform.system", return_value="Darwin")
@patch("os.path.expanduser", return_value="/Users/Test")
def test_find_firefox_profiles_dir_darwin(mock_expanduser, mock_system):
    expected = os.path.join("/Users/Test", "Library", "Application Support", "Firefox", "Profiles")
    assert cookies._find_firefox_profiles_dir() == expected

@patch("platform.system", return_value="Linux")
@patch("os.path.expanduser", return_value="/home/test")
@patch("os.path.isdir", return_value=True)
def test_find_firefox_profiles_dir_linux_snap(mock_isdir, mock_expanduser, mock_system):
    expected = os.path.join("/home/test", "snap", "firefox", "common", ".mozilla", "firefox")
    assert cookies._find_firefox_profiles_dir() == expected

@patch("platform.system", return_value="Linux")
@patch("os.path.expanduser", return_value="/home/test")
@patch("os.path.isdir", return_value=False)
def test_find_firefox_profiles_dir_linux_default(mock_isdir, mock_expanduser, mock_system):
    expected = os.path.join("/home/test", ".mozilla", "firefox")
    assert cookies._find_firefox_profiles_dir() == expected


import tempfile

@patch("os.path.isfile", return_value=False)
def test_get_all_profile_paths_no_ini(mock_isfile):
    assert cookies._get_all_profile_paths() == []

@patch("platform.system", return_value="Linux")
@patch("os.path.expanduser")
@patch("os.path.isfile")
def test_get_all_profile_paths_with_ini(mock_isfile, mock_expanduser, mock_system):
    # Setup temporary directory and fake profiles.ini
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_expanduser.return_value = tmpdir
        ini_path = os.path.join(tmpdir, ".mozilla", "firefox", "profiles.ini")
        os.makedirs(os.path.dirname(ini_path), exist_ok=True)

        ini_content = """
[General]
StartWithLastProfile=1

[Profile0]
Name=default
IsRelative=1
Path=Profiles/abc.default
Default=1

[Profile1]
Name=default-release
IsRelative=1
Path=Profiles/xyz.default-release

[Profile2]
Name=absolute-path
IsRelative=0
Path=/absolute/path/to/profile

[Install123456789]
Default=Profiles/xyz.default-release
Locked=1
"""
        with open(ini_path, "w") as f:
            f.write(ini_content)

        # Mock isfile to return True for snap path (will be ignored if we configure snap right,
        # or we just let it return True for our specific ini_path)
        mock_isfile.side_effect = lambda p: p == ini_path

        # We need to monkeypatch the platform path finding so it points to our temp ini
        # _get_all_profile_paths will look for ini at snap or normal path.
        # Let's just force snap to False and let it use the normal path.
        mock_isfile.side_effect = lambda path: path == ini_path

        paths = cookies._get_all_profile_paths()

        ini_dir = os.path.dirname(ini_path)
        expected_install = os.path.normpath(os.path.join(ini_dir, "Profiles/xyz.default-release"))
        expected_default = os.path.normpath(os.path.join(ini_dir, "Profiles/abc.default"))
        expected_absolute = "/absolute/path/to/profile"

        assert paths == [expected_install, expected_default, expected_absolute]


import sqlite3

def test_read_cookies_from_db_matching_domains():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cookies.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table
        cursor.execute('''
            CREATE TABLE moz_cookies (
                id INTEGER PRIMARY KEY,
                host TEXT,
                name TEXT,
                value TEXT,
                path TEXT,
                expiry INTEGER,
                isSecure INTEGER,
                isHttpOnly INTEGER,
                sameSite INTEGER
            )
        ''')

        # Insert test data
        cookies_data = [
            ("gettyimages.com", "cookie1", "val1", "/", 1700000000, 1, 1, 0),  # match, normal expiry, sameSite None
            (".gettyimages.com", "cookie2", "val2", "/", 1700000000000, 0, 0, 1), # match, ms expiry, sameSite Lax
            ("a.gettyimages.com", "cookie3", "val3", "/path", -1, 1, 0, 2), # match via %.gettyimages.com, no expiry, sameSite Strict
            ("other.com", "cookie4", "val4", "/", 1700000000, 1, 1, 0), # no match
        ]

        cursor.executemany('''
            INSERT INTO moz_cookies
            (host, name, value, path, expiry, isSecure, isHttpOnly, sameSite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', cookies_data)
        conn.commit()
        conn.close()

        extracted = cookies._read_cookies_from_db(db_path, ["gettyimages.com"])

        assert len(extracted) == 3

        # Verify first cookie
        assert extracted[0]["name"] == "cookie1"
        assert extracted[0]["value"] == "val1"
        assert extracted[0]["domain"] == "gettyimages.com"
        assert extracted[0]["expires"] == 1700000000.0
        assert extracted[0]["secure"] is True
        assert extracted[0]["httpOnly"] is True
        assert extracted[0]["sameSite"] == "None"

        # Verify ms expiry
        assert extracted[1]["name"] == "cookie2"
        assert extracted[1]["expires"] == 1700000000.0
        assert extracted[1]["sameSite"] == "Lax"

        # Verify no expiry
        assert extracted[2]["name"] == "cookie3"
        assert extracted[2]["expires"] == -1
        assert extracted[2]["sameSite"] == "Strict"


@patch("cookies._get_all_profile_paths", return_value=[])
def test_get_firefox_cookies_no_profiles(mock_get_all_profile_paths):
    with pytest.raises(FileNotFoundError, match="Could not locate any Firefox profile."):
        cookies.get_firefox_cookies(["gettyimages.com"])

@patch("cookies._get_all_profile_paths", return_value=["/fake/profile"])
@patch("os.path.isfile", return_value=False)
def test_get_firefox_cookies_no_cookies_db(mock_isfile, mock_get_all_profile_paths):
    assert cookies.get_firefox_cookies(["gettyimages.com"]) == []

@patch("cookies._get_all_profile_paths", return_value=["/fake/profile1", "/fake/profile2"])
@patch("os.path.isfile", side_effect=lambda x: x == "/fake/profile2/cookies.sqlite")
@patch("cookies._read_cookies_from_db")
def test_get_firefox_cookies_success(mock_read_cookies, mock_isfile, mock_get_all_profile_paths):
    expected_cookies = [{"name": "test", "value": "123", "domain": "gettyimages.com"}]
    mock_read_cookies.return_value = expected_cookies

    result = cookies.get_firefox_cookies(["gettyimages.com"])

    assert result == expected_cookies
    mock_read_cookies.assert_called_once_with("/fake/profile2/cookies.sqlite", ["gettyimages.com"])

@patch("cookies._get_all_profile_paths", return_value=["/fake/profile1", "/fake/profile2"])
@patch("os.path.isfile", return_value=True)
@patch("cookies._read_cookies_from_db", return_value=[])
def test_get_firefox_cookies_no_matching_cookies(mock_read_cookies, mock_isfile, mock_get_all_profile_paths):
    assert cookies.get_firefox_cookies(["gettyimages.com"]) == []


def test_get_gettyimages_cookies():
    """Test that get_gettyimages_cookies calls get_firefox_cookies with the correct domains."""
    mock_return_value = [{"name": "test_cookie", "value": "123", "domain": "gettyimages.com"}]

    with patch("cookies.get_firefox_cookies", return_value=mock_return_value) as mock_get_firefox_cookies:
        result = cookies.get_gettyimages_cookies()

        # Verify get_firefox_cookies was called with the correct domains list
        mock_get_firefox_cookies.assert_called_once_with(["gettyimages.com", "www.gettyimages.com"])

        # Verify the return value matches what get_firefox_cookies returned
        assert result == mock_return_value
