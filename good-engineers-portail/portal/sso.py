"""Jeton de bascule (SSO) — émission et vérification.

Le portail signe un petit jeton JWT (HS256) avec le secret PARTAGÉ. Le
module cible le vérifie avec le même secret, contrôle qu'il lui est bien
destiné (claim `aud`), qu'il n'est pas expiré, et qu'il n'a jamais servi
(claim `jti`, usage unique). Il ouvre alors sa propre session.

Durée de vie très courte (60 s par défaut) : le jeton ne sert qu'à franchir
la redirection navigateur portail -> module, jamais à rester en session.
"""
import time
import uuid

import jwt
from django.conf import settings


def mint_token(*, module: str, username: str, role: str, ent_id, modules, display_name=""):
    """Fabrique un jeton pour `module` ('forage' ou 'mine')."""
    now = int(time.time())
    jti = uuid.uuid4().hex
    payload = {
        "iss": settings.SSO_ISSUER,
        "aud": module,
        "sub": str(username),
        "role": str(role or ""),
        "ent": ent_id,                  # entier (forage) ou texte (mine)
        "mods": list(modules),          # modules actifs -> barre de bascule
        "name": display_name or str(username),
        "portal": settings.PORTAIL_BASE_URL,
        "iat": now,
        "nbf": now - 5,
        "exp": now + settings.SSO_TOKEN_TTL_SECONDS,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.SSO_SHARED_SECRET, algorithm="HS256")
    return token, jti


def verify_token(token: str, *, expected_aud: str):
    """Vérifie un jeton reçu (utilisé par les adaptateurs côté app).

    Fourni ici en Python pour référence ; les adaptateurs embarquent leur
    propre version (Node pour Forage, Django pour Mine).
    """
    return jwt.decode(
        token,
        settings.SSO_SHARED_SECRET,
        algorithms=["HS256"],
        audience=expected_aud,
        issuer=settings.SSO_ISSUER,
        options={"require": ["exp", "aud", "iss", "jti", "sub"]},
    )
