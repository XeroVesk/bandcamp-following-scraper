# Bandcamp Following Scraper

A Python tool for scraping Bandcamp following lists with comprehensive filtering capabilities. Can be used both as a command-line tool and as a Python module.

## Features

- Scrape complete following lists from any Bandcamp user profile
- Multiple filtering options for refining results
- Support for Firefox and Chrome browsers
- Automatic timeout calculation based on list size
- Comprehensive retry and error handling
- Clean command-line interface with detailed logging

## Requirements

- Python 3.7+
- Selenium WebDriver
- Firefox or Chrome browser
- geckodriver (for Firefox) or chromedriver (for Chrome)

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install selenium
   ```
3. Install browser drivers:
   - For Firefox: Download [geckodriver](https://github.com/mozilla/geckodriver/releases)
   - For Chrome: Download [chromedriver](https://chromedriver.chromium.org/)
   - Ensure drivers are in your PATH or same directory as the script

## Usage

### Basic Usage

```bash
python bandcamp_following_scraper.py username
```

### Browser Options

```bash
# Use Chrome instead of Firefox
python bandcamp_following_scraper.py username --browser chrome

# Run with visible browser (non-headless)
python bandcamp_following_scraper.py username --no-headless
```

### Filtering Options

```bash
# Include only labels containing specific substrings
python bandcamp_following_scraper.py username --substring-include records,music

# Exclude labels containing specific substrings
python bandcamp_following_scraper.py username --substring-exclude test,demo

# Include only specific labels by exact name
python bandcamp_following_scraper.py username --include-only epitaph,victory

# Exclude specific labels by exact name
python bandcamp_following_scraper.py username --exclude spambot,fakemusic

# Complex filtering - combine multiple filters
python bandcamp_following_scraper.py username --substring-include records --substring-exclude demo
```

### Performance Tuning

```bash
# Custom scroll timeout (seconds)
python bandcamp_following_scraper.py username --scroll-timeout 30

# Faster scrolling with shorter delays
python bandcamp_following_scraper.py username --scroll-delay 1

# More retry attempts for unreliable connections
python bandcamp_following_scraper.py username --max-retries 5
```

### Logging Options

```bash
# Verbose logging for debugging
python bandcamp_following_scraper.py username --verbose

# Quiet mode - only show results and errors
python bandcamp_following_scraper.py username --quiet
```

### Advanced Options

```bash
# Custom user agent
python bandcamp_following_scraper.py username --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Custom timeouts for different operations
python bandcamp_following_scraper.py username --page-load-timeout 20 --button-wait-timeout 10
```

## Command Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `username` | string | required | Bandcamp username to scrape |
| `--browser` | choice | firefox | Browser to use (firefox or chrome) |
| `--headless` | flag | True | Run browser in headless mode |
| `--no-headless` | flag | False | Run browser with GUI |
| `--exclude` | string | None | Comma-separated labels to exclude |
| `--include-only` | string | None | Comma-separated labels to include only |
| `--substring-include` | string | None | Comma-separated substrings that must be present |
| `--substring-exclude` | string | None | Comma-separated substrings to exclude |
| `--max-retries` | int | 3 | Maximum number of retry attempts |
| `--request-delay` | float | 2.0 | Delay between retry attempts (seconds) |
| `--page-load-timeout` | int | 10 | Timeout for initial page load (seconds) |
| `--button-wait-timeout` | int | 5 | Timeout for finding view all button (seconds) |
| `--content-load-timeout` | int | 10 | Timeout for content to load after button click (seconds) |
| `--scroll-timeout` | int | auto | Maximum time to spend scrolling (seconds) |
| `--scroll-delay` | float | 2.0 | Wait time between scroll attempts (seconds) |
| `--user-agent` | string | default | Custom user agent string |
| `--verbose` | flag | False | Enable debug logging |
| `--quiet` | flag | False | Suppress info messages |

## Automatic Timeout Calculation

When `--scroll-timeout` is not specified, the script automatically calculates optimal timeout based on the total number of followers using this formula:

```
timeout = ((total_followers - 80) / 40) * scroll_delay * 1.5
```

Examples:
- 281 followers = ~18 seconds
- 645 followers = ~42 seconds  
- 1000 followers = ~46 seconds

## Using as a Python Module

```python
from bandcamp_following_scraper import scrape_bandcamp_following

# Basic usage
labels = scrape_bandcamp_following("username")

# With filtering
labels = scrape_bandcamp_following(
    "username",
    browser="chrome",
    headless=True,
    substring_include_filter=["records"],
    exclude_labels=["spam", "fake"]
)

print(f"Found {len(labels)} labels: {labels}")
```

## Output Format

The script outputs a list of Bandcamp label/artist names in lowercase format:

```
Found 4 labels:
  label1,
  label2,
  label3,
  label4
```

## Error Handling

The script includes comprehensive error handling:

- Automatic retries for transient network failures
- Graceful timeout handling when scroll operations take too long
- Detailed logging for debugging connection issues
- Privacy banner removal for uninterrupted scraping

## Limitations

- Requires following lists to be publicly visible
- Rate limited by Bandcamp's page loading speed
- Large following lists (1000+ items) may take several minutes to complete
- Some browser warnings may appear when using Chrome

## License

MIT License

## Author

Yonah Kho (XeroVesk)
