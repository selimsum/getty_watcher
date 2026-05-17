import pytest
import datetime
from unittest.mock import MagicMock
from main import App

@pytest.fixture
def app_instance():
    # Create a mock App to avoid UI initialization issues during testing
    app = MagicMock(spec=App)
    # Bind the actual methods to our mocked instance
    app._parse_date = App._parse_date.__get__(app, App)
    app._parse_iso_date = App._parse_iso_date.__get__(app, App)
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
