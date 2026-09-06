FROM python:3.12-slim
WORKDIR /app
COPY owncloud/search-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY owncloud/search-api/app.py .
COPY shared/log_buffer.py .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
