"""Importe les comptes d'une entreprise depuis l'app Mine (app_database.json).

Les mots de passe de la Mine sont des SHA-256 non salés. On les stocke tels
quels sous la forme `legacy_mine_sha256$<hash>` : l'utilisateur se connecte
avec son mot de passe habituel, et Django le ré-hache en bcrypt tout seul à
la première connexion (voir portal/hashers.py).

Usage :
  python manage.py importer_mine --fichier /chemin/app_database.json \
      --entreprise-slug sahara --tenant default

--entreprise-slug : le slug de l'Entreprise déjà créée dans le portail.
--tenant          : l'identifiant de tenant Mine à rattacher (ex: 'default').
--dry-run         : montre ce qui serait importé sans rien écrire.
"""
import json

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from portal.models import Entreprise, Profil


class Command(BaseCommand):
    help = "Importe les comptes Mine (SHA-256) dans le portail, prêts à passer en bcrypt."

    def add_arguments(self, parser):
        parser.add_argument("--fichier", required=True, help="Chemin vers app_database.json")
        parser.add_argument("--entreprise-slug", required=True)
        parser.add_argument("--tenant", default="default")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        try:
            ent = Entreprise.objects.get(slug=opts["entreprise_slug"])
        except Entreprise.DoesNotExist:
            raise CommandError("Entreprise introuvable : crée-la d'abord dans l'admin.")

        with open(opts["fichier"], "r", encoding="utf-8") as f:
            db = json.load(f)

        comptes = db.get("users_list", []) or []
        tenant = opts["tenant"]
        n = 0
        for u in comptes:
            # On ne prend que les comptes du tenant demandé.
            if str(u.get("tenant_id", "default")) != tenant:
                continue
            username = (u.get("user") or u.get("username") or "").strip()
            if not username:
                continue
            pass_hash = (u.get("pass") or "").strip()
            role = u.get("role", "Invite")
            portail_user = f"{opts['entreprise_slug']}_{username}"

            self.stdout.write(f"  {username}  (rôle Mine: {role}) -> {portail_user}")
            if opts["dry_run"]:
                n += 1
                continue

            user, _ = User.objects.get_or_create(
                username=portail_user, defaults={"first_name": username}
            )
            # Mot de passe : hash SHA-256 existant, reconnu par le hasher legacy.
            if len(pass_hash) == 64 and all(c in "0123456789abcdef" for c in pass_hash.lower()):
                user.password = f"legacy_mine_sha256${pass_hash.lower()}"
            user.save()

            Profil.objects.update_or_create(
                user=user,
                defaults={
                    "entreprise": ent,
                    "mine_username": username,
                    "mine_role": role,
                    "role_portail": "admin" if role in ("Administrateur", "Gestionnaire") else "membre",
                },
            )
            n += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'(dry-run) ' if opts['dry_run'] else ''}{n} compte(s) traité(s)."
        ))
