# PORTAIL GOOD ENGINEERS — image de production (Coolify)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=good_engineers_portail.settings

WORKDIR /app

# Pas d'outils de build nécessaires : bcrypt et toutes les dépendances
# s'installent depuis des wheels (pip). Build plus léger et plus fiable.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Dossier de la base SQLite du portail (monté en volume persistant Coolify).
RUN mkdir -p /app/data

EXPOSE 8000

ENV PORTAIL_DB_PATH=/app/data/portail.db

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

# migrate + collectstatic au démarrage, puis gunicorn.
CMD sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn good_engineers_portail.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60"
