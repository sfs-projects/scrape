# ──────────────────────────────
# Base image
# ──────────────────────────────
FROM python:3.10-slim

# ──────────────────────────────
# Install system dependencies required for Playwright Chromium
# ──────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
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
# Set working directory
# ──────────────────────────────
WORKDIR /app

# ──────────────────────────────
# Copy only requirements first (to leverage Docker layer caching)
# ──────────────────────────────
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ──────────────────────────────
# Install Playwright Chromium only once (cached layer)
# ──────────────────────────────
RUN python -m playwright install --with-deps chromium

# ──────────────────────────────
# Copy the rest of the project (changes here won’t bust dependency cache)
# ──────────────────────────────
COPY . /app

# ──────────────────────────────
# Default entry point
# ──────────────────────────────
ENTRYPOINT ["python", "main.py"]
