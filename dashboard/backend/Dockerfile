FROM python:3.12-slim
WORKDIR /app
COPY dashboard/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY dashboard/__init__.py /app/dashboard/__init__.py
COPY dashboard/backend/*.py /app/dashboard/backend/
COPY dashboard/inspection/index.html dashboard/inspection/app.js /app/dashboard/inspection/
CMD ["sh", "-c", "uvicorn dashboard.backend.main:app --host 0.0.0.0 --port ${PORT:-8200} --workers 1"]
