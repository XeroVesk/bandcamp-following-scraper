#!/usr/bin/env python3
"""
Bandcamp Following Scraper

A Python tool for scraping Bandcamp following lists with filtering capabilities.
Can be used both as a command-line tool and as a Python module.

Author: Yonah Kho (XeroVesk)
License: MIT
"""

import re
import time
import logging
import argparse
from functools import wraps

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions

__version__ = "1.0.0"

logger = logging.getLogger(__name__)


def apply_filters(labels, include_only=None, exclude=None, substring_include=None, substring_exclude=None):
    """
    Apply various filters to the labels list.

    Args:
        labels: List of label names to filter
        include_only: List of labels to include exclusively
        exclude: List of labels to exclude
        substring_include: List of substrings that must be present
        substring_exclude: List of substrings to exclude

    Returns:
        List of filtered labels

    Example:
        >>> labels = ['epitaphrecords', 'bridgeninerecords', 'popmusic', 'metalunderground']
        >>> apply_filters(labels, substring_include=['records'])
        ['epitaphrecords', 'bridgeninerecords']
    """
    if not labels:
        return labels

    logger.info(f"Applying filters to {len(labels)} labels")

    # Convert all filter lists to lowercase for case-insensitive matching
    include_only = [item.lower() for item in (include_only or [])]
    exclude = [item.lower() for item in (exclude or [])]
    substring_include = [item.lower() for item in (substring_include or [])]
    substring_exclude = [item.lower() for item in (substring_exclude or [])]

    filtered_labels = []

    for label in labels:
        label_lower = label.lower()

        # Skip if in exclude list
        if label_lower in exclude:
            logger.debug(f"Excluding label (exact match): {label}")
            continue

        # Skip if it doesn't match include_only list (when specified)
        if include_only and label_lower not in include_only:
            logger.debug(f"Excluding label (not in include_only): {label}")
            continue

        # Skip if contains excluded substring
        if any(substr in label_lower for substr in substring_exclude):
            logger.debug(f"Excluding label (substring match): {label}")
            continue

        # Skip if it doesn't contain required substring (when specified)
        if substring_include and not any(substr in label_lower for substr in substring_include):
            logger.debug(f"Excluding label (no required substring): {label}")
            continue

        filtered_labels.append(label)

    logger.info(f"Filtering reduced labels from {len(labels)} to {len(filtered_labels)}")
    return filtered_labels


def retry_on_failure(max_attempts, delay):
    """
    Retry decorator for handling transient failures.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Delay between retry attempts in seconds

    Returns:
        Decorator function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"Attempt {attempt}/{max_attempts} for {func.__name__}")
                    return func(*args, **kwargs)
                except (TimeoutException, WebDriverException) as e:
                    logger.warning(f"Attempt {attempt} failed: {e}")
                    if attempt == max_attempts:
                        logger.error(f"All {max_attempts} attempts failed")
                        raise
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None

        return wrapper

    return decorator


def handle_privacy_policy(driver):
    """
    Remove privacy policy banner by deleting the shadow host element.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        bool: True if banner was removed, False otherwise
    """
    logger.info("Attempting to remove privacy policy banner...")

    try:
        privacy_banner = driver.find_element(By.CSS_SELECTOR, "#propOpenWrapper page-footer")
        driver.execute_script("arguments[0].remove()", privacy_banner)
        logger.info("Successfully removed privacy policy banner")
        return True
    except NoSuchElementException:
        logger.info("No privacy policy banner found to remove")
        return False
    except Exception as e:
        logger.warning(f"Error removing privacy policy banner: {e}")
        return False


def calculate_recommended_scroll_timeout(expected_total, scroll_delay=2, safety_margin=1.5):
    """
        Calculate recommended scroll timeout based on expected total followers.

        Bandcamp loading pattern:
        - Initial load: ~45 items
        - After 'view all' button: +35 items (80 total)
        - Each scroll: +40 items

        Args:
            expected_total: Total number of followers expected
            scroll_delay: Seconds between scroll attempts (default: 2)
            safety_margin: Safety multiplier for timeout (default: 1.5)

        Returns:
            int: Recommended timeout in seconds

        Example:
            calculate_recommended_scroll_timeout(500)
            # Returns: 42
        """
    initial_loaded = 80
    items_per_scroll = 40

    if expected_total <= initial_loaded:
        scrolls_needed = 0
        recommended_timeout = scroll_delay * 2
    else:
        remaining_items = expected_total - initial_loaded
        scrolls_needed = (remaining_items + items_per_scroll - 1) // items_per_scroll
        recommended_timeout = scrolls_needed * scroll_delay

    recommended_timeout = int(recommended_timeout * safety_margin)

    logger.info(f"Auto-calculating timeout: {expected_total} total items, ~{scrolls_needed} scrolls needed")
    logger.info(f"Using scroll timeout: {recommended_timeout} seconds (with {safety_margin}x safety margin)")

    return recommended_timeout


def scroll_to_load_all_content(driver, scroll_timeout=None, scroll_delay=2, expected_total=None):
    """
    Scroll down to trigger infinite scroll loading until no more content loads.

    Args:
        driver: Selenium WebDriver instance
        scroll_timeout: Maximum time to spend scrolling in seconds
        scroll_delay: Wait time between scroll attempts in seconds
        expected_total: Expected total number of items to load
    """
    if scroll_timeout is None:
        if expected_total:
            scroll_timeout = calculate_recommended_scroll_timeout(expected_total, scroll_delay)
        else:
            scroll_timeout = 60
            logger.info(f"No expected total provided, using fallback timeout: {scroll_timeout} seconds")
    else:
        logger.info(f"Using provided scroll timeout: {scroll_timeout} seconds")

    logger.info("Scrolling to load all content...")

    scroll_attempts = 0
    max_scroll_attempts = scroll_timeout // scroll_delay

    while scroll_attempts < max_scroll_attempts:
        if expected_total:
            current_count = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))
            if current_count >= expected_total:
                logger.info(f"Reached expected total: {current_count}/{expected_total}")
                break

        count_before = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))

        artists = driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer")
        if artists:
            last_element = artists[-1]
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'nearest'});", last_element)
            time.sleep(scroll_delay)

            count_after = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))
            if count_after > count_before:
                remaining_attempts = max_scroll_attempts - scroll_attempts - 1
                if expected_total:
                    logger.info(
                        f"Progress: {count_after}/{expected_total} loaded (+{count_after - count_before} new) - {remaining_attempts} attempts left")
                else:
                    logger.info(
                        f"Progress: {count_after} loaded (+{count_after - count_before} new) - {remaining_attempts} attempts left")
                scroll_attempts += 1
                continue

        logger.info(f"No new content loaded after scroll attempt {scroll_attempts + 1}")
        break

    final_count = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))
    if expected_total:
        logger.info(f"Final count after scrolling: {final_count}/{expected_total}")
    else:
        logger.info(f"Final count after scrolling: {final_count}")


def scrape_bandcamp_following(username,
                              max_retries=3,
                              request_delay=2,
                              page_load_timeout=10,
                              button_wait_timeout=5,
                              content_load_timeout=10,
                              scroll_timeout=None,
                              scroll_delay=2,
                              user_agent=None,
                              browser='firefox',  # Added browser parameter with default
                              exclude_labels=None,
                              include_only_labels=None,
                              substring_include_filter=None,
                              substring_exclude_filter=None,
                              headless=False):
    """
    Scrape bandcamp following list for a given username with optional filtering.

    Args:
        username (str): Bandcamp username to scrape
        max_retries (int): Maximum number of retry attempts (default: 3)
        request_delay (float): Delay between retry attempts in seconds (default: 2)
        page_load_timeout (int): Timeout for initial page load in seconds (default: 10)
        button_wait_timeout (int): Timeout for finding 'view all' button in seconds (default: 5)
        content_load_timeout (int): Timeout for content to load after button click in seconds (default: 10)
        scroll_timeout (int): Maximum time to spend scrolling in seconds (default: auto-calculated)
        scroll_delay (float): Wait time between scroll attempts in seconds (default: 2)
        user_agent (str): Custom user agent string
        browser (str): Browser to use ('firefox' or 'chrome', default: 'firefox')
        exclude_labels (list): List of labels to exclude
        include_only_labels (list): List of labels to include (exclusive)
        substring_include_filter (list): List of substrings that must be present
        substring_exclude_filter (list): List of substrings to exclude
        headless (bool): Run browser in headless mode (default: False)

    Returns:
        list: List of bandcamp label names

    Raises:
        ValueError: If username is not a valid string
        TimeoutException: If page fails to load or elements are not found
        WebDriverException: If browser encounters an error

    Example:
        # Basic usage
        labels = scrape_bandcamp_following("myusername", headless=True)
        print(f"Found {len(labels)} labels")
        # Output: Found 42 labels


        # With filtering
        filtered = scrape_bandcamp_following("myusername",
                                           exclude_labels=["midmusic", "fakemusic"],
                                           substring_include_filter=["records"])
        print(filtered)
        # Output: ['epitaphrecords', 'bridgeninerecords', 'victoryrecords']

    Note:
        When scroll_timeout is None (default), the function automatically calculates
        the optimal timeout based on the expected total count from the page.
        Formula: (followers - 80) / 40 * 2 * 1.5
        Examples: 645 followers ≈ 42s, 1000 followers ≈ 46s, 2000 followers ≈ 96s
    """
    if not username or not isinstance(username, str):
        raise ValueError("Username must be a non-empty string")

    username = username.split('/')[-1] if '/' in username else username
    logger.info(f"Starting scrape for user: {username}")

    @retry_on_failure(max_attempts=max_retries, delay=request_delay)
    def _scrape_with_retry():
        if browser.lower() == 'chrome':
            options = ChromeOptions()
            if headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            # Suppress Chrome warnings and errors
            options.add_argument('--disable-logging')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--log-level=3')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_experimental_option('useAutomationExtension', False)

            # Disable various Chrome features that generate warnings
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-component-extensions-with-background-pages')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')

            if user_agent:
                options.add_argument(f'--user-agent={user_agent}')
            else:
                default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                options.add_argument(f'--user-agent={default_ua}')

            driver = webdriver.Chrome(options=options)
        else:  # Default to Firefox
            options = FirefoxOptions()
            if headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            if user_agent:
                options.set_preference("general.useragent.override", user_agent)
            else:
                default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0"
                options.set_preference("general.useragent.override", default_ua)

            driver = webdriver.Firefox(options=options)

        with driver:
            try:
                url = f"https://bandcamp.com/{username}/following/artists_and_labels"
                logger.info(f"Navigating to: {url}")
                driver.get(url)

                handle_privacy_policy(driver)

                try:
                    WebDriverWait(driver, page_load_timeout).until(
                        ec.presence_of_element_located((By.CSS_SELECTOR, ".following-bands .followeer"))
                    )
                    initial_count = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))

                    try:
                        count_element = driver.find_element(
                            By.XPATH,
                            "//span[@class='tab-title'][contains(text(), 'artists & labels')]/span[@class='count']"
                        )
                        total_count = int(count_element.text.strip())
                        logger.info(f"Found {initial_count}/{total_count} followers initially")
                        needs_more_loading = initial_count < total_count
                    except (NoSuchElementException, ValueError) as e:
                        logger.warning(f"Could not determine total count: {e}")
                        total_count = None
                        needs_more_loading = True

                except TimeoutException:
                    logger.warning("No followed artists found or page failed to load")
                    return []

                if needs_more_loading:
                    logger.info(f"Need to load more content ({initial_count}/{total_count or '?'})")
                    try:
                        show_button = WebDriverWait(driver, button_wait_timeout).until(
                            ec.element_to_be_clickable(
                                (By.XPATH,
                                 "//button[contains(text(), 'view all') and contains(text(), 'artists & labels')]"))
                        )
                        logger.info("Found 'view all' button, clicking...")
                        show_button.click()

                        if total_count:
                            try:
                                WebDriverWait(driver, content_load_timeout).until(
                                    lambda d: len(
                                        d.find_elements(By.CSS_SELECTOR, ".following-bands .followeer")) > initial_count
                                )
                                final_count = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))

                                if final_count < total_count:
                                    logger.info(f"Loaded {final_count}/{total_count} items after 'view all'")
                                    logger.info(
                                        f"Remaining {total_count - final_count} items will be loaded via scrolling")
                                else:
                                    logger.info(f"Successfully loaded all content: {final_count}/{total_count}")

                            except TimeoutException:
                                current_count = len(
                                    driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))
                                if current_count <= initial_count:
                                    logger.warning(f"No content loaded after 'view all' button click")
                                else:
                                    logger.info(
                                        f"Loaded {current_count}/{total_count} items after 'view all' (will continue with scrolling)")
                        else:
                            try:
                                WebDriverWait(driver, content_load_timeout).until(
                                    lambda d: len(
                                        d.find_elements(By.CSS_SELECTOR, ".following-bands .followeer")) > initial_count
                                )
                                final_count = len(driver.find_elements(By.CSS_SELECTOR, ".following-bands .followeer"))
                                logger.info(f"Content loaded after 'view all': {final_count} (unknown total)")
                            except TimeoutException:
                                logger.warning("Button clicked but additional content didn't load in time")

                    except TimeoutException:
                        logger.info("No 'view all' button found")
                else:
                    logger.info("All content already loaded, no need for 'view all' button")

                scroll_to_load_all_content(driver, scroll_timeout, scroll_delay, total_count)

                logger.info("Extracting bandcamp URLs...")
                all_links = driver.find_elements(By.TAG_NAME, "a")
                labels = set()

                for link in all_links:
                    href = link.get_attribute("href")
                    if href:
                        match = re.match(r'^https://([^.]+)\.bandcamp\.com/?$', href.strip())
                        if match:
                            label = match.group(1).lower()
                            labels.add(label)
                            logger.debug(f"Found label: {label}")

                raw_labels = sorted(labels)
                logger.info(f"Successfully extracted {len(raw_labels)} unique labels before filtering")

                filter_params = [exclude_labels, include_only_labels, substring_include_filter,
                                 substring_exclude_filter]
                if any(param is not None for param in filter_params):
                    filtered_labels = apply_filters(
                        raw_labels,
                        include_only=include_only_labels,
                        exclude=exclude_labels,
                        substring_include=substring_include_filter,
                        substring_exclude=substring_exclude_filter
                    )
                    return filtered_labels
                else:
                    return raw_labels

            except Exception as e:
                logger.error(f"Unexpected error during scraping: {e}")
                raise

    return _scrape_with_retry()


def main():
    """Main function for command-line interface."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='Scrape Bandcamp following lists with filtering capabilities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bandcamp_following_scraper.py myusername
  python bandcamp_following_scraper.py myusername --no-headless --browser chrome
  python bandcamp_following_scraper.py myusername --exclude spam,fake --substring-include metal
  python bandcamp_following_scraper.py myusername --max-retries 5 --scroll-timeout 120
        """
    )

    parser.add_argument('username', help='Bandcamp username to scrape')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    # Logging options
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress info messages, only show errors and results')

    # Filter options
    parser.add_argument('--exclude', help='Comma-separated labels to exclude')
    parser.add_argument('--include-only', help='Comma-separated labels to include only')
    parser.add_argument('--substring-include', help='Comma-separated substrings that must be present')
    parser.add_argument('--substring-exclude', help='Comma-separated substrings to exclude')

    # Scraping options
    parser.add_argument('--max-retries', type=int, default=3,
                        help='Maximum number of retry attempts (default: 3)')
    parser.add_argument('--request-delay', type=float, default=2.0,
                        help='Delay between retry attempts in seconds (default: 2.0)')
    parser.add_argument('--page-load-timeout', type=int, default=10,
                        help='Timeout for initial page load in seconds (default: 10)')
    parser.add_argument('--button-wait-timeout', type=int, default=5,
                        help='Timeout for finding view all button in seconds (default: 5)')
    parser.add_argument('--content-load-timeout', type=int, default=10,
                        help='Timeout for content to load after button click in seconds (default: 10)')
    parser.add_argument('--scroll-timeout', type=int, default=None,
                        help='Maximum time to spend scrolling in seconds (default: auto-calculated)')
    parser.add_argument('--scroll-delay', type=float, default=2.0,
                        help='Wait time between scroll attempts in seconds (default: 2.0)')
    parser.add_argument('--user-agent', type=str, default=None,
                        help='Custom user agent string')
    parser.add_argument('--browser', choices=['firefox', 'chrome'], default='firefox',
                        help='Browser to use (default: firefox)')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (no GUI, default: True)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                        help='Run browser with GUI (override default headless mode)')

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    def parse_list(value):
        """Parse comma-separated string into list."""
        return [item.strip() for item in value.split(',')] if value else None

    try:
        labels = scrape_bandcamp_following(
            username=args.username,
            max_retries=args.max_retries,
            request_delay=args.request_delay,
            page_load_timeout=args.page_load_timeout,
            button_wait_timeout=args.button_wait_timeout,
            content_load_timeout=args.content_load_timeout,
            scroll_timeout=args.scroll_timeout,
            scroll_delay=args.scroll_delay,
            user_agent=args.user_agent,
            browser=args.browser,
            headless=args.headless,
            exclude_labels=parse_list(args.exclude),
            include_only_labels=parse_list(args.include_only),
            substring_include_filter=parse_list(args.substring_include),
            substring_exclude_filter=parse_list(args.substring_exclude)
        )

        print(f"\nFound {len(labels)} labels:")
        for label in labels:
            print(f"  {label}")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()