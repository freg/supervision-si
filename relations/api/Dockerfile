FROM python:3.12-slim

WORKDIR /app

COPY relations/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY relations/api/app.py .
COPY relations/api/entity_fetchers.py .
COPY relations/api/relation_engine.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
