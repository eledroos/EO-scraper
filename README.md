# White House Executive Order Scraper
By [Nasser Eledroos](https://nasser.wiki/)
A Python script to scrape and archive Executive Orders from [WhiteHouse.gov/presidential-actions](https://www.whitehouse.gov/presidential-actions/).

## Features
- Automatically detects new Executive Orders
- Saves data to CSV with timestamps
- Color-coded command line output
- Error handling with retries
- Tracks progress and final statistics

## Installation

1. **Install Python** (3.6 or newer required)
2. **Install dependencies**:
   ```bash
   pip install requests beautifulsoup4 newspaper4k colorama python-dateutil
   ```

## Usage

```bash
python scraper.py
```

- First run: Creates `executive_orders.csv`
- Subsequent runs: Only adds new Executive Orders
- Output includes:
  - EO titles and dates
  - Full text (preserves formatting)
  - Verification status (TRUE/FALSE)
  - Scraped timestamps

## License

MIT License. Free to use and modify. Include license notice if redistributed.  
See [LICENSE](LICENSE) for details.