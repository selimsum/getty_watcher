from unittest.mock import patch, MagicMock, call
from scraper import GettyScraper

class TestGettyScraper:
    @patch('time.time')
    @patch('time.sleep')
    def test_stop_aware_sleep_no_stop_callback(self, mock_sleep, mock_time):
        # We need time.time() to return increasing values
        # Initially 0.0, then it will check loop condition
        # the loop condition checks time.time() < end_time (which is 1.0)
        # Inside the loop time.time() is called again to calculate sleep
        time_values = [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 0.75, 0.75, 1.0]
        mock_time.side_effect = time_values

        scraper = GettyScraper()
        result = scraper._stop_aware_sleep(1.0)

        assert result is False
        assert mock_sleep.call_count == 4
        mock_sleep.assert_has_calls([call(0.25), call(0.25), call(0.25), call(0.25)])

    @patch('time.time')
    @patch('time.sleep')
    def test_stop_aware_sleep_returns_false_when_not_stopped(self, mock_sleep, mock_time):
        time_values = [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 0.75, 0.75, 1.0]
        mock_time.side_effect = time_values

        scraper = GettyScraper()
        should_stop = MagicMock(return_value=False)
        result = scraper._stop_aware_sleep(1.0, should_stop)

        assert result is False
        assert should_stop.call_count == 4
        assert mock_sleep.call_count == 4

    @patch('time.time')
    @patch('time.sleep')
    def test_stop_aware_sleep_returns_true_when_stopped(self, mock_sleep, mock_time):
        time_values = [0.0, 0.0, 0.0, 0.25, 0.25]
        mock_time.side_effect = time_values

        scraper = GettyScraper()
        should_stop = MagicMock(side_effect=[False, True])
        result = scraper._stop_aware_sleep(1.0, should_stop)

        assert result is True
        assert should_stop.call_count == 2
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_once_with(0.25)

    @patch('time.time')
    @patch('time.sleep')
    def test_stop_aware_sleep_exact_sleep_durations(self, mock_sleep, mock_time):
        # Test sleeping for 0.6 seconds
        # time.time() calls:
        # 1. calculate end_time: 0.0 -> end_time = 0.6
        # 2. while condition 1: 0.0 < 0.6 (True)
        # 3. calculate sleep 1: min(0.25, 0.6 - 0.0) -> 0.25
        # 4. while condition 2: 0.25 < 0.6 (True)
        # 5. calculate sleep 2: min(0.25, 0.6 - 0.25) -> 0.25
        # 6. while condition 3: 0.5 < 0.6 (True)
        # 7. calculate sleep 3: min(0.25, 0.6 - 0.5) -> 0.1
        # 8. while condition 4: 0.6 < 0.6 (False) -> break
        time_values = [0.0, 0.0, 0.0, 0.25, 0.25, 0.5, 0.5, 0.6]
        mock_time.side_effect = time_values

        scraper = GettyScraper()
        result = scraper._stop_aware_sleep(0.6)

        assert result is False
        assert mock_sleep.call_count == 3

        # In actual code: min(0.25, end_time - time.time())
        # First sleep: min(0.25, 0.6 - 0.0) = 0.25
        # Second sleep: min(0.25, 0.6 - 0.25) = 0.25
        # Third sleep: min(0.25, 0.6 - 0.5) = 0.1

        # Let's check floating point issues.
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 0.25
        assert calls[1][0][0] == 0.25
        assert round(calls[2][0][0], 1) == 0.1

    @patch.object(GettyScraper, 'get_full_res_urls_batch')
    def test_get_full_res_url_success(self, mock_batch):
        scraper = GettyScraper()
        url = "http://example.com/page1"
        full_url = "http://example.com/image1.jpg"
        mock_batch.return_value = {url: full_url}

        result = scraper.get_full_res_url(url)

        mock_batch.assert_called_once_with([url])
        assert result == full_url

    @patch.object(GettyScraper, 'get_full_res_urls_batch')
    def test_get_full_res_url_not_found(self, mock_batch):
        scraper = GettyScraper()
        url = "http://example.com/page1"
        mock_batch.return_value = {}

        result = scraper.get_full_res_url(url)

        mock_batch.assert_called_once_with([url])
        assert result is None

    @patch.object(GettyScraper, 'get_full_res_urls_batch')
    def test_get_full_res_url_different_url_returned(self, mock_batch):
        scraper = GettyScraper()
        url = "http://example.com/page1"
        mock_batch.return_value = {"http://example.com/otherpage": "http://example.com/image.jpg"}

        result = scraper.get_full_res_url(url)

        mock_batch.assert_called_once_with([url])
        assert result is None
