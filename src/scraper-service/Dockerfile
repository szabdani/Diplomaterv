FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUNNING_IN_DOCKER=true \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DISPLAY=:99

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/scraper-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/scraper-service ./src/scraper-service

# Purge old Xvfb lock files, run Xvfb in the background, then execute main.py
CMD ["sh", "-c", "rm -f /tmp/.X99-lock && Xvfb :99 -screen 0 1920x1080x24 & python src/scraper-service/main.py"]