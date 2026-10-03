# groupware-api (livraison #664) -- noyau groupware : partages, catégories, liens, préférences, droits Radicale.
FROM python:3.12-slim
WORKDIR /app
COPY groupware/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY groupware/api/app.py groupware/api/core.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN mkdir -p /data /dav-config
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "60", "app:app"]
