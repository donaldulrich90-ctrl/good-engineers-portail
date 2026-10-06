"""Hasher « legacy » pour convertir les comptes de la Mine sans friction.

L'ancienne application Mine (héritée de Streamlit) stocke les mots de passe
en SHA-256 NON salé, après une normalisation NFKC (voir core/security.py
dans GEMINING-1). Ce hasher permet au portail de reconnaître ces mots de
passe tels quels, le temps que Django les ré-hache en bcrypt.

Fonctionnement :
  1. On importe un compte Mine dans le portail en stockant son mot de passe
     sous la forme :  legacy_mine_sha256$<sha256_hex>
     (voir la commande d'import importer_mine dans management/commands).
  2. À la première connexion réussie, comme ce hasher n'est pas le premier
     de PASSWORD_HASHERS, Django ré-hache automatiquement le mot de passe
     avec bcrypt. Le champ en base passe tout seul en bcrypt.

L'utilisateur ne change jamais son mot de passe.
"""
import hashlib
import unicodedata

from django.contrib.auth.hashers import BasePasswordHasher
from django.utils.crypto import constant_time_compare

_DASH_CHARS = ("‐", "‑", "‒", "–", "—",
               "−", "－", "­")


def _normalize(value: str) -> str:
    """Même normalisation que l'ancienne app Mine (tirets spéciaux, espaces)."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip()
    for ch in _DASH_CHARS:
        s = s.replace(ch, "-")
    return s


def mine_sha256(raw_password: str) -> str:
    """SHA-256 compatible avec app_database.json de la Mine."""
    return hashlib.sha256(_normalize(raw_password).encode("utf-8")).hexdigest()


class LegacyMineSHA256PasswordHasher(BasePasswordHasher):
    algorithm = "legacy_mine_sha256"

    def encode(self, password, salt=None, **kwargs):
        # Pas de sel : c'est tout l'intérêt de la compatibilité ascendante.
        return "%s$%s" % (self.algorithm, mine_sha256(password))

    def decode(self, encoded):
        algorithm, digest = encoded.split("$", 1)
        assert algorithm == self.algorithm
        return {"algorithm": algorithm, "hash": digest, "salt": None}

    def verify(self, password, encoded):
        _, digest = encoded.split("$", 1)
        return constant_time_compare(mine_sha256(password), digest)

    def safe_summary(self, encoded):
        _, digest = encoded.split("$", 1)
        return {"algorithm": self.algorithm, "hash": digest[:6] + "…"}

    def harden_runtime(self, password, encoded):
        # Rien à faire : la conversion vers bcrypt est gérée par Django.
        pass
