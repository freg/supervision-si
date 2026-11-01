FROM python:3.12-slim
WORKDIR /app
COPY messages/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY messages/api/app.py .
COPY messages/api/store.py .
COPY si-proxy/admin/auth.py .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
