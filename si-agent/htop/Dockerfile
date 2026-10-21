# #800 : relais si-htop (UDP signé -> état, constats, historique ; HTTP interne pour le central ; diffusion aux clients)
FROM python:3.12-slim
WORKDIR /app
COPY si-agent/htop/relais.py .
RUN useradd -r -u 10800 htop && mkdir -p /data && chown htop /data
USER htop
EXPOSE 8399/udp 8400
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8400/sante',headers={'X-Htop-Token':os.environ.get('HTOP_JETON_INTERNE','')}),timeout=3)"
CMD ["python", "-u", "relais.py"]
