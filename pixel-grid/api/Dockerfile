FROM python:3.12-slim

WORKDIR /app

COPY pixel-grid/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pixel-grid/api/app.py .
COPY pixel-grid/api/name_resolver.py .
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV PIXEL_GRID_DB_PATH=/data/timeseries.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
