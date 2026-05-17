import pytest
import os
from unittest.mock import patch
from main import App

@patch('os.makedirs')
def test_get_download_path_keyword_sanitization(mock_makedirs):
    keyword = "test/k e*yw#ord!"
    img_data = {
        'id': '12345',
        'title': 'A normal title'
    }

    filename, download_dir = App._get_download_path(None, keyword, img_data)

    # [^\w\s] replaced with '' -> "testk eyword"
    expected_dir = os.path.join("downloads", "testk eyword")
    assert download_dir == expected_dir
    mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)

@patch('os.makedirs')
def test_get_download_path_title_sanitization(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'A! b@a#d/ t?i*t&l%e'
    }

    filename, download_dir = App._get_download_path(None, keyword, img_data)

    # 0000.00.00 A bad title 12345.jpg
    assert filename == "0000.00.00 A bad title 12345.jpg"

@patch('os.makedirs')
def test_get_download_path_title_truncation(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'A' * 300
    }

    filename, download_dir = App._get_download_path(None, keyword, img_data)

    assert len(filename) == 250
    # Fixed length: len("0000.00.00") (10) + 2 spaces + len("12345") (5) + len(".jpg") (4) = 21
    # Max title len: 250 - 21 = 229
    assert filename.startswith("0000.00.00 " + ("A" * 229) + " 12345.jpg")


@patch('os.makedirs')
def test_get_download_path_valid_date(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'Test title',
        'date': '2023-10-25T14:30:00Z'
    }

    filename, _ = App._get_download_path(None, keyword, img_data)
    assert filename.startswith("2023.10.25 ")

@patch('os.makedirs')
def test_get_download_path_missing_date(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'Test title'
    }

    filename, _ = App._get_download_path(None, keyword, img_data)
    assert filename.startswith("0000.00.00 ")

@patch('os.makedirs')
def test_get_download_path_empty_date(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'Test title',
        'date': ''
    }

    filename, _ = App._get_download_path(None, keyword, img_data)
    assert filename.startswith("0000.00.00 ")

@patch('os.makedirs')
def test_get_download_path_invalid_date(mock_makedirs):
    keyword = "test"
    img_data = {
        'id': '12345',
        'title': 'Test title',
        'date': 'invalid-date-string'
    }

    filename, _ = App._get_download_path(None, keyword, img_data)
    assert filename.startswith("0000.00.00 ")
