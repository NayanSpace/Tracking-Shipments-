FROM python:3.12-slim

# Install OS-level dependencies for Playwright/Chromium + Xvfb for non-headless Chrome on Linux
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
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
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxss1 \
    xvfb \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers:
#   chromium — used by Day & Ross and Polaris (headless, no Akamai issue)
#   chrome   — Chrome for Testing, used by UPS/FedEx via non-headless + Xvfb
RUN playwright install chromium
RUN playwright install-deps chromium
RUN playwright install chrome

# Copy application code
COPY . .

# Expose API port
EXPOSE 8000

# Start with uvicorn — single worker to stay within 512MB RAM free tier limit
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
