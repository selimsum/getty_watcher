import time
import urllib.parse
import datetime
import re
import random
import sys
import os
import subprocess
import json
from cookies import get_gettyimages_cookies

def _get_clean_env():
    """Returns a clean environment dictionary with only safe keys."""
    clean_env = {}
    safe_keys = ["PATH", "SYSTEMROOT", "USERPROFILE", "HOME", "TEMP", "TMP"]
    for key in safe_keys:
        if key in os.environ:
            clean_env[key] = os.environ[key]
    return clean_env

def ensure_playwright_browsers():
    """Ensures that playwright is installed and its browser binaries are available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Scraper] Playwright python package is not installed. Attempting to install...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], env=_get_clean_env(), check=True)
            print("[Scraper] Playwright python package installed successfully.")
        except Exception as e:
            print(f"[Scraper] Failed to install Playwright package: {e}")
            return False

    try:
        from playwright_stealth import Stealth
    except ImportError:
        print("[Scraper] Playwright-stealth python package is not installed. Attempting to install...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "playwright-stealth"], env=_get_clean_env(), check=True)
            print("[Scraper] Playwright-stealth python package installed successfully.")
        except Exception as e:
            print(f"[Scraper] Failed to install Playwright-stealth package: {e}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        error_msg = str(e)
        if "Executable doesn't exist" in error_msg or "playwright install" in error_msg:
            print("[Scraper] Playwright browser binaries not found or outdated. Installing firefox...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "firefox"],
                    env=_get_clean_env(),
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("[Scraper] Playwright firefox browser installed successfully!")
                    return True
                else:
                    print(f"[Scraper] Playwright installation failed with exit code {result.returncode}.\nError: {result.stderr}")
                    return False
            except Exception as ex:
                print(f"[Scraper] Failed to run playwright install command: {ex}")
                return False
        else:
            print(f"[Scraper] Error verifying Playwright installation: {e}")
            return False


class GettyScraper:
    # Firefox preferences to block media autoplay and mute audio
    _MUTED_PREFS = {
        "media.autoplay.default": 5,
        "media.autoplay.ask-permission": True,
        "media.autoplay.blocking_policy": 3,
        "media.volume": 0.0,
    }

    def __init__(self, use_cookies_fn=None):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
        self._use_cookies_fn = use_cookies_fn or (lambda: True)

    def _inject_cookies(self, context):
        """Load Getty cookies from Firefox and inject them into the browser context."""
        if not self._use_cookies_fn():
            print("[Scraper] Firefox cookies disabled in settings.")
            return
        try:
            cookies = get_gettyimages_cookies()
            if cookies:
                context.add_cookies(cookies)
                print(f"[Scraper] Injected {len(cookies)} cookies from Firefox.")
            else:
                print("[Scraper] No Getty cookies found in Firefox profile.")
        except FileNotFoundError as e:
            print(f"[Scraper] Cookie loading skipped: {e}")
        except Exception as e:
            print(f"[Scraper] Failed to inject cookies: {e}")

    def _is_blocked(self, page, response):
        """Checks if the current page is blocked by a captcha or rate limit."""
        if response and response.status in [403, 429]:
            return True
        if "challenge" in page.url:
            return True
        
        content = page.content().lower()
        block_keywords = ["captcha", "pardon our interruption", "perimeterx", "are you empty?", "bot-wall", "user validation"]
        return any(kw in content for kw in block_keywords)

    def check_keyword(self, keyword, cutoff_date=None, should_stop=None, media_type="images"):
        """
        Scrapes Getty Images for the given keyword.
        media_type: 'images', 'videos', or 'both'
        If cutoff_date (datetime object) is provided, scrapes until an image older than that date is found.
        Returns a list of dictionaries: {'id': str, 'url': str, 'title': str, 'date': str}
        """
        if media_type == "both":
            image_results = self.check_keyword(keyword, cutoff_date, should_stop, "images")
            if should_stop and should_stop():
                return image_results
            video_results = self.check_keyword(keyword, cutoff_date, should_stop, "videos")
            return image_results + video_results

        results = []
        encoded_keyword = urllib.parse.quote(keyword)
        item_type = "video" if media_type == "videos" else "image"
        if media_type == "videos":
            base_url = f"https://www.gettyimages.com/search/2/film?phrase={encoded_keyword}&suppressfamilycorrection=true&sort=newest"
        else:
            base_url = f"https://www.gettyimages.com/search/2/image?family=editorial&groupbyevent=false&phrase={encoded_keyword}&sort=newest"
        
        type_label = "videos" if media_type == "videos" else "images"
        print(f"[Scraper] Checking {type_label}: {keyword} (Cutoff: {cutoff_date})")
        
        page_num = 1
        keep_scraping = True
        
        try:
            if not ensure_playwright_browsers():
                print("[Scraper] Playwright browser is not ready. Aborting scrape.")
                return results

            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth

            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True, firefox_user_prefs=self._MUTED_PREFS)
                context = browser.new_context(user_agent=self.user_agent)
                self._inject_cookies(context)
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                
                last_page_first_id = None
                end_of_results = False
                
                while keep_scraping:
                    if should_stop and should_stop():
                        print(f"[Scraper] Stop requested for '{keyword}'.")
                        break

                    url = f"{base_url}&page={page_num}"
                    print(f"[Scraper] Scraping page {page_num}...")
                    
                    success = False
                    for attempt in range(3):
                        try:
                            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                            if self._is_blocked(page, response):
                                wait_time = 15 + (attempt * 10)
                                print(f"[Scraper] Block detected on page {page_num}. Waiting {wait_time}s...")
                                time.sleep(wait_time)
                                continue
                                
                            page.wait_for_selector('article, [class*="MosaicAsset-module__container"]', timeout=30000)
                            success = True
                            break
                        except Exception as e:
                            error_str = str(e).lower()
                            is_timeout = "timeout" in error_str

                            if is_timeout:
                                # Page loaded but no items — check if this is end of results
                                try:
                                    has_json_items = False
                                    scripts = page.query_selector_all('script[type="application/json"]')
                                    for script in scripts:
                                        text = script.inner_text() or ""
                                        if '"assets"' in text and '"gallery"' in text:
                                            data = json.loads(text)
                                            if data.get('search', {}).get('gallery', {}).get('assets', []):
                                                has_json_items = True
                                                break

                                    has_dom_items = bool(
                                        page.query_selector_all('article')
                                        or page.query_selector_all('[class*="MosaicAsset-module__container"]')
                                    )

                                    if not has_json_items and not has_dom_items:
                                        print(f"[Scraper] No more results at page {page_num}.")
                                        success = True  # Mark as done, not as error
                                        end_of_results = True
                                        break
                                except Exception:
                                    pass

                            print(f"[Scraper] Error on page {page_num} (Attempt {attempt+1}): {e}")
                            time.sleep(5)
                    
                    if not success:
                        print(f"[Scraper] Failed to load page {page_num}.")
                        break

                    if end_of_results:
                        break

                    json_assets = []
                    try:
                        scripts = page.query_selector_all('script[type="application/json"]')
                        for script in scripts:
                            text = script.inner_text() or ""
                            if '"assets"' in text and '"gallery"' in text:
                                json_data = json.loads(text)
                                assets = json_data.get('search', {}).get('gallery', {}).get('assets', [])
                                if assets:
                                    json_assets = assets
                                    break
                    except Exception as e:
                        print(f"[Scraper] Error checking page JSON: {e}")

                    parsed_items = []
                    if json_assets:
                        print(f"[Scraper] Found {len(json_assets)} items in page JSON data.")
                        for asset in json_assets:
                            asset_id = str(asset.get('id', asset.get('assetId', '')))
                            landing_url = asset.get('landingUrl', '')
                            img_url = f"https://www.gettyimages.com{landing_url}" if landing_url else ""
                            title = asset.get('title') or asset.get('altText') or "No Title"
                            date_str = asset.get('uploadDate', '')
                            
                            if asset_id and img_url:
                                parsed_items.append({
                                    'id': asset_id,
                                    'url': img_url,
                                    'title': title,
                                    'date': date_str,
                                    'type': item_type
                                })
                    else:
                        items = page.query_selector_all('article') or page.query_selector_all('[class*="MosaicAsset-module__container"]')
                        if not items:
                            print(f"[Scraper] No items found on page {page_num}.")
                            break
                        print(f"[Scraper] Found {len(items)} items on page {page_num}")
                        for item in items:
                            try:
                                img_id = item.get_attribute('data-unique-id')
                                link_el = item.query_selector('a[href]')
                                img_url = f"https://www.gettyimages.com{link_el.get_attribute('href')}" if link_el else ""
                                
                                if not img_id and img_url:
                                    match = re.search(r'/(\d+)(?:\?|$)', img_url)
                                    if match:
                                        img_id = match.group(1)

                                if not img_id:
                                    continue

                                date_el = item.query_selector('meta[itemprop="uploadDate"]')
                                date_str = date_el.get_attribute('content') if date_el else ""
                                
                                img_el = item.query_selector('img')
                                title = img_el.get_attribute('alt') if img_el else "No Title"

                                if img_id and img_url:
                                    parsed_items.append({
                                        'id': img_id,
                                        'url': img_url,
                                        'title': title,
                                        'date': date_str,
                                        'type': item_type
                                    })
                            except Exception as e:
                                print(f"Error parsing item: {e}")

                    page_new_items_count = 0
                    for item_data in parsed_items:
                        img_id = item_data['id']
                        img_url = item_data['url']
                        title = item_data['title']
                        date_str = item_data['date']
                        
                        if cutoff_date and date_str:
                            try:
                                img_date = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                                if img_date < cutoff_date:
                                    keep_scraping = False
                                    print(f"[Scraper] Reached cutoff date ({img_date} < {cutoff_date}).")
                                    break
                            except Exception:
                                pass
                        
                        results.append(item_data)
                        page_new_items_count += 1

                    if results and page_new_items_count > 0:
                        current_page_first_id = results[-page_new_items_count]['id']
                        if current_page_first_id == last_page_first_id:
                            print(f"[Scraper] Pagination repeated at page {page_num}.")
                            break
                        last_page_first_id = current_page_first_id
                    
                    if not keep_scraping:
                        break
                        
                    page_num += 1
                    if page_num > 10000:
                        break
                    
                    time.sleep(2 + random.uniform(0.5, 2.0))
                        
                browser.close()
        except Exception as e:
            print(f"[Scraper] Error scraping '{keyword}': {e}")
            
        return results

    def get_full_res_url(self, page_url):
        """Fetches the full resolution image URL for a given detail page URL."""
        res = self.get_full_res_urls_batch([page_url])
        return res.get(page_url)

    def _extract_video_urls_from_page(self, content):
        """
        Extract video mp4 URLs from a Getty Images video detail page.
        Tries JSON-LD, embedded JSON, and video/source elements.
        """
        urls = []

        # 1. JSON-LD VideoObject contentUrl
        for match in re.finditer(r'"contentUrl"\s*:\s*"([^"]*?\.mp4[^"]*?)"', content):
            url = match.group(1).replace(r'\u0026', '&').replace('&amp;', '&')
            urls.append(url)

        # 2. Any media.gettyimages.com .mp4 URL in the page source
        for match in re.finditer(r'(?:"|\')(https?://media\.gettyimages\.com/[^"\']*?\.mp4[^"\']*)(?:"|\')', content):
            url = match.group(1).replace(r'\u0026', '&').replace('&amp;', '&')
            urls.append(url)

        # 3. <video> or <source> element src attributes
        for match in re.finditer(r'<(?:video|source)[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']', content):
            url = match.group(1).replace(r'\u0026', '&').replace('&amp;', '&')
            urls.append(url)

        # Deduplicate while preserving order (earliest match = highest priority)
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _stop_aware_sleep(self, seconds, should_stop=None):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if should_stop and should_stop():
                return True
            time.sleep(min(0.25, end_time - time.time()))
        return False

    def get_full_res_urls_batch(self, page_urls, should_stop=None, media_type="images"):
        """Fetches full resolution URLs for a list of page URLs in a single browser session."""
        results = {}
        if not page_urls:
            return results

        type_label = "videos" if media_type == "videos" else "images"
        print(f"[Scraper] Batch fetching {len(page_urls)} {type_label} URLs...")
        
        try:
            if not ensure_playwright_browsers():
                print("[Scraper] Playwright browser is not ready. Aborting batch fetch.")
                return results

            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True, firefox_user_prefs=self._MUTED_PREFS)
                context = browser.new_context(user_agent=self.user_agent)
                self._inject_cookies(context)
                page = context.new_page()

                for i, url in enumerate(page_urls):
                    if should_stop and should_stop():
                        print("[Scraper] Stop requested during batch fetch.")
                        break

                    print(f"[Scraper] Fetching {i+1}/{len(page_urls)}: {url}")
                    for attempt in range(2):
                        if should_stop and should_stop():
                            print("[Scraper] Stop requested during batch fetch.")
                            break

                        try:
                            response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            if should_stop and should_stop():
                                print("[Scraper] Stop requested during batch fetch.")
                                break

                            if self._is_blocked(page, response):
                                wait_time = 10 + (attempt * 5)
                                if self._stop_aware_sleep(wait_time, should_stop):
                                    print("[Scraper] Stop requested during batch fetch.")
                                    break
                                continue
                            
                            content = page.content()
                            if media_type == "videos":
                                video_urls = self._extract_video_urls_from_page(content)
                                if video_urls:
                                    results[url] = video_urls[0]
                                    break
                                else:
                                    print(f"[Scraper] Could not find video URL for {url}")
                            else:
                                match = re.search(r'"largeMainImageURL":"([^"]+)"', content)
                                if match:
                                    full_url = match.group(1).replace(r'\u0026', '&')
                                    results[url] = full_url
                                    break
                                else:
                                    print(f"[Scraper] Could not find URL for {url}")
                                
                        except Exception as e:
                            print(f"[Scraper] Error fetching {url}: {e}")
                            if self._stop_aware_sleep(2, should_stop):
                                print("[Scraper] Stop requested during batch fetch.")
                                break

                    if should_stop and should_stop():
                        break
                            
                    if self._stop_aware_sleep(2.0 + random.uniform(0.5, 2.0), should_stop):
                        print("[Scraper] Stop requested during batch fetch.")
                        break
                
                browser.close()
        except Exception as e:
            print(f"[Scraper] Batch error: {e}")
            
        return results

