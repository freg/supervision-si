# assistant-api (livraison #532, item 81) -- PoC assistant IA interne :
# RAG lexical + appels à un serveur de modèle compatible OpenAI (Ollama,
# llama.cpp, vLLM) ; évaluation reproductible. Un seul worker (index en
# mémoire), délais longs (CPU).
FROM python:3.12-slim
WORKDIR /app
COPY assistant/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/app.py assistant/rag.py .
COPY assistant/static/ ./static/
COPY assistant/eval/ ./eval/
COPY shared/version_endpoint.py shared/VERSION.json .
RUN mkdir -p /data /docs
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "app:app"]
