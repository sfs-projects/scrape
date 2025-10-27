# ──────────────────────────────
# Base image
# ──────────────────────────────
FROM python:3.10-slim

# System deps (for Playwright Chromium)
RUN apt-get update && apt-get install -y \
    wget \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────
# Install Python dependencies
# ──────────────────────────────
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ──────────────────────────────
# Install Chromium (Playwright)
# ──────────────────────────────
RUN python -m playwright install --with-deps chromium

# ──────────────────────────────
# Copy project code
# ──────────────────────────────
COPY . /app

# ──────────────────────────────
# Run the scraper
# ──────────────────────────────
ENTRYPOINT ["python", "scraper.py"]
