"""ADAPTATEUR MINE (GEMINING-1) — connexion unique (SSO) depuis le portail.

À déposer dans GEMINING-1 (ex: webcore/ge_sso_views.py) et à brancher dans
good_engineers_os/urls.py (voir urls-snippet.txt).

Route GET /sso/?token=... :
  - vérifie le jeton signé par le portail (secret PARTAGÉ SSO_SHARED_SECRET),
  - contrôle qu'il est destiné à "mine" et qu'il n'a jamais servi (usage unique),
  - charge le compte depuis le gestionnaire d'utilisateurs de la Mine,
  - remplit la session (ge_user, ge_tenant) EXACTEMENT comme login_view,
  - mémorise la config de la barre de bascule (ge_switchbar),
  - redirige vers le tableau de bord.

L'ancienne page /login/ reste disponible comme secours.
"""
import os

import jwt
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse

from core.auth import get_user_manager
from core import storage

SSO_SHARED_SECRET = os.environ.get("SSO_SHARED_SECRET", "")


def sso_login(request):
    token = request.GET.get("token", "")
    if not token:
        return _refus(request, "Jeton manquant.")
    if not SSO_SHARED_SECRET:
        return _refus(request, "SSO non configuré (SSO_SHARED_SECRET).")

    try:
        payload = jwt.decode(
            token, SSO_SHARED_SECRET, algorithms=["HS256"],
            audience="mine", issuer="portail-ge",
            options={"require": ["exp", "aud", "iss", "jti", "sub"]},
        )
    except Exception:  # noqa: BLE001
        return _refus(request, "Jeton invalide ou expiré.")

    jti = payload.get("jti")
    cache_key = f"ge_sso_jti:{jti}"
    if not jti or cache.get(cache_key):
        return _refus(request, "Jeton déjà utilisé.")
    # Marqué consommé jusqu'à l'expiration (usage unique).
    import time
    ttl = max(1, int(payload.get("exp", 0) - time.time()) + 5)
    cache.set(cache_key, 1, ttl)

    username = str(payload.get("sub") or "")
    tenant = storage.safe_tenant_id(payload.get("ent") or "default")

    user = get_user_manager().get_user(username)
    if not user:
        return _refus(request, "Compte Mine introuvable.")

    # Session identique à login_view.
    request.session["ge_user"] = user
    request.session["ge_tenant"] = tenant

    # Config de la barre de bascule (lue par base.html).
    request.session["ge_switchbar"] = {
        "portal": payload.get("portal", ""),
        "current": "mine",
        "modules": payload.get("mods", ["mine"]),
        "enterprise": payload.get("name", ""),
    }

    if user.get("role") == "Gestionnaire":
        return redirect("console")
    return redirect(reverse("dashboard"))


def _refus(request, message):
    from django.http import HttpResponseForbidden
    return HttpResponseForbidden(f"SSO refusé : {message}")
