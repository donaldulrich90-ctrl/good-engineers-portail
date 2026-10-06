"""Quand une entreprise change d'état de module, prévenir l'application.

Décocher « module Forage » -> on demande à Forage de désactiver l'entreprise.
Recocher -> on la réactive. Idem pour la Mine. C'est best effort : voir
services.py (une app injoignable n'empêche pas de sauvegarder).
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from . import services
from .models import Entreprise


@receiver(pre_save, sender=Entreprise)
def _memo_etat_precedent(sender, instance, **kwargs):
    if instance.pk:
        try:
            ancien = Entreprise.objects.get(pk=instance.pk)
            instance._ancien_forage = (ancien.module_forage, ancien.active)
            instance._ancien_mine = (ancien.module_mine, ancien.active)
        except Entreprise.DoesNotExist:
            instance._ancien_forage = None
            instance._ancien_mine = None
    else:
        instance._ancien_forage = None
        instance._ancien_mine = None


@receiver(post_save, sender=Entreprise)
def _propager(sender, instance, created, **kwargs):
    veut_forage = instance.module_forage and instance.active
    veut_mine = instance.module_mine and instance.active

    if created or getattr(instance, "_ancien_forage", None) != (instance.module_forage, instance.active):
        services.propager_etat_forage(instance.forage_enterprise_id, veut_forage)
    if created or getattr(instance, "_ancien_mine", None) != (instance.module_mine, instance.active):
        services.propager_etat_mine(instance.mine_tenant_id, veut_mine)
