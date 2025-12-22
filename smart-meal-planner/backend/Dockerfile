# Dockerfile for Backend

# Stage 1: Build the application and install all dependencies
FROM python:3.12-slim as builder

WORKDIR /app

# Install build-time system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    # Playwright dependencies
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
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
# The --with-deps flag is crucial to install browser binaries
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# Copy application code
COPY . .


# Stage 2: Create the final, smaller image
FROM python:3.12-slim

WORKDIR /app

# Install runtime system dependencies
# Use libpq5 for runtime, not the -dev package
RUN apt-get update && apt-get install -y \
    libpq5 \
    # Playwright dependencies
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
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy Playwright browser from the builder stage
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Set the PLAYWRIGHT_BROWSERS_PATH environment variable
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
