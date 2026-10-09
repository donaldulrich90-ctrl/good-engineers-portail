from django.contrib import admin
from django.urls import path

from portal import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Bascule : mint d'un jeton SSO court et redirection vers le module.
    path("go/<slug:module>/", views.go_module, name="go_module"),

    # Rapport consolidé.
    path("rapport/", views.rapport_view, name="rapport"),
    path("suivi-plan/", views.suivi_plan_view, name="suivi_plan"),
    path("rapport/export.xlsx", views.rapport_export_xlsx, name="rapport_export_xlsx"),

    # Personnel + Pointage (côté entreprise, partagé tous packs).
    path("personnel/", views.personnel, name="personnel"),
    path("pointage/", views.pointage, name="pointage"),
    path("pointage/recap/", views.pointage_recap, name="pointage_recap"),

    # Console gestionnaire (plateforme) — réservée au superuser.
    path("gestion/", views.gestion_clients, name="gestion_clients"),
    path("gestion/client/nouveau/", views.gestion_client_edit, name="gestion_client_nouveau"),
    path("gestion/client/<int:client_id>/", views.gestion_client_edit, name="gestion_client_edit"),
    path("gestion/client/<int:client_id>/comptes/", views.gestion_comptes, name="gestion_comptes"),

    # Petite API lue par la barre de bascule (modules actifs de l'entreprise).
    path("api/nav/", views.api_nav, name="api_nav"),

    path("healthz", views.healthz, name="healthz"),
]
