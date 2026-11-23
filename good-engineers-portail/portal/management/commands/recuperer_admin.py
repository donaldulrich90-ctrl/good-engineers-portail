"""Récupération de l'accès super-administrateur du portail.

But : permettre de regagner l'accès propriétaire du portail par un simple
redéploiement, sans terminal ni manipulation de variable d'environnement.

Comportement au démarrage (appelée depuis le Dockerfile après `migrate`) :

1. Si ``RESET_PORTAL_ADMIN`` est défini (≠ off/vide) OU ``PORTAL_ADMIN_PASSWORD``
   fourni : le mot de passe du compte ``proprietaire`` (ou ``PORTAL_ADMIN_USERNAME``)
   est (re)défini. La valeur de ``RESET_PORTAL_ADMIN`` sert de mot de passe si ce
   n'est pas un simple drapeau (1/true/on/yes) ; sinon on prend
   ``PORTAL_ADMIN_PASSWORD`` puis, à défaut, le mot de passe de secours.

2. Sinon : réinitialisation AUTOMATIQUE, UNE SEULE FOIS, vers un mot de passe de
   secours connu, tant qu'un marqueur n'existe pas sur le volume de données.
   Une fois appliquée, elle n'est plus jamais rejouée (le marqueur est écrit)
   et n'écrase donc pas un mot de passe changé ensuite.

N'altère aucune donnée métier : crée/met à jour le seul compte administrateur.
Le mot de passe de secours DOIT être changé immédiatement après connexion.
"""
import os
import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

RECOVERY_USERNAME = "proprietaire"
RECOVERY_PASSWORD = "GEDrilling2026"
_FLAG_VALUES = {"1", "true", "on", "yes"}


class Command(BaseCommand):
    help = "Crée ou réinitialise le super-administrateur du portail (récupération d'accès)."

    def _marker_path(self) -> Path:
        db_path = os.environ.get("PORTAIL_DB_PATH", "")
        base = os.path.dirname(db_path) if db_path else str(getattr(settings, "BASE_DIR", ".") )
        return Path(base) / ".portal_admin_reset_v1"

    def _upsert_admin(self, username: str, password: str) -> str:
        User = get_user_model()
        user = User.objects.filter(username__iexact=username).first()
        created = user is None
        if user is None:
            user = User(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        return "créé" if created else "réinitialisé"

    def handle(self, *args, **options):
        username = (os.environ.get("PORTAL_ADMIN_USERNAME") or RECOVERY_USERNAME).strip() or RECOVERY_USERNAME
        env_pwd = (os.environ.get("PORTAL_ADMIN_PASSWORD") or "").strip()
        reset_flag = (os.environ.get("RESET_PORTAL_ADMIN") or "").strip()

        # (1) Réinitialisation pilotée par variable d'environnement.
        if (reset_flag and reset_flag.lower() != "off") or env_pwd:
            if reset_flag and reset_flag.lower() not in _FLAG_VALUES and reset_flag.lower() != "off":
                password = reset_flag  # la valeur EST le mot de passe
            else:
                password = env_pwd or RECOVERY_PASSWORD
            action = self._upsert_admin(username, password)
            self.stdout.write(
                f"🔑 Admin portail « {username} » {action} via variable d'environnement. "
                f"Connectez-vous puis RETIREZ RESET_PORTAL_ADMIN / PORTAL_ADMIN_PASSWORD."
            )
            return

        # (2) Récupération automatique unique (marqueur sur le volume).
        marker = self._marker_path()
        try:
            already = marker.exists()
        except Exception:
            already = False
        if already:
            self.stdout.write("Admin portail : marqueur de récupération présent, aucune action.")
            return

        action = self._upsert_admin(username, RECOVERY_PASSWORD)
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(datetime.datetime.utcnow().isoformat() + "\n")
        except Exception:
            pass
        self.stdout.write(
            f"🔑 Récupération automatique unique — admin portail « {username} » {action} "
            f"avec le mot de passe « {RECOVERY_PASSWORD} ». À CHANGER immédiatement après connexion."
        )
