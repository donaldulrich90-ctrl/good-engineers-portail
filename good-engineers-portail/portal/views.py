"""Vues du portail.

Parcours type :
  1. L'utilisateur se connecte UNE fois sur le portail (login_view).
  2. Le tableau de bord (dashboard) affiche ses modules et le rapport.
  3. Il clique sur un module -> go_module mint un jeton SSO et redirige vers
     l'application, qui ouvre sa session toute seule. Pas de reconnexion.
"""
import json
import urllib.parse
from datetime import date, datetime

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .models import Employe, Entreprise, JetonConsomme, Pointage, Profil
from .services import (
    creer_entreprise_forage,
    creer_entreprise_mine,
    creer_user_forage,
    creer_user_mine,
    fetch_forage_metrics,
    fetch_mine_metrics,
)
from .sso import mint_token

OFFRE_LABELS = {"forage": "Forage seul", "mine": "Mine seule", "suite": "Suite intégrale"}


def _offre(entreprise):
    mods = entreprise.modules_actifs()
    if len(mods) >= 2:
        return "suite"
    if mods == ["forage"]:
        return "forage"
    if mods == ["mine"]:
        return "mine"
    return "aucune"

MODULE_URLS = {"forage": settings.FORAGE_BASE_URL, "mine": settings.MINE_BASE_URL}
MODULE_LABELS = {"forage": "Forage", "mine": "Mine"}


def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


# --------------------------------------------------------------------------
# Authentification
# --------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    erreur = ""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            nxt = request.GET.get("next") or "dashboard"
            return redirect(nxt)
        erreur = "Identifiant ou mot de passe incorrect."
    return render(request, "portal/login.html", {"erreur": erreur})


def logout_view(request):
    logout(request)
    return redirect("login")


# --------------------------------------------------------------------------
# Tableau de bord
# --------------------------------------------------------------------------
def _profil(request):
    return getattr(request.user, "profil", None)


@login_required
def dashboard(request):
    profil = _profil(request)
    if profil is None:
        return render(request, "portal/sans_entreprise.html", status=200)

    ent = profil.entreprise
    modules = []
    for m in ("forage", "mine"):
        modules.append({
            "cle": m,
            "label": MODULE_LABELS[m],
            "actif": m in ent.modules_actifs(),
            "accessible": profil.peut_acceder(m),
        })
    offre = _offre(ent)
    return render(request, "portal/dashboard.html", {
        "entreprise": ent,
        "modules": modules,
        "profil": profil,
        "offre": offre,
        "offre_label": OFFRE_LABELS.get(offre, "—"),
        "est_suite": offre == "suite",
    })


# --------------------------------------------------------------------------
# Bascule : mint d'un jeton et redirection vers le module
# --------------------------------------------------------------------------
@login_required
def go_module(request, module):
    profil = _profil(request)
    if profil is None or module not in MODULE_URLS:
        return HttpResponseBadRequest("Module inconnu.")
    if not profil.peut_acceder(module):
        return render(request, "portal/acces_refuse.html",
                      {"module": MODULE_LABELS.get(module, module)}, status=403)

    username, role, ent_id = profil.identite_module(module)
    modules_actifs = [m for m in profil.entreprise.modules_actifs()
                      if profil.peut_acceder(m)]
    token, jti = mint_token(
        module=module, username=username, role=role, ent_id=ent_id,
        modules=modules_actifs, display_name=profil.user.get_full_name() or username,
    )
    JetonConsomme.objects.create(jti=jti, module=module, username=str(username))

    base = MODULE_URLS[module]
    # L'application expose /sso (Forage) ou /sso/ (Mine) ; on envoie le jeton.
    sep = "/sso/" if module == "mine" else "/sso"
    url = f"{base}{sep}?token={urllib.parse.quote(token)}"
    return redirect(url)


# --------------------------------------------------------------------------
# API lue par la barre de bascule (facultatif : la barre peut être rendue
# côté application à partir du claim `mods` du jeton SSO).
# --------------------------------------------------------------------------
@login_required
def api_nav(request):
    profil = _profil(request)
    if profil is None:
        return JsonResponse({"modules": []})
    mods = [{"cle": m, "label": MODULE_LABELS[m],
             "url": f"{settings.PORTAIL_BASE_URL}/go/{m}/"}
            for m in profil.entreprise.modules_actifs() if profil.peut_acceder(m)]
    return JsonResponse({"portail": settings.PORTAIL_BASE_URL, "modules": mods})


# --------------------------------------------------------------------------
# Rapport consolidé
# --------------------------------------------------------------------------
def _periode(request):
    today = date.today()
    first = today.replace(day=1)
    try:
        start = datetime.strptime(request.GET.get("start", ""), "%Y-%m-%d").date()
    except ValueError:
        start = first
    try:
        end = datetime.strptime(request.GET.get("end", ""), "%Y-%m-%d").date()
    except ValueError:
        end = today
    if end < start:
        start, end = end, start
    return start, end


def _collecte(profil, start, end):
    """Interroge les modules actifs et renvoie un dict de sections."""
    ent = profil.entreprise
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    data = {"forage": None, "mine": None, "erreurs": []}

    if "forage" in ent.modules_actifs():
        d, err = fetch_forage_metrics(ent.forage_enterprise_id, s, e)
        data["forage"] = d
        if err:
            data["erreurs"].append(f"Forage : {err}")

    if "mine" in ent.modules_actifs():
        d, err = fetch_mine_metrics(ent.mine_tenant_id, s, e)
        data["mine"] = d
        if err:
            data["erreurs"].append(f"Mine : {err}")

    # Vue croisée simple : coûts et carburant additionnés si les deux existent.
    croise = None
    if data["forage"] and data["mine"]:
        f, m = data["forage"], data["mine"]
        croise = {
            "cout_total": round((f.get("cout_total") or 0) + (m.get("cout_total") or 0), 2),
            "carburant_litres": round((f.get("carburant_litres") or 0)
                                      + (m.get("carburant_litres") or 0), 1),
            "effectif": (f.get("effectif") or 0) + (m.get("effectif") or 0),
        }
    data["croise"] = croise
    return data


@login_required
def rapport_view(request):
    profil = _profil(request)
    if profil is None:
        return render(request, "portal/sans_entreprise.html", status=200)
    start, end = _periode(request)
    data = _collecte(profil, start, end)
    return render(request, "portal/rapport.html", {
        "entreprise": profil.entreprise,
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "start_fr": start.strftime("%d/%m/%Y"),
        "end_fr": end.strftime("%d/%m/%Y"),
        "data": data,
        "data_json": json.dumps(data),
    })


@login_required
def rapport_export_xlsx(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    profil = _profil(request)
    if profil is None:
        return HttpResponseBadRequest("Aucune entreprise.")
    start, end = _periode(request)
    data = _collecte(profil, start, end)

    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    gras = Font(bold=True)
    ws["A1"] = f"Rapport consolidé — {profil.entreprise.nom}"
    ws["A1"].font = gras
    ws["A2"] = f"Période : {start:%d/%m/%Y} au {end:%d/%m/%Y}"
    row = 4

    def bloc(titre, d, colonnes):
        nonlocal row
        ws.cell(row=row, column=1, value=titre).font = gras
        row += 1
        for i, (cle, libelle) in enumerate(colonnes, start=1):
            ws.cell(row=row, column=i, value=libelle).font = gras
        row += 1
        for ligne in (d or {}).get("par_engin", []):
            for i, (cle, _lib) in enumerate(colonnes, start=1):
                ws.cell(row=row, column=i, value=ligne.get(cle))
            row += 1
        row += 1

    if data["forage"]:
        bloc("FORAGE", data["forage"], [
            ("engin", "Foreuse"), ("metres", "Mètres forés"),
            ("rop", "ROP moy."), ("arrets", "Arrêts"),
            ("consommables_cout", "Coût consommables"),
        ])
    if data["mine"]:
        bloc("MINE", data["mine"], [
            ("engin", "Engin"), ("production", "Production (t)"),
            ("heures", "Heures"), ("carburant", "Carburant (L)"),
            ("tph", "t/h"), ("lpt", "L/t"),
        ])

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    nom = f"rapport-{profil.entreprise.slug}-{start:%Y%m%d}-{end:%Y%m%d}.xlsx"
    resp["Content-Disposition"] = f'attachment; filename="{nom}"'
    wb.save(resp)
    return resp


# ==========================================================================
# CONSOLE GESTIONNAIRE (plateforme) — réservée au superuser (toi).
# Créer les clients, cocher leurs modules, et donner les accès, en pages web.
# ==========================================================================
gestionnaire = user_passes_test(lambda u: u.is_superuser, login_url="login")


@gestionnaire
def gestion_clients(request):
    clients = []
    for e in Entreprise.objects.all():
        clients.append({
            "obj": e,
            "offre": OFFRE_LABELS.get(_offre(e), "—"),
            "nb_comptes": e.profils.count(),
        })
    return render(request, "portal/gestion/clients.html", {"clients": clients})


@gestionnaire
@require_http_methods(["GET", "POST"])
def gestion_client_edit(request, client_id=None):
    ent = get_object_or_404(Entreprise, pk=client_id) if client_id else None
    erreur = ""
    if request.method == "POST":
        nom = (request.POST.get("nom") or "").strip()
        slug = (request.POST.get("slug") or "").strip() or slugify(nom)
        module_forage = bool(request.POST.get("module_forage"))
        module_mine = bool(request.POST.get("module_mine"))
        active = bool(request.POST.get("active"))
        forage_id = (request.POST.get("forage_enterprise_id") or "").strip()
        mine_tenant = (request.POST.get("mine_tenant_id") or "").strip()

        if not nom:
            erreur = "Le nom est obligatoire."
        else:
            soucis = []
            try:
                forage_val = int(forage_id) if (module_forage and forage_id) else None
            except ValueError:
                forage_val = None
            mine_val = mine_tenant if (module_mine and mine_tenant) else ""

            # Un module coché sans correspondance : on crée l'entreprise dans
            # l'application et on récupère son identifiant automatiquement.
            if module_forage and forage_val is None:
                fid, err = creer_entreprise_forage(nom, slug)
                if fid is not None:
                    forage_val = int(fid)
                else:
                    soucis.append(f"Forage ({err})")
            if module_mine and not mine_val:
                tid, err = creer_entreprise_mine(nom, slug)
                if tid:
                    mine_val = tid
                else:
                    soucis.append(f"Mine ({err})")

            champs = {
                "nom": nom, "slug": slug, "active": active,
                "module_forage": module_forage, "module_mine": module_mine,
                "forage_enterprise_id": forage_val if module_forage else None,
                "mine_tenant_id": mine_val if module_mine else "",
            }
            try:
                if ent:
                    for k, v in champs.items():
                        setattr(ent, k, v)
                    ent.save()
                else:
                    ent = Entreprise.objects.create(**champs)
                if not soucis:
                    return redirect(reverse("gestion_comptes", args=[ent.pk]))
                erreur = ("Entreprise enregistrée, mais la création a échoué dans : "
                          + " ; ".join(soucis)
                          + ". Réessaie (enregistre à nouveau) quand l'application répond.")
            except Exception as e:  # noqa: BLE001
                erreur = f"Enregistrement impossible : {e}"

    return render(request, "portal/gestion/client_edit.html", {"ent": ent, "erreur": erreur})


@gestionnaire
@require_http_methods(["GET", "POST"])
def gestion_comptes(request, client_id):
    ent = get_object_or_404(Entreprise, pk=client_id)
    erreur = ""
    ok = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "supprimer":
            uid = request.POST.get("user_id")
            Profil.objects.filter(entreprise=ent, user_id=uid).delete()
            User.objects.filter(pk=uid, is_superuser=False).delete()
            ok = "Compte supprimé."
        else:
            # Un seul identifiant + un seul mot de passe, créés PARTOUT :
            # dans le portail, et dans chaque application dont le module est actif.
            username = (request.POST.get("username") or "").strip()
            password = request.POST.get("password") or ""
            role_portail = request.POST.get("role_portail") or "membre"
            f_role = (request.POST.get("forage_role") or "foreur").strip()
            m_role = (request.POST.get("mine_role") or "Invite").strip()
            existant = User.objects.filter(username=username).first()
            lie_ici = existant and Profil.objects.filter(user=existant, entreprise=ent).exists()
            if not username or not password:
                erreur = "Identifiant et mot de passe obligatoires."
            elif existant and not lie_ici:
                erreur = "Cet identifiant est déjà utilisé par un autre client."
            else:
                # Création, ou mise à jour si on resaisit le même compte (retry).
                with transaction.atomic():
                    u = existant or User.objects.create(username=username, first_name=username)
                    u.set_password(password)  # bcrypt
                    u.save()
                    Profil.objects.update_or_create(
                        user=u, defaults={
                            "entreprise": ent, "role_portail": role_portail,
                            "forage_username": username if ent.module_forage else "",
                            "forage_role": f_role if ent.module_forage else "",
                            "mine_username": username if ent.module_mine else "",
                            "mine_role": m_role if ent.module_mine else "",
                        },
                    )
                # Création du même compte dans les applications actives.
                faits, soucis = [], []
                if ent.module_forage:
                    o, e = creer_user_forage(ent.forage_enterprise_id, username, password, f_role)
                    (faits if o else soucis).append("Forage" if o else f"Forage ({e})")
                if ent.module_mine:
                    o, e = creer_user_mine(ent.mine_tenant_id, username, password, m_role)
                    (faits if o else soucis).append("Mine" if o else f"Mine ({e})")
                ok = f"Compte « {username} » créé"
                if faits:
                    ok += " — aussi dans : " + ", ".join(faits)
                ok += "."
                if soucis:
                    erreur = ("Compte portail créé, mais échec côté : " + " ; ".join(soucis)
                              + ". Réessaie quand l'application répond (le même formulaire met à jour).")

    comptes = ent.profils.select_related("user").all()
    return render(request, "portal/gestion/comptes.html", {
        "ent": ent, "comptes": comptes, "erreur": erreur, "ok": ok,
        "offre": OFFRE_LABELS.get(_offre(ent), "—"),
    })


# ==========================================================================
# PERSONNEL + POINTAGE — côté entreprise (saisi une seule fois, tous packs)
# ==========================================================================
import calendar as _calendar


def _entreprise_courante(request):
    """L'entreprise du compte connecté ; un superuser peut viser ?entreprise=<id>."""
    profil = _profil(request)
    if profil is not None:
        return profil.entreprise, profil
    if request.user.is_superuser:
        eid = request.GET.get("entreprise") or request.POST.get("entreprise")
        if eid:
            return get_object_or_404(Entreprise, pk=eid), None
    return None, None


def _peut_gerer_personnel(profil):
    # Gérer la liste du personnel : admin du compte client (ou superuser).
    return profil is None or profil.role_portail == "admin"


@login_required
@require_http_methods(["GET", "POST"])
def personnel(request):
    ent, profil = _entreprise_courante(request)
    if ent is None:
        return render(request, "portal/sans_entreprise.html", status=200)
    erreur = ""
    ok = ""
    peut_gerer = _peut_gerer_personnel(profil)

    if request.method == "POST":
        if not peut_gerer:
            erreur = "Seul un administrateur du compte peut modifier le personnel."
        else:
            action = request.POST.get("action")
            if action == "supprimer":
                Employe.objects.filter(entreprise=ent, pk=request.POST.get("employe_id")).delete()
                ok = "Employé supprimé."
            elif action == "desactiver":
                Employe.objects.filter(entreprise=ent, pk=request.POST.get("employe_id")).update(actif=False)
                ok = "Employé désactivé."
            elif action == "activer":
                Employe.objects.filter(entreprise=ent, pk=request.POST.get("employe_id")).update(actif=True)
                ok = "Employé réactivé."
            else:
                nom = (request.POST.get("nom") or "").strip()
                if not nom:
                    erreur = "Le nom est obligatoire."
                else:
                    Employe.objects.create(
                        entreprise=ent, nom=nom,
                        matricule=(request.POST.get("matricule") or "").strip(),
                        poste=(request.POST.get("poste") or "").strip(),
                        sous_traitant=bool(request.POST.get("sous_traitant")),
                    )
                    ok = f"Employé « {nom} » ajouté."

    employes = ent.employes.all()
    return render(request, "portal/pointage/personnel.html", {
        "entreprise": ent, "employes": employes, "erreur": erreur, "ok": ok,
        "peut_gerer": peut_gerer, "postes_suggeres": Employe.POSTES_SUGGERES,
    })


def _parse_date(s, defaut):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return defaut


@login_required
@require_http_methods(["GET", "POST"])
def pointage(request):
    ent, profil = _entreprise_courante(request)
    if ent is None:
        return render(request, "portal/sans_entreprise.html", status=200)
    jour = _parse_date(request.GET.get("date") or request.POST.get("date"), date.today())
    ok = ""

    employes = list(ent.employes.filter(actif=True))
    if request.method == "POST":
        for e in employes:
            statut = request.POST.get(f"statut_{e.id}")
            if not statut:
                continue
            poste = request.POST.get(f"poste_{e.id}", "")
            heures_raw = (request.POST.get(f"heures_{e.id}") or "0").replace(",", ".")
            try:
                heures = float(heures_raw)
            except ValueError:
                heures = 0
            note = (request.POST.get(f"note_{e.id}") or "").strip()
            Pointage.objects.update_or_create(
                employe=e, date=jour,
                defaults={"entreprise": ent, "statut": statut, "poste": poste,
                          "heures": heures, "note": note},
            )
        ok = f"Pointage du {jour:%d/%m/%Y} enregistré."

    existants = {p.employe_id: p for p in Pointage.objects.filter(entreprise=ent, date=jour)}
    lignes = []
    for e in employes:
        p = existants.get(e.id)
        lignes.append({
            "e": e,
            "statut": p.statut if p else "present",
            "poste": p.poste if p else "",
            "heures": (f"{p.heures:.2f}" if p else ""),
            "note": p.note if p else "",
        })
    return render(request, "portal/pointage/pointage.html", {
        "entreprise": ent, "lignes": lignes, "ok": ok,
        "date": jour.strftime("%Y-%m-%d"), "date_fr": jour.strftime("%d/%m/%Y"),
        "statuts": Pointage.STATUTS, "postes": Pointage.POSTES,
    })


@login_required
def pointage_recap(request):
    ent, profil = _entreprise_courante(request)
    if ent is None:
        return render(request, "portal/sans_entreprise.html", status=200)
    today = date.today()
    try:
        annee, mois = (request.GET.get("mois") or today.strftime("%Y-%m")).split("-")
        annee, mois = int(annee), int(mois)
    except (ValueError, TypeError):
        annee, mois = today.year, today.month
    debut = date(annee, mois, 1)
    fin = date(annee, mois, _calendar.monthrange(annee, mois)[1])

    pts = Pointage.objects.filter(entreprise=ent, date__gte=debut, date__lte=fin).select_related("employe")
    par_emp = {}
    for p in pts:
        r = par_emp.setdefault(p.employe_id, {
            "employe": p.employe, "present": 0, "absent": 0, "conge": 0,
            "repos": 0, "maladie": 0, "heures": 0.0,
        })
        if p.statut in r:
            r[p.statut] += 1
        r["heures"] += float(p.heures or 0)
    lignes = sorted(par_emp.values(), key=lambda x: x["employe"].nom)
    for r in lignes:
        r["heures"] = round(r["heures"], 1)

    return render(request, "portal/pointage/recap.html", {
        "entreprise": ent, "lignes": lignes,
        "mois": f"{annee:04d}-{mois:02d}",
        "mois_fr": debut.strftime("%m/%Y"),
    })
