"""Modèles du portail : entreprises clientes, modules activés, et le lien
entre un compte du portail et son identité dans chaque application.

Le portail ne duplique AUCUNE donnée métier. Il ne connaît que :
  - quelles entreprises existent et quels modules elles ont souscrits ;
  - comment une entreprise s'appelle côté Forage (enterpriseId entier) et
    côté Mine (identifiant de tenant texte) ;
  - comment un utilisateur s'appelle et quel rôle il a dans chaque module.
"""
from django.conf import settings
from django.db import models


class Entreprise(models.Model):
    """Un client. Porte les cases « modules » et le mapping vers les apps."""

    nom = models.CharField("nom", max_length=200)
    slug = models.SlugField("slug", unique=True)
    active = models.BooleanField("entreprise active", default=True)

    # --- Modules souscrits (les « cases à cocher ») ---------------------
    module_forage = models.BooleanField("module Forage", default=False)
    module_mine = models.BooleanField("module Mine", default=False)

    # --- Mapping vers chaque application --------------------------------
    # Forage (DRILLING-GE) identifie l'entreprise par un entier (enterprises.id).
    forage_enterprise_id = models.IntegerField(
        "enterpriseId côté Forage", null=True, blank=True,
        help_text="L'id de l'entreprise dans la base de DRILLING-GE.",
    )
    # Mine (GEMINING-1) identifie l'entreprise par un identifiant de tenant.
    mine_tenant_id = models.CharField(
        "tenant côté Mine", max_length=120, blank=True, default="",
        help_text="L'identifiant de tenant dans GOOD ENGINEERS OS (ex: 'default' ou un slug).",
    )

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "entreprise"
        verbose_name_plural = "entreprises"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def modules_actifs(self):
        """Liste des modules réellement utilisables (souscrits + mappés)."""
        mods = []
        if self.module_forage and self.forage_enterprise_id is not None:
            mods.append("forage")
        if self.module_mine and self.mine_tenant_id:
            mods.append("mine")
        return mods


class Profil(models.Model):
    """Étend le compte Django avec l'entreprise et l'identité par module.

    Le username et le rôle peuvent différer d'un module à l'autre : on les
    stocke donc séparément. Laisser vide un couple username/rôle revient à
    refuser l'accès de cet utilisateur à ce module.
    """

    ROLE_PORTAIL = [
        ("admin", "Administrateur du compte client"),
        ("membre", "Membre"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    entreprise = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE, related_name="profils"
    )
    role_portail = models.CharField(max_length=20, choices=ROLE_PORTAIL, default="membre")

    # Identité dans le module Forage.
    forage_username = models.CharField(max_length=120, blank=True, default="")
    forage_role = models.CharField(max_length=60, blank=True, default="")

    # Identité dans le module Mine.
    mine_username = models.CharField(max_length=120, blank=True, default="")
    mine_role = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profils"

    def __str__(self):
        return f"{self.user.username} — {self.entreprise.nom}"

    def peut_acceder(self, module: str) -> bool:
        if module not in self.entreprise.modules_actifs():
            return False
        if module == "forage":
            return bool(self.forage_username)
        if module == "mine":
            return bool(self.mine_username)
        return False

    def identite_module(self, module: str):
        """(username, role, ent_id) à injecter dans le jeton SSO du module."""
        if module == "forage":
            return self.forage_username, (self.forage_role or "foreur"), self.entreprise.forage_enterprise_id
        if module == "mine":
            return self.mine_username, (self.mine_role or "Invite"), self.entreprise.mine_tenant_id
        return None, None, None


class JetonConsomme(models.Model):
    """Trace les jti déjà émis (anti-rejeu, côté portail — journal)."""

    jti = models.CharField(max_length=64, unique=True)
    module = models.CharField(max_length=20)
    username = models.CharField(max_length=120)
    emis_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "jeton SSO émis"
        verbose_name_plural = "jetons SSO émis"
        ordering = ["-emis_le"]

    def __str__(self):
        return f"{self.jti[:8]}… → {self.module}"
