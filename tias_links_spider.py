import scrapy
import pandas as pd
import logging
import random
import re
import os
from urllib.parse import urljoin
from scrapy_playwright.page import PageMethod

# Configure logging
logging.getLogger('scrapy').setLevel(logging.DEBUG)
logging.getLogger('playwright').setLevel(logging.DEBUG)

class TiasLinksSpider(scrapy.Spider):
    name = 'tias_links_spider'
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'DOWNLOAD_DELAY': 45,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [403, 429, 503],
        'LOG_LEVEL': 'DEBUG',
        'FEEDS': {
            'all_extracted_links.csv': {
                'format': 'csv',
                'fields': ['URL'],
                'overwrite': True,
            },
        },
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'tias_scraper.middlewares.RandomUserAgentMiddleware': 400,
        },
    }

    def __init__(self, max_years=None, *args, **kwargs):
        """
        Initialize spider with optional max_years.
        """
        super().__init__(*args, **kwargs)
        years_df = pd.read_csv('https://raw.githubusercontent.com/nicolesorense/Diplomatic-agreements-files-and-code/refs/heads/main/treaty_years.csv')
        self.year_urls = [f'https://www.state.gov/{year}-TIAS/?results=200' for year in years_df['Years'].astype(str)]
        if max_years:
            try:
                self.year_urls = self.year_urls[:int(max_years)]
            except ValueError:
                self.log(f"Invalid max_years: {max_years}, processing all years", level=logging.WARNING)
        self.log(f"Processing {len(self.year_urls)} year URLs: {self.year_urls}", level=logging.DEBUG)
        os.makedirs('debug_html', exist_ok=True)

    def start_requests(self):
        """
        Use Playwright to render yearly index pages.
        """
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.state.gov/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Ch-Ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
        }
        for url in self.year_urls:
            yield scrapy.Request(
                url,
                headers=headers,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_selector', 'ul.collection-results li', timeout=30000),
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),
                        PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
                        PageMethod('wait_for_timeout', 2000),
                    ],
                    'playwright_context_kwargs': {
                        'viewport': {'width': 1920, 'height': 1080},
                        'locale': 'en-US',
                        'ignore_https_errors': True,
                    },
                },
                callback=self.parse,
                errback=self.errback
            )

    def parse(self, response):
        """
        Extract agreement links from yearly index page.
        """
        self.log(f"Processing URL: {response.url} (Status: {response.status})", level=logging.DEBUG)
        self.log(f"Response headers: {response.headers}", level=logging.DEBUG)

        # Save HTML
        html_file = f"debug_html/{response.url.split('/')[-2]}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        self.log(f"Saved HTML to {html_file}", level=logging.DEBUG)

        if 'forbidden' in response.text.lower() or response.status in [403, 429]:
            self.log(f"Blocked or forbidden response for {response.url}", level=logging.ERROR)
            return

        # Method 1: Firecrawl regex
        url_pattern = r'\((https://www\.state\.gov/[^\)]+)\)'
        markdown_links = re.findall(url_pattern, response.text)
        agreement_links = [
            link for link in markdown_links
            if re.match(r'https://www\.state\.gov/\d{2}-\d{3,4}$', link)
        ]
        self.log(f"Found {len(markdown_links)} markdown links, {len(agreement_links)} valid: {agreement_links[:5]}", level=logging.DEBUG)

        # Method 2: CSS/XPath for <a> tags
        links = response.css('ul.collection-results a.collection-result__link::attr(href)').getall()
        links = list(set(links))  # Deduplicate early
        all_hrefs = response.css('a::attr(href)').getall()
        self.log(f"Found {len(all_hrefs)} total <a> hrefs: {all_hrefs[:20]}", level=logging.DEBUG)
        self.log(f"Found {len(links)} agreement-like hrefs: {links[:10]}", level=logging.DEBUG)

        # Filter out year pages (treaties-and-agreements) and keep all other links
        agreement_links.extend([
            link for link in links
            if link and 'treaties-and-agreements' not in link.lower()
        ])
        agreement_links = list(set(agreement_links))  # Ensure uniqueness
        self.log(f"Total {len(agreement_links)} unique agreement links: {agreement_links[:5]}", level=logging.DEBUG)

        # Yield each link
        for link in agreement_links:
            self.log(f"Yielding link: {link}", level=logging.DEBUG)
            yield {'URL': link}

    def errback(self, failure):
        """
        Handle request failures.
        """
        self.log(f"Request failed: {failure}", level=logging.ERROR)
        if failure.check(scrapy.exceptions.IgnoreRequest):
            self.log(f"Ignored request: {failure.request.url}", level=logging.WARNING)
        else:
            self.log(f"Error on {failure.request.url}: {failure.value}", level=logging.ERROR)