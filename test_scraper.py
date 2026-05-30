import pytest
from unittest.mock import MagicMock
from scraper import GettyScraper


@pytest.fixture
def scraper():
    return GettyScraper()


def test_is_blocked_status_403(scraper):
    page = MagicMock()
    page.url = "https://example.com"
    page.content.return_value = "Normal page content"

    response = MagicMock()
    response.status = 403

    assert scraper._is_blocked(page, response) is True


def test_is_blocked_status_429(scraper):
    page = MagicMock()
    page.url = "https://example.com"
    page.content.return_value = "Normal page content"

    response = MagicMock()
    response.status = 429

    assert scraper._is_blocked(page, response) is True


def test_is_blocked_url_challenge(scraper):
    page = MagicMock()
    page.url = "https://example.com/challenge?something=1"
    page.content.return_value = "Normal page content"

    response = MagicMock()
    response.status = 200

    assert scraper._is_blocked(page, response) is True


@pytest.mark.parametrize("keyword", [
    "captcha",
    "pardon our interruption",
    "perimeterx",
    "are you empty?",
    "bot-wall",
    "user validation"
])
def test_is_blocked_content_keywords(scraper, keyword):
    page = MagicMock()
    page.url = "https://example.com"
    # Ensure it works even if the page content has different casing
    page.content.return_value = (
        f"<html><body>Please complete the "
        f"{keyword.upper()} to continue.</body></html>"
    )

    response = MagicMock()
    response.status = 200

    assert scraper._is_blocked(page, response) is True


def test_is_blocked_no_block(scraper):
    page = MagicMock()
    page.url = "https://example.com/normal-path"
    page.content.return_value = (
        "<html><body>Welcome to the site!</body></html>"
    )

    response = MagicMock()
    response.status = 200

    assert scraper._is_blocked(page, response) is False


def test_is_blocked_none_response(scraper):
    # This simulates cases where response might be None
    page = MagicMock()
    page.url = "https://example.com/normal-path"
    page.content.return_value = (
        "<html><body>Welcome to the site!</body></html>"
    )

    response = None

    assert scraper._is_blocked(page, response) is False


def test_is_blocked_none_response_with_challenge_url(scraper):
    page = MagicMock()
    page.url = "https://example.com/challenge"
    page.content.return_value = (
        "<html><body>Welcome to the site!</body></html>"
    )

    response = None

    assert scraper._is_blocked(page, response) is True
