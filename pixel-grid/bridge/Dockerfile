FROM python:3.12-slim

WORKDIR /app

COPY pixel-grid/bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pixel-grid/bridge/bridge.py .
COPY shared/log_buffer.py .

CMD ["python", "bridge.py"]
