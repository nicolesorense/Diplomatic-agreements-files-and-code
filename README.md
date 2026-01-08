# TIAS Scraper

A Scrapy-based web scraper designed to extract diplomatic agreement links and their associated PDF documents from the U.S. State Department website (https://www.state.gov/). This project includes two spiders: `tias_links_spider.py` to collect agreement URLs and `tias_pdf_spider.py` to download or extract content from those URLs.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features
- Extracts agreement links (e.g., `https://www.state.gov/denmark-25-204`) from yearly TIAS pages.
- Downloads or extracts content (e.g., PDFs) from the collected links.
- Uses Playwright for JavaScript-rendered page handling.
- Includes random user agent rotation and delay to avoid anti-scraping measures.
- Saves results to CSV and HTML for debugging.

## Requirements
- Python 3.8+
- The following Python packages (listed in `requirements.txt`):
  - `scrapy==2.8.0`
  - `scrapy-playwright==0.0.41`
  - `pandas==2.2.3`
- Playwright browser binaries (installed via `playwright install`).
- Access to a terminal and Git.

## Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/nicolesorense/diplomatic-agreements.git
   cd diplomatic-agreements
   ```

2. **Set Up a Virtual Environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   - Install required Python packages:
     ```bash
     pip install -r requirements.txt
     ```
   - Install Playwright browsers:
     ```bash
     playwright install
     ```

4. **Fix Project Structure** (if needed):
   - The `scrapy.cfg` file must be in the root directory (not inside `tias_scraper/`).
   - If `scrapy.cfg` is inside `tias_scraper/`, move it:
     ```bash
     mv tias_scraper/scrapy.cfg .
     ```

## Configuration
- **Settings**: Edit `tias_scraper/settings.py` to customize behavior:
  - Adjust `DOWNLOAD_DELAY` (default: 45 seconds) or `CONCURRENT_REQUESTS` (default: 1) based on your needs.
  - Add proxies under `PROXIES` if facing 403/429 errors:
    ```python
    DOWNLOADER_MIDDLEWARES.update({
        'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
    })
    PROXIES = ['http://your-proxy:port']
    ```
- **Treaty Years**: The spider uses `treaty_years.csv` (fetched from https://raw.githubusercontent.com/nicolesorense/diplomatic-agreements/refs/heads/main/treaty_years.csv). Update this file locally if needed.

## Usage
### Step 1: Extract Agreement Links
1. Run the `tias_links_spider` to collect agreement URLs:
   ```bash
   scrapy crawl tias_links_spider -a max_years=1
   ```
   - The `-a max_years=1` argument limits the spider to the most recent year (e.g., 2025). Omit or increase to process more years.
   - Output is saved to `all_extracted_links.csv`.

2. Verify the output:
   - Check `all_extracted_links.csv` for URLs (e.g., `https://www.state.gov/denmark-25-204`).
   - Debug HTML is saved to `debug_html/2025-tias.html`.

### Step 2: Download or Extract PDFs
1. Prepare the input file:
   ```bash
   awk -F',' 'NR>1 {print $1}' all_extracted_links.csv > urls.txt
   ```
   - This creates `urls.txt` with one URL per line.

2. Run the `tias_pdf_spider` to process the URLs:
   ```bash
   scrapy crawl tias_pdf_spider -a urls_file=urls.txt
   ```
   - Output (e.g., PDFs or text) is saved to `tias_scraped_data.csv`

### Notes
- The spiders include a 45-second `DOWNLOAD_DELAY` and use Playwright to handle dynamic content. Expect runs to take time.
- Logs are set to DEBUG level; review them for issues (e.g., timeouts, 403 errors).

## Project Structure
```
diplomatic-agreements/
├── scrapy.cfg                              # Scrapy configuration (must be at root level)
├── requirements.txt                        # Python dependencies
├── README.md
├── treaty_years.csv                        # Input data for treaty years
├── tias_links_spider.py                    # Spider source (reference copy)
├── tias_pdf_spider.py                      # Spider source (reference copy)
├── Copy of Updated_states_and_organizations...  # Supporting data
├── tias_scraped_data.csv                   # Output from PDF spider
├── tias_scraper/                           # Scrapy project package
│   ├── __init__.py
│   ├── settings.py
│   ├── middlewares.py
│   ├── items.py
│   ├── pipelines.py
│   └── spiders/
│       ├── __init__.py
│       ├── tias_links_spider.py
│       └── tias_pdf_spider.py
├── urls.txt                                # Generated URL list (after Step 1)
├── all_extracted_links.csv                 # Generated links (after Step 1)
└── debug_html/                             # Debug HTML files
```

**Important**: The `scrapy.cfg` file must be at the root level of the project for Scrapy to recognize the project. If you see "no active project" errors, ensure `scrapy.cfg` is not inside the `tias_scraper/` folder.

## Troubleshooting
- **"No active project" or "Unknown command: crawl"**: 
  - Make sure you're in the `diplomatic-agreements/` directory (not inside `tias_scraper/`).
  - Ensure `scrapy.cfg` is at the root level, not inside `tias_scraper/`.
  - Run `scrapy list` to verify spiders are detected.
- **ModuleNotFoundError: No module named 'tias_scraper'**:
  - Move `scrapy.cfg` to the root directory: `mv tias_scraper/scrapy.cfg .`
- **Timeout Errors**: Increase `PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT` in `settings.py` or add scrolling triggers in `start_requests`:
  ```python
  PageMethod('evaluate', 'window.scrollTo(0, document.body.scrollHeight)'),
  PageMethod('wait_for_timeout', 2000),
  ```
- **403/429 Errors**: Add a proxy as described in [Configuration](#configuration).
- **No Links Extracted**: Verify `debug_html/2025-tias.html` contains `<ul class="collection-results">`. Adjust selectors in `tias_links_spider.py` if needed.
- **No PDFs Downloaded**: Check the target URLs (e.g., `https://www.state.gov/denmark-25-204`) manually for content type (PDF or HTML).
