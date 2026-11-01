# dns-api (livraison #656) -- DNS éditable : OVH / Scaleway (API) et intranet BIND (nsupdate/dig avec TSIG).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends bind9-dnsutils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY dns/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dns/api/app.py dns/api/providers.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN mkdir -p /data
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
