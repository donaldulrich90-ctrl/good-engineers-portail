"""Provisionne un client complet dans le portail, en une seule commande.

Crée (ou met à jour) l'entreprise, ses modules, la correspondance vers les
applications, et un compte administrateur du compte client. Idempotent :
relancer avec les mêmes arguments ne crée pas de doublon.

Exemples
--------
Client Suite (forage + mine) :
  python manage.py creer_client \\
      --nom "SAHARA MINING" --slug sahara --offre suite \\
      --forage-id 2 --mine-tenant sahara \\
      --admin-user donald --admin-pass "MotDePasseFort" \\
      --forage-user d.forage --mine-user d.mine

Client Forage seul :
  python manage.py creer_client --nom "FORAG SARL" --slug forag \\
      --offre forage --forage-id 3 --admin-user chef --admin-pass "xxxx"

Client Mine seule :
  python manage.py creer_client --nom "OR DU SAHEL" --slug orsahel \\
      --offre mine --mine-tenant orsahel --admin-user chef --admin-pass "xxxx"

Si --admin-pass est omis, un mot de passe est généré et affiché une fois.
--forage-user / --mine-user valent --admin-user par défaut : ce sont les
identifiants du compte DANS l'application Forage / Mine (ils doivent exister
côté app pour que la connexion unique aboutisse).
"""
import secrets

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from portal.models import Entreprise, Profil


class Command(BaseCommand):
    help = "Crée (ou met à jour) un client : entreprise, modules, mapping et compte admin."

    def add_arguments(self, parser):
        parser.add_argument("--nom", required=True)
        parser.add_argument("--slug", default="")
        parser.add_argument("--offre", required=True, choices=["forage", "mine", "suite"])
        parser.add_argument("--forage-id", type=int, default=None,
                            help="enterpriseId dans l'app Forage (requis sauf offre mine)")
        parser.add_argument("--mine-tenant", default="",
                            help="tenant dans l'app Mine (requis sauf offre forage)")
        parser.add_argument("--admin-user", required=True,
                            help="identifiant du compte admin DANS le portail")
        parser.add_argument("--admin-pass", default="",
                            help="mot de passe (généré si omis)")
        parser.add_argument("--admin-nom", default="")
        parser.add_argument("--forage-user", default="",
                            help="identifiant côté app Forage (défaut: --admin-user)")
        parser.add_argument("--forage-role", default="admin")
        parser.add_argument("--mine-user", default="",
                            help="identifiant côté app Mine (défaut: --admin-user)")
        parser.add_argument("--mine-role", default="Administrateur")

    @transaction.atomic
    def handle(self, *args, **o):
        offre = o["offre"]
        veut_forage = offre in ("forage", "suite")
        veut_mine = offre in ("mine", "suite")

        if veut_forage and o["forage_id"] is None:
            raise CommandError("--forage-id est requis pour l'offre forage/suite.")
        if veut_mine and not o["mine_tenant"]:
            raise CommandError("--mine-tenant est requis pour l'offre mine/suite.")

        slug = o["slug"] or slugify(o["nom"])

        ent, cree = Entreprise.objects.update_or_create(
            slug=slug,
            defaults={
                "nom": o["nom"],
                "active": True,
                "module_forage": veut_forage,
                "module_mine": veut_mine,
                "forage_enterprise_id": o["forage_id"] if veut_forage else None,
                "mine_tenant_id": o["mine_tenant"] if veut_mine else "",
            },
        )

        # Compte administrateur du compte client.
        mot_de_passe = o["admin_pass"] or secrets.token_urlsafe(10)
        user, user_cree = User.objects.get_or_create(
            username=o["admin_user"],
            defaults={"first_name": o["admin_nom"] or o["admin_user"]},
        )
        user.set_password(mot_de_passe)  # haché en bcrypt (hasher par défaut)
        user.save()

        Profil.objects.update_or_create(
            user=user,
            defaults={
                "entreprise": ent,
                "role_portail": "admin",
                "forage_username": (o["forage_user"] or o["admin_user"]) if veut_forage else "",
                "forage_role": o["forage_role"] if veut_forage else "",
                "mine_username": (o["mine_user"] or o["admin_user"]) if veut_mine else "",
                "mine_role": o["mine_role"] if veut_mine else "",
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"{'Créé' if cree else 'Mis à jour'} : {ent.nom} ({slug}) — offre {offre}"
        ))
        self.stdout.write(f"  modules actifs : {', '.join(ent.modules_actifs()) or '(aucun — vérifie le mapping)'}")
        self.stdout.write(f"  admin portail  : {o['admin_user']}")
        if not o["admin_pass"]:
            self.stdout.write(self.style.WARNING(
                f"  mot de passe généré (note-le, affiché une seule fois) : {mot_de_passe}"
            ))
        self.stdout.write("  -> connexion sur le portail, puis bascule entre les modules actifs.")
