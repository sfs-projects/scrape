[![CI/CD Workflow](https://github.com/sfs-projects/scrape/actions/workflows/deploy-docker.yaml/badge.svg)](https://github.com/sfs-projects/scrape/actions/workflows/deploy-docker.yaml)

# Price Scraper Notifier
A Python project that scrapes and processes data using async aiohttp requests and pandas, then sends alerts to Telegram based on price changes. The scraping tags are taken from a spreadsheet, making the process dynamic. This project uses GitHub Actions and Docker for automation.

## Description
This project is designed to scrape and process data from various sources using async aiohttp requests and pandas. The scraping tags for the data are stored in a spreadsheet, allowing for flexibility and ease of updating. The processed data is then analyzed for any changes in prices, and alerts are sent to a Telegram group chat. The project is automated using GitHub Actions and Docker.

## Technologies Used
- Python 3.10 or higher
- aiohttp
- pandas
- GitHub Actions
- Docker
