"""Appels sortants du portail vers les deux applications.

Deux usages :
  1. Rapport consolidé : lire les métriques d'une entreprise sur une période.
  2. Propagation d'état : quand on (dé)coche un module, dire à l'application
     d'activer / désactiver l'entreprise (sécurité en plus du SSO).

Tous les appels portent l'en-tête X-Service-Key (clé de service partagée) et
sont « best effort » : une application injoignable ne doit jamais casser
l'enregistrement d'une entreprise ni le rapport.
"""
import logging

import requests
from django.conf import settings

log = logging.getLogger("portail.services")

_HEADERS = {"X-Service-Key": settings.SERVICE_API_KEY}


# --------------------------------------------------------------------------
# 1. Métriques (rapport consolidé)
# --------------------------------------------------------------------------
def fetch_forage_metrics(enterprise_id, start, end):
    url = f"{settings.FORAGE_BASE_URL}/api/service/metrics"
    params = {"enterpriseId": enterprise_id, "start": start, "end": end}
    try:
        r = requests.get(url, params=params, headers=_HEADERS,
                         timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:  # noqa: BLE001
        log.warning("Forage metrics KO: %s", e)
        return None, str(e)


def fetch_mine_metrics(tenant_id, start, end):
    url = f"{settings.MINE_BASE_URL}/api/service/metrics/"
    params = {"tenant": tenant_id, "start": start, "end": end}
    try:
        r = requests.get(url, params=params, headers=_HEADERS,
                         timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:  # noqa: BLE001
        log.warning("Mine metrics KO: %s", e)
        return None, str(e)


# --------------------------------------------------------------------------
# 2. Propagation d'état d'un module (activation / détachement)
# --------------------------------------------------------------------------
def propager_etat_forage(enterprise_id, active: bool):
    if enterprise_id is None:
        return
    url = f"{settings.FORAGE_BASE_URL}/api/service/module-state"
    _post_state(url, {"enterpriseId": enterprise_id, "active": bool(active)}, "Forage")


def propager_etat_mine(tenant_id, active: bool):
    if not tenant_id:
        return
    url = f"{settings.MINE_BASE_URL}/api/service/module-state/"
    _post_state(url, {"tenant": tenant_id, "active": bool(active)}, "Mine")


def creer_entreprise_forage(nom, slug):
    """Crée (ou retrouve) l'entreprise dans Forage. Renvoie (enterpriseId, erreur)."""
    url = f"{settings.FORAGE_BASE_URL}/api/service/enterprise"
    try:
        r = requests.post(url, json={"name": nom, "slug": slug}, headers=_HEADERS,
                          timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("id"), None
    except Exception as e:  # noqa: BLE001
        log.warning("Création entreprise Forage KO (%s): %s", nom, e)
        return None, str(e)


def creer_entreprise_mine(nom, slug):
    """Crée (ou retrouve) le tenant dans la Mine. Renvoie (tenant, erreur)."""
    url = f"{settings.MINE_BASE_URL}/api/service/enterprise/"
    try:
        r = requests.post(url, json={"name": nom, "tenant": slug}, headers=_HEADERS,
                          timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("tenant"), None
    except Exception as e:  # noqa: BLE001
        log.warning("Création entreprise Mine KO (%s): %s", nom, e)
        return None, str(e)


def creer_user_forage(enterprise_id, username, password, role):
    """Crée/maj le compte dans l'app Forage. Renvoie (ok, erreur)."""
    if enterprise_id is None:
        return False, "entreprise Forage non reliée"
    url = f"{settings.FORAGE_BASE_URL}/api/service/user"
    body = {"enterpriseId": enterprise_id, "username": username,
            "password": password, "role": role, "name": username}
    return _post_user(url, body, "Forage")


def creer_user_mine(tenant_id, username, password, role):
    """Crée/maj le compte dans l'app Mine. Renvoie (ok, erreur)."""
    if not tenant_id:
        return False, "tenant Mine non relié"
    url = f"{settings.MINE_BASE_URL}/api/service/user/"
    body = {"tenant": tenant_id, "username": username,
            "password": password, "role": role}
    return _post_user(url, body, "Mine")


def _post_user(url, body, label):
    try:
        r = requests.post(url, json=body, headers=_HEADERS,
                          timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
        return True, None
    except Exception as e:  # noqa: BLE001
        log.warning("Création compte %s KO (%s): %s", label, body.get("username"), e)
        return False, str(e)


def _post_state(url, body, label):
    try:
        r = requests.post(url, json=body, headers=_HEADERS,
                          timeout=settings.METRICS_HTTP_TIMEOUT)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        # Non bloquant : le SSO refuse déjà l'accès à un module décoché.
        log.warning("Propagation état %s KO (%s): %s", label, body, e)
