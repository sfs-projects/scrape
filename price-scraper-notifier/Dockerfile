FROM python:3.10

COPY price-scraper-notifier/requirements.txt .
COPY price-scraper-notifier/main.py .


RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
