FROM python:3.12-slim
WORKDIR /app
COPY geo-catalog/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY geo-catalog/api/app.py .
COPY geo-catalog/api/catalog.py .
COPY geo-catalog/api/refs.py .
COPY geo-catalog/api/store.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "600", "app:app"]
