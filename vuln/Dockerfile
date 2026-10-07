# vuln-api (livraison #688) -- SBOM (syft) → OSV (osv-scanner) → priorisation EPSS + KEV → Dependency-Track (option).
FROM python:3.12-slim
ARG SYFT_VERSION=1.40.0
ARG OSV_SCANNER_VERSION=2.6.0
ARG TARGETARCH=amd64
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* \
 && A="${TARGETARCH:-amd64}" \
 && curl -fsSL -o /tmp/syft.tgz "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_${A}.tar.gz" \
 && tar -xzf /tmp/syft.tgz -C /usr/local/bin syft && rm /tmp/syft.tgz \
 && if [ "$OSV_SCANNER_VERSION" = "latest" ]; then U="https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_${A}"; \
    else U="https://github.com/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}/osv-scanner_linux_${A}"; fi \
 && curl -fsSL -o /usr/local/bin/osv-scanner "$U" && chmod +x /usr/local/bin/osv-scanner \
 && syft version && osv-scanner --version
WORKDIR /app
COPY vuln/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vuln/app.py vuln/vulnlib.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN mkdir -p /data/sboms
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "1800", "app:app"]
