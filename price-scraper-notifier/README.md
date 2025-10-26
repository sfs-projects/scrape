[![CI/CD Workflow](https://github.com/sfs-projects/scrape/actions/workflows/price-scraper-pipeline.yaml/badge.svg)](https://github.com/sfs-projects/scrape/actions/workflows/price-scraper-pipeline.yaml)

# Price Scraper Notifier
A Python project that scrapes and processes data using asyncio, aiohttp requests, BeautifulSoup and pandas, then sends alerts to Telegram based on price changes. The scraping tags are taken from a spreadsheet, making the process dynamic. This project uses GitHub Actions and Docker for automation.

## Features
- Scrapes data from various sources using async aiohttp requests and pandas
- Processes the scraped data and analyzes for price changes
- Sends alerts to a Telegram group chat
- Automated using GitHub Actions and Docker

## Technologies Used
- [Python](https://www.python.org/) 3.8 or higher
- [asyncio](https://docs.python.org/3/library/asyncio.html) - Asynchronous I/O framework for Python
- [aiohttp](https://aiohttp.readthedocs.io/en/stable/) - Asynchronous HTTP client/server for asyncio and Python
- [pandas](https://pandas.pydata.org/) - Data manipulation and analysis tool
- [GitHub Actions](https://docs.github.com/en/actions) - Automation platform for GitHub
- [Docker](https://www.docker.com/) - Containerization platform
