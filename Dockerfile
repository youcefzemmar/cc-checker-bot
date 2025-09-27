# Use official Python slim image
FROM python:3.10-slim

# Install all Playwright/Chromium system dependencies (including the missing ones)
RUN apt-get update && \
    apt-get install -y \
        wget \
        gnupg \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libxshmfence1 \
        libx11-xcb1 \
        libgtk-3-0 \
        libgtk-4-1 \
        libgraphene-1.0-0 \
        libgstgl-1.0-0 \
        libgstcodecparsers-1.0-0 \
        libenchant-2-2 \
        libsecret-1-0 \
        libmanette-0.2-0 \
        libgles2 \
        fonts-liberation \
        libappindicator3-1 \
        libu2f-udev \
        xdg-utils \
        libgbm-dev \
        libgdk-pixbuf2.0-0 \
        libxss1 \
        libgconf-2-4 \
        libxtst6 \
        libxinerama1 \
        lsb-release \
        && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN python -m playwright install

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
