import pytest
import datetime
from unittest.mock import MagicMock
from main import App

import builtins
from unittest.mock import patch

@pytest.fixture
def app_instance():
    # Create a mock App to avoid UI initialization issues during testing
    app = MagicMock(spec=App)
    # Bind the actual methods to our mocked instance
    app._parse_date = App._parse_date.__get__(app, App)
    app._parse_iso_date = App._parse_iso_date.__get__(app, App)
    app._download_file = App._download_file.__get__(app, App)
    app.save_settings = App.save_settings.__get__(app, App)
    app.log = MagicMock()
    return app


def test_parse_date_valid(app_instance):
    # Test valid dates in "%d.%m.%Y" format
    dt = app_instance._parse_date("15.05.2023")
    assert isinstance(dt, datetime.datetime)
    assert dt.year == 2023
    assert dt.month == 5
    assert dt.day == 15

    dt = app_instance._parse_date("01.01.2000")
    assert dt.year == 2000
    assert dt.month == 1
    assert dt.day == 1

def test_parse_date_invalid(app_instance):
    # Test invalid date formats
    assert app_instance._parse_date("2023-05-15") is None
    assert app_instance._parse_date("15/05/2023") is None
    assert app_instance._parse_date("invalid date") is None
    assert app_instance._parse_date("32.01.2023") is None  # Invalid day
    assert app_instance._parse_date("15.13.2023") is None  # Invalid month

def test_parse_date_empty(app_instance):
    # Test empty or None inputs
    assert app_instance._parse_date("") is None
    assert app_instance._parse_date(None) is None


def test_parse_iso_date_valid(app_instance):
    # Test valid dates in ISO format strings, expects "%Y-%m-%d" parsing of first 10 chars
    dt = app_instance._parse_iso_date("2023-05-15T10:30:00Z")
    assert isinstance(dt, datetime.datetime)
    assert dt.year == 2023
    assert dt.month == 5
    assert dt.day == 15

    dt = app_instance._parse_iso_date("2000-01-01")
    assert dt.year == 2000
    assert dt.month == 1
    assert dt.day == 1

def test_parse_iso_date_invalid(app_instance):
    # Test invalid date formats
    assert app_instance._parse_iso_date("15.05.2023") is None
    assert app_instance._parse_iso_date("15/05/2023") is None
    assert app_instance._parse_iso_date("invalid date") is None
    assert app_instance._parse_iso_date("2023-13-15") is None  # Invalid month
    assert app_instance._parse_iso_date("2023-01-32") is None  # Invalid day
    assert app_instance._parse_iso_date("123") is None  # Too short

def test_parse_iso_date_empty(app_instance):
    # Test empty or None inputs
    assert app_instance._parse_iso_date("") is None
    assert app_instance._parse_iso_date(None) is None

@patch("main.requests.get")
@patch("builtins.open", new_callable=MagicMock)
def test_download_file_timeout(mock_open, mock_get, app_instance):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"image data"
    mock_get.return_value = mock_resp

    url = "https://example.com/image.jpg"
    filepath = "test.jpg"

    result = app_instance._download_file(url, filepath)

    assert result is True
    # Ensure get was called with a timeout
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert "timeout" in kwargs
    assert kwargs["timeout"] == 15

@patch("main.requests.get")
@patch("main.time.sleep")
@patch("builtins.open", new_callable=MagicMock)
def test_download_file_retry_timeout(mock_open, mock_sleep, mock_get, app_instance):
    # First call returns 429, second returns 200
    resp_429 = MagicMock()
    resp_429.status_code = 429

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.content = b"image data"

    mock_get.side_effect = [resp_429, resp_200]

    url = "https://example.com/image.jpg"
    filepath = "test.jpg"

    result = app_instance._download_file(url, filepath)

    assert result is True
    # Ensure get was called twice, both times with a timeout
    assert mock_get.call_count == 2
    for call in mock_get.call_args_list:
        _, kwargs = call
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 15

@patch("main.os.makedirs")
@patch("main.DEFAULT_DOWNLOAD_DIR", "mocked_default_dir")
def test_save_settings_error_path(mock_makedirs, app_instance):
    # Setup mocks
    mock_makedirs.side_effect = Exception("Permission denied")

    app_instance.settings_path_var = MagicMock()
    app_instance.settings_path_var.get.return_value = "new_dir"

    app_instance._absolute_download_dir = MagicMock()
    app_instance._absolute_download_dir.return_value = "/mock/new_dir"

    app_instance.settings_feedback_text = MagicMock()
    app_instance.state_manager = MagicMock()
    app_instance.settings_notifications_var = MagicMock()
    app_instance._refresh_save_location = MagicMock()

    # Call method
    app_instance.save_settings()

    # Assertions
    app_instance._absolute_download_dir.assert_called_once_with("new_dir")
    mock_makedirs.assert_called_once_with("/mock/new_dir", exist_ok=True)
    app_instance.settings_feedback_text.set.assert_called_once_with("Could not use this folder: Permission denied")

    # Verify we returned early and didn't save settings
    app_instance.state_manager.set_setting.assert_not_called()
    app_instance._refresh_save_location.assert_not_called()
