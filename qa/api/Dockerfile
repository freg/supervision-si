# qa-api (livraison #651) -- scénarios joués dans Chromium : image Playwright officielle (navigateurs et dépendances inclus).
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY qa/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY qa/api/app.py qa/api/qa_steps.py qa/api/qa_design.py qa/api/qa_visual.py qa/api/runner.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN mkdir -p /data
EXPOSE 5000
# UN worker, plusieurs threads : une exécution Playwright est synchrone et borne son délai par étape (QA_STEP_TIMEOUT_MS).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "app:app"]
