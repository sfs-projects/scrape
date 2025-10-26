FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only requirements first (better layer caching)
COPY requirements.txt /app/requirements.txt

# Install deps
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the scraper code into the container
COPY . /app

# Run the scraper
# adjust path if main.py is in this same folder (it is)
CMD ["python", "main.py"]
