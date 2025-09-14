
import csv
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import newspaper
from newspaper import Article
from colorama import Fore, Style, init
import os
from urllib.parse import urljoin

# Initialize colorama
init(autoreset=True)

# Configuration
BASE_URL = "https://www.whitehouse.gov/presidential-actions/"
CSV_FILE = "executive_orders.csv"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
RETRIES = 3
INITIAL_DELAY = 1  # seconds

def colored(text, color):
    return f"{color}{text}{Style.RESET_ALL}"

def log(message, level="info"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    colors = {
        "info": Fore.WHITE,
        "error": Fore.RED,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "highlight": Fore.CYAN
    }
    print(f"[{timestamp}] {colored(message, colors.get(level, Fore.WHITE))}")

def get_existing_urls():
    """Returns a set of URLs already present in the CSV file."""
    if not os.path.exists(CSV_FILE):
        return set()
    
    existing_urls = set()
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_urls.add(row['url'])
    except FileNotFoundError:
        pass
    return existing_urls

def fetch_with_retry(url):
    """Fetches a URL with retries and exponential backoff."""
    delay = INITIAL_DELAY
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            log(f"Attempt {attempt+1}/{RETRIES} failed for {url}: {str(e)}", "warning")
            if attempt < RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    log(f"All retries failed for {url}", "error")
    return None

def get_eo_urls():
    """Collects all EO URLs from the paginated list."""
    log("Starting URL collection...")
    eo_urls = []
    current_url = BASE_URL
    existing_urls = get_existing_urls()
    
    while current_url:
        log(f"Processing page: {current_url}")
        response = fetch_with_retry(current_url)
        
        if not response:
            log(f"Skipping page due to fetch failure: {current_url}", "warning")
            break
            
        soup = BeautifulSoup(response.content, 'html.parser')
        # Updated selector for new website structure
        articles = soup.select('li.wp-block-post h2.wp-block-post-title a')
        
        if not articles:
            log("No articles found on page - check CSS selectors!", "error")
            break
            
        new_urls = 0
        for article in articles:
            url = article.get('href')
            if url and url not in existing_urls:
                eo_urls.append(url)
                new_urls += 1
                log(f"Found new Presidential Action: {url}", "highlight")
        
        log(f"Page processed: Found {new_urls} new URLs (Total: {len(eo_urls)})")
        
        # Updated pagination selector for new website structure
        next_link = soup.select_one('a.wp-block-query-pagination-next')
        current_url = urljoin(response.url, next_link['href']) if next_link else None
    
    log(f"Found {len(eo_urls)} new Presidential Action URLs to process", "success")
    return eo_urls

def is_executive_order(soup):
    """Checks if the page is an Executive Order."""
    # Check for Executive Orders in the taxonomy categories
    taxonomy_links = soup.select('.taxonomy-category a')
    for link in taxonomy_links:
        if "executive-orders" in link.get('href', '') or "Executive Orders" in link.get_text():
            return True
    
    # Fallback: check for EXECUTIVE ORDER in the byline (old method)
    byline = soup.find('div', class_='wp-block-whitehouse-topper__meta--byline')
    if byline and "EXECUTIVE ORDER" in byline.get_text().upper():
        return True
    
    # Additional fallback: check title for executive order keywords
    title = soup.find('h1')
    if title and any(keyword in title.get_text().upper() for keyword in ["EXECUTIVE ORDER", "EXECUTIVE ORDER NO"]):
        return True
    
    return False

def process_eo(url, current, total):
    """Processes a single EO URL."""
    log(f"Processing item {current}/{total}: {url}")
    try:
        response = fetch_with_retry(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        article = Article(url)
        article.download()
        article.parse()
        
        return {
            'title': article.title,
            'date_published': article.publish_date,
            'is_eo': str(is_executive_order(soup)).upper(),
            'text': article.text.replace('\n', '\\n').strip(),
            'url': url,
            'scraped_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        log(f"Error processing {url}: {str(e)}", "error")
        return None

def save_to_csv(data):
    """Saves EO data to CSV."""
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'date_published', 'is_eo', 'text', 'url', 'scraped_date']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(data)
    log(f"Saved ({data['is_eo']}): {data['title'][:50]}...", "success")

def main():
    """Main function to orchestrate the scraping process."""
    if not os.path.exists(CSV_FILE):
        log("No existing CSV found - starting fresh scrape", "highlight")
    
    eo_urls = get_eo_urls()
    total = len(eo_urls)
    
    if not eo_urls:
        if os.path.exists(CSV_FILE):
            log("No new Executive Orders found", "warning")
        else:
            log("ERROR: No Executive Orders found - check:", "error")
            log("1. Website structure may have changed", "error")
            log("2. CSS selectors might need updating", "error")
            log("3. Network connection/issues", "error")
        return
    
    log(f"Starting processing of {total} new items")
    stats = {'total': 0, 'eos': 0, 'non_eos': 0}
    
    for idx, url in enumerate(eo_urls, 1):
        eo_data = process_eo(url, idx, total)
        if eo_data:
            save_to_csv(eo_data)
            stats['total'] += 1
            if eo_data['is_eo'] == 'TRUE':
                stats['eos'] += 1
            else:
                stats['non_eos'] += 1
        time.sleep(1)  # Be polite
    
    log("\nScraping complete! Final stats:", "success")
    log(f"Total processed: {stats['total']}")
    log(f"Executive Orders: {stats['eos']}")
    log(f"Non-EO Actions: {stats['non_eos']}")

if __name__ == "__main__":
    main()