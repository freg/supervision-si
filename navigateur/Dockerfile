# Navigateur de l'hôte (#798) : Chromium visible dans un écran virtuel, vu et utilisé depuis le hub (noVNC), et piloté
# en même temps par Playwright (CDP) pour la QA, le rejeu des parcours et les demandes en langage courant.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      xvfb x11vnc novnc websockify fluxbox fonts-dejavu fonts-noto-color-emoji locales \
    && sed -i 's/^# *fr_FR.UTF-8/fr_FR.UTF-8/' /etc/locale.gen && locale-gen \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /profil /app && chown pwuser:pwuser /profil
ENV LANG=fr_FR.UTF-8 LANGUAGE=fr_FR:fr PYTHONUNBUFFERED=1
COPY automate.py entrypoint.sh /app/
RUN chmod 755 /app/entrypoint.sh
USER pwuser
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
