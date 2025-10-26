FROM python:3.10-slim

WORKDIR /app

# 1. install system deps needed to build pandas, aiohttp, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. copy requirements first for layer caching
COPY requirements.txt /app/requirements.txt

# 3. install python deps
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# 4. copy the rest of the app
COPY . /app

# 5. run
CMD ["python", "main.py"]
