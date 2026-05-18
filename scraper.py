from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import time
import urllib.parse
import datetime
import re
import random

class GettyScraper:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"

    def _is_blocked(self, page, response):
        """Checks if the current page is blocked by a captcha or rate limit."""
        if response and response.status in [403, 429]:
            return True
        if "challenge" in page.url:
            return True
        
        content = page.content().lower()
        block_keywords = ["captcha", "pardon our interruption", "perimeterx", "are you empty?", "bot-wall", "user validation"]
        return any(kw in content for kw in block_keywords)

    def check_keyword(self, keyword, cutoff_date=None, should_stop=None):
        """
        Scrapes Getty Images for the given keyword.
        If cutoff_date (datetime object) is provided, scrapes until an image older than that date is found.
        Returns a list of dictionaries: {'id': str, 'url': str, 'title': str, 'date': str}
        """
        results = []
        encoded_keyword = urllib.parse.quote(keyword)
        base_url = f"https://www.gettyimages.com/search/2/image?family=editorial&groupbyevent=false&phrase={encoded_keyword}&sort=newest"
        
        print(f"[Scraper] Checking: {keyword} (Cutoff: {cutoff_date})")
        
        page_num = 1
        keep_scraping = True
        
        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True)
                context = browser.new_context(user_agent=self.user_agent)
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                
                last_page_first_id = None
                
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
                            print(f"[Scraper] Error on page {page_num} (Attempt {attempt+1}): {e}")
                            time.sleep(5)
                    
                    if not success:
                        print(f"[Scraper] Failed to load page {page_num}.")
                        break

                    items = page.query_selector_all('article') or page.query_selector_all('[class*="MosaicAsset-module__container"]')
                    if not items:
                        print(f"[Scraper] No items found on page {page_num}.")
                        break

                    print(f"[Scraper] Found {len(items)} items on page {page_num}")
                    page_new_items_count = 0
                    
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
                            
                            if cutoff_date and date_str:
                                try:
                                    img_date = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                                    if img_date < cutoff_date:
                                        keep_scraping = False
                                        print(f"[Scraper] Reached cutoff date ({img_date} < {cutoff_date}).")
                                        break 
                                except Exception:
                                    pass

                            img_el = item.query_selector('img')
                            title = img_el.get_attribute('alt') if img_el else "No Title"

                            if img_id and img_url:
                                results.append({
                                    'id': img_id,
                                    'url': img_url,
                                    'title': title,
                                    'date': date_str
                                })
                                page_new_items_count += 1
                        except Exception as e:
                            print(f"Error parsing item: {e}")

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

    def _stop_aware_sleep(self, seconds, should_stop=None):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if should_stop and should_stop():
                return True
            time.sleep(min(0.25, end_time - time.time()))
        return False

    def get_full_res_urls_batch(self, page_urls, should_stop=None):
        """Fetches full resolution URLs for a list of page URLs in a single browser session."""
        results = {}
        if not page_urls:
            return results

        print(f"[Scraper] Batch fetching {len(page_urls)} URLs...")
        
        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True)
                context = browser.new_context(user_agent=self.user_agent)
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

