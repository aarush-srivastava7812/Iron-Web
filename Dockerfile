FROM falkordb/falkordb:v4.20.7 AS graph
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VOYARA_DATA_PATH=/data \
    FASTEMBED_CACHE_PATH=/data/models \
    COOKIE_SECURE=true \
    DEV_LOGIN_ENABLED=false \
    CONTEXT_USE_GPU=false
ENV USE_GPU=false FALKORDB_PORT=6379

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libsystemd0 libssl3t64 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=graph /usr/local/bin/redis-server /usr/local/bin/redis-server
COPY --from=graph /var/lib/falkordb/bin/falkordb.so /usr/local/lib/falkordb.so

COPY requirements.txt ./
COPY requirements/ ./requirements/
COPY stitch_ai_travel_booking_platform/backend/requirements.txt ./stitch_ai_travel_booking_platform/backend/requirements.txt
RUN pip install -r requirements.txt -r requirements/application.txt -r requirements/nim.txt

COPY config.yaml ./
COPY memory/ ./memory/
COPY Iron_Web_2/memory/ ./Iron_Web_2/memory/
COPY agents/ ./agents/
COPY stitch_ai_travel_booking_platform/backend/ ./stitch_ai_travel_booking_platform/backend/
COPY stitch_ai_travel_booking_platform/transitions/ ./stitch_ai_travel_booking_platform/transitions/
COPY deploy/voyara/start.py ./deploy/voyara/start.py

CMD ["python", "deploy/voyara/start.py"]
