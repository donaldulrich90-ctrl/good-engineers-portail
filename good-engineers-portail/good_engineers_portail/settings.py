"""Configuration Django — PORTAIL GOOD ENGINEERS.

Le portail est un service distinct, posé AU-DESSUS des applications
Forage (DRILLING-GE) et Mine (GOOD ENGINEERS OS / GEMINING-1).
Il ne touche pas à leur code : il gère les entreprises, les modules
activés, la connexion unique (SSO) et le rapport consolidé.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("PORTAIL_SECRET_KEY", "dev-change-me-en-production")
DEBUG = os.environ.get("PORTAIL_DEBUG", "0") == "1"

ALLOWED_HOSTS = ["*"]
_env_hosts = os.environ.get("PORTAIL_ALLOWED_HOSTS", "").strip()
if _env_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _env_hosts.split(",") if h.strip()]

# Derrière le reverse-proxy de Coolify : cookies + CSRF corrects.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("PORTAIL_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "portal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "good_engineers_portail.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "good_engineers_portail.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Base propre au portail (entreprises, comptes, mapping). Volume Coolify.
        "NAME": os.environ.get("PORTAIL_DB_PATH", str(BASE_DIR / "data" / "portail.db")),
    }
}

# --- Mots de passe --------------------------------------------------------
# bcrypt par défaut. Le hasher « legacy » reconnaît l'ancien SHA-256 non salé
# de la Mine (hérité de Streamlit) : un compte importé s'authentifie puis est
# ré-haché en bcrypt automatiquement à la connexion suivante. Personne n'a
# besoin de changer son mot de passe.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "portal.hashers.LegacyMineSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

SESSION_COOKIE_NAME = "portail_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =========================================================================
# CONNEXION UNIQUE (SSO) ET RAPPORT CONSOLIDÉ
# =========================================================================
# Secret PARTAGÉ entre le portail et les deux applications. Il signe le jeton
# de bascule. À définir à l'identique dans DRILLING-GE et GEMINING-1.
SSO_SHARED_SECRET = os.environ.get("SSO_SHARED_SECRET", "dev-sso-secret-change-me")
SSO_TOKEN_TTL_SECONDS = int(os.environ.get("SSO_TOKEN_TTL_SECONDS", "60"))
SSO_ISSUER = "portail-ge"

# Clé de service pour interroger les API métriques des deux apps (rapport).
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "dev-service-key-change-me")

# URLs publiques des modules (utilisées pour la bascule et le rapport).
FORAGE_BASE_URL = os.environ.get("FORAGE_BASE_URL", "https://gedrilling.duckdns.org").rstrip("/")
MINE_BASE_URL = os.environ.get("MINE_BASE_URL", "https://gemining.duckdns.org").rstrip("/")

# URL publique du portail lui-même (injectée dans la barre de bascule).
PORTAIL_BASE_URL = os.environ.get("PORTAIL_BASE_URL", "https://geportail.duckdns.org").rstrip("/")

# Délai d'appel aux API métriques (secondes).
METRICS_HTTP_TIMEOUT = int(os.environ.get("METRICS_HTTP_TIMEOUT", "20"))
