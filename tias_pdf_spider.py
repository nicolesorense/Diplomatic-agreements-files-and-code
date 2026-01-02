import scrapy
from urllib.parse import urljoin
import logging
import random
import re
from scrapy_playwright.page import PageMethod

# Configure logging
logging.getLogger('scrapy').setLevel(logging.INFO)
logging.getLogger('playwright').setLevel(logging.INFO)

class TiasPdfSpider(scrapy.Spider):
    name = 'tias_pdf_spider'
    # Example URLs; replace with your 84 URLs or load from file
    start_urls = [
        'https://www.state.gov/16-629/',
        'https://www.state.gov/10-413',
        'https://www.state.gov/argentina-97-826'
    ]
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        },
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'DOWNLOAD_DELAY': 5,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [403, 429, 503],
        'LOG_LEVEL': 'INFO',
        'FEEDS': {
            'tias_scraped_data.csv': {
                'format': 'csv',
                'fields': ['source_url', 'title', 'paragraphs', 'agreement_codes', 'primary_pdf', 'other_pdfs'],
                'overwrite': True,
            },
        },
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'tias_scraper.middlewares.RandomUserAgentMiddleware': 400,
        },
    }

    def __init__(self, urls_file=None, *args, **kwargs):
        """
        Initialize spider with optional URLs file.
        """
        super().__init__(*args, **kwargs)
        if urls_file:
            with open(urls_file, 'r') as f:
                self.start_urls = [line.strip() for line in f if line.strip()]

    def start_requests(self):
        """
        Use Playwright to render pages with JavaScript and custom headers.
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
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                headers=headers,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                        PageMethod('wait_for_timeout', random.uniform(1000, 3000)),
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
        Extract title, paragraphs, agreement codes, primary PDF, and other PDF links.
        """
        # Debug: Log response details
        self.log(f"Processing URL: {response.url} (Status: {response.status})")
        self.log(f"Response headers: {response.headers}")

        # Check for forbidden or error page
        if 'forbidden' in response.text.lower() or response.status in [403, 429]:
            self.log(f"Blocked or forbidden response for {response.url}")
            return

        # Extract title
        title_pattern = r'class="featured-content__headline stars-above">\s*(.*?)\s*</h1>'
        title_match = re.search(title_pattern, response.text, re.DOTALL)
        title = title_match.group(1).strip().replace('\n', '').replace('\t', '') if title_match else ''
        if not title:
            title = response.css('h1.featured-content__headline.stars-above::text').get(default='').strip()
        self.log(f"Extracted title: {title}")

        # Extract paragraphs (including text in nested tags)
        paragraph_nodes = response.xpath('//p//text()').getall()
        paragraphs = [p.strip() for p in paragraph_nodes if p.strip()]
        paragraphs_text = ' | '.join(paragraphs)
        self.log(f"Extracted {len(paragraphs)} paragraphs")

        # Extract agreement codes from paragraphs or links
        code_pattern = r'\b\d{2}[-\s]?\d{3,4}\b'
        agreement_codes = re.findall(code_pattern, paragraphs_text)
        # Also check PDF link text
        pdf_link_texts = response.css('a[href$=".pdf"]::text').getall()
        for link_text in pdf_link_texts:
            agreement_codes.extend(re.findall(code_pattern, link_text))
        agreement_codes = list(set(agreement_codes))  # Remove duplicates
        agreement_codes_text = ', '.join(agreement_codes) if agreement_codes else ''
        self.log(f"Extracted agreement codes: {agreement_codes_text}")

        # Extract primary PDF link
        primary_pdf = response.css('a.button--download::attr(href)').get(default='')
        primary_pdf = urljoin(response.url, primary_pdf) if primary_pdf else ''
        self.log(f"Primary PDF: {primary_pdf}")

        # Extract other PDF links (exclude primary)
        all_pdf_links = response.css('a[href$=".pdf"]::attr(href)').getall()
        all_pdf_links = [urljoin(response.url, link) for link in all_pdf_links]
        other_pdfs = [link for link in all_pdf_links if link != primary_pdf]
        other_pdfs_text = ', '.join(other_pdfs) if other_pdfs else ''
        self.log(f"Found {len(other_pdfs)} other PDF links")

        # Yield item for CSV
        yield {
            'source_url': response.url,
            'title': title,
            'paragraphs': paragraphs_text,
            'agreement_codes': agreement_codes_text,
            'primary_pdf': primary_pdf,
            'other_pdfs': other_pdfs_text
        }

    def errback(self, failure):
        """
        Handle request failures (e.g., 403, 429).
        """
        self.log(f"Request failed: {failure}")
        if failure.check(scrapy.exceptions.IgnoreRequest):
            self.log(f"Ignored request: {failure.request.url}")
        else:
            self.log(f"Error on {failure.request.url}: {failure.value}")