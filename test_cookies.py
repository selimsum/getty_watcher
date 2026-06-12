from unittest.mock import patch

import cookies

def test_get_gettyimages_cookies():
    """Test that get_gettyimages_cookies calls get_firefox_cookies with the correct domains."""
    mock_return_value = [{"name": "test_cookie", "value": "123", "domain": "gettyimages.com"}]

    with patch("cookies.get_firefox_cookies", return_value=mock_return_value) as mock_get_firefox_cookies:
        result = cookies.get_gettyimages_cookies()

        # Verify get_firefox_cookies was called with the correct domains list
        mock_get_firefox_cookies.assert_called_once_with(["gettyimages.com", "www.gettyimages.com"])

        # Verify the return value matches what get_firefox_cookies returned
        assert result == mock_return_value
