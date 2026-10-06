"""Back-office : c'est ici que tu gères tes clients et leurs modules.

Cocher / décocher « module Forage » ou « module Mine » sur une entreprise
= activer / détacher le module pour ce client. Au décochage, le portail
désactive aussi l'entreprise dans l'application concernée (voir signaux).
"""
from django.contrib import admin

from .models import Entreprise, JetonConsomme, Profil


class ProfilInline(admin.StackedInline):
    model = Profil
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ("nom", "active", "module_forage", "module_mine",
                    "forage_enterprise_id", "mine_tenant_id")
    list_filter = ("active", "module_forage", "module_mine")
    search_fields = ("nom", "slug", "mine_tenant_id")
    prepopulated_fields = {"slug": ("nom",)}
    fieldsets = (
        (None, {"fields": ("nom", "slug", "active")}),
        ("Modules souscrits", {
            "fields": ("module_forage", "module_mine"),
            "description": "Décocher un module le détache pour ce client. "
                           "Les données restent en base : recocher rend tout.",
        }),
        ("Correspondance avec les applications", {
            "fields": ("forage_enterprise_id", "mine_tenant_id"),
            "description": "Relie cette entreprise à son enregistrement dans "
                           "Forage (enterpriseId) et dans la Mine (tenant).",
        }),
    )


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ("user", "entreprise", "role_portail",
                    "forage_username", "mine_username")
    list_filter = ("entreprise", "role_portail")
    search_fields = ("user__username", "forage_username", "mine_username")
    autocomplete_fields = ["user", "entreprise"]


@admin.register(JetonConsomme)
class JetonConsommeAdmin(admin.ModelAdmin):
    list_display = ("jti", "module", "username", "emis_le")
    list_filter = ("module",)
    search_fields = ("jti", "username")
    readonly_fields = ("jti", "module", "username", "emis_le")
