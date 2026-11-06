# Démonstration automatisée du hub (#982) : Chromium + Playwright (image officielle), python-pptx pour la présentation.
# Construite et lancée par scripts/demo.sh (jamais un service permanent).
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy
RUN pip install --no-cache-dir python-pptx==1.0.2 Pillow
WORKDIR /demo
COPY demo/demo_lib.py demo/tour.py demo/build.py ./
COPY demo/parcours/ ./parcours/
ENV HOME=/tmp
ENTRYPOINT ["python3", "tour.py"]
