# assistant-api (livraison #532, item 81) -- PoC assistant IA interne :
# RAG lexical + appels à un serveur de modèle compatible OpenAI (Ollama,
# llama.cpp, vLLM) ; évaluation reproductible. Un seul worker (index en
# mémoire), délais longs (CPU).
# Étape 1 (#534) : documentation du dépôt indexée par l'assistant --
# README de chaque module (renommé <module>.md), README, CHANGELOG, BACKLOG.
# Seul /repo-docs passe dans l'image finale (jamais .env ni le reste).
FROM python:3.12-slim AS repodocs
COPY . /ctx
RUN mkdir -p /repo-docs && cp /ctx/README.md /ctx/CHANGELOG.md /ctx/BACKLOG.md /repo-docs/ 2>/dev/null; \
    for f in /ctx/*/README.md; do d=$(basename "$(dirname "$f")"); cp "$f" "/repo-docs/$d.md"; done; \
    ls /repo-docs | wc -l

FROM python:3.12-slim
WORKDIR /app
COPY assistant/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/app.py assistant/rag.py .
COPY assistant/static/ ./static/
COPY assistant/eval/ ./eval/
COPY shared/version_endpoint.py shared/VERSION.json .
COPY --from=repodocs /repo-docs /repo-docs
RUN mkdir -p /data /docs
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "app:app"]
