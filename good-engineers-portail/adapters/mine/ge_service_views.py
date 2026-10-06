"""ADAPTATEUR MINE (GEMINING-1) — API de métriques pour le rapport consolidé.

À déposer dans GEMINING-1 (ex: webcore/ge_service_views.py) et à brancher
dans good_engineers_os/urls.py (voir urls-snippet.txt).

Deux routes protégées par la clé de service SERVICE_API_KEY (X-Service-Key) :

  GET  /api/service/metrics/?tenant=..&start=YYYY-MM-DD&end=YYYY-MM-DD
       -> métriques mine de l'entreprise sur la période (réutilise
          core.engineering.get_period_report, déjà écrit).
  POST /api/service/module-state/   { tenant, active }
       -> active / désactive le tenant (quand on coche/décoche le module
          Mine dans le portail).

Ces routes sont PUBLIQUES vis-à-vis du middleware d'auth de la Mine : on les
place sous /api/ et on ajoute "/api" aux préfixes publics du middleware
(voir urls-snippet.txt). La sécurité est assurée par la clé de service.
"""
import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core import storage
from core.auth import get_user_manager
from core.engineering import get_period_report

SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")


def _cle_ok(request):
    return SERVICE_API_KEY and request.headers.get("X-Service-Key", "") == SERVICE_API_KEY


def metrics(request):
    if not _cle_ok(request):
        return JsonResponse({"error": "Clé de service invalide"}, status=401)
    tenant = storage.safe_tenant_id(request.GET.get("tenant") or "default")
    start = request.GET.get("start", "")
    end = request.GET.get("end", "")
    if not start or not end:
        return JsonResponse({"error": "start et end requis"}, status=400)

    rows, tot = get_period_report(tenant, start, end)
    par_engin = [{
        "engin": r.get("machine_id"),
        "production": round(r.get("prod", 0), 1),
        "heures": round(r.get("h", 0), 1),
        "carburant": round(r.get("fuel", 0), 1),
        "cycles": int(r.get("cyc", 0)),
        "tph": r.get("tph", 0),
        "lpt": r.get("lpt", 0),
    } for r in rows]

    # Effectif (best effort : StaffManager de la Mine si présent).
    effectif = 0
    try:
        from core.staff import StaffManager
        effectif = len(StaffManager(tenant).get_active_staff() or [])
    except Exception:  # noqa: BLE001
        pass

    return JsonResponse({
        "module": "mine",
        "periode": {"start": start, "end": end},
        "par_engin": par_engin,
        "production_total": tot.get("prod", 0),
        "carburant_litres": tot.get("fuel", 0),
        # Le coût d'exploitation détaillé vit dans le module finance ; on le
        # laisse à 0 ici pour rester léger (à relier plus tard si besoin).
        "cout_total": 0,
        "effectif": effectif,
    })


@csrf_exempt
def module_state(request):
    if not _cle_ok(request):
        return JsonResponse({"error": "Clé de service invalide"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    tenant = storage.safe_tenant_id(body.get("tenant") or "")
    active = bool(body.get("active"))
    if not tenant:
        return JsonResponse({"error": "tenant requis"}, status=400)

    storage.set_tenant_active(tenant, active)
    return JsonResponse({"ok": True, "tenant": tenant, "active": active})


@csrf_exempt
def create_user(request):
    """Crée (ou met à jour) un compte Mine, piloté par le portail."""
    if not _cle_ok(request):
        return JsonResponse({"error": "Clé de service invalide"}, status=401)
    if request.method != "POST":
        return JsonResponse({"error": "POST requis"}, status=405)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    tenant = storage.safe_tenant_id(body.get("tenant") or "default")
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = body.get("role") or "Invite"
    if not username or not password:
        return JsonResponse({"error": "username et password requis"}, status=400)

    mgr = get_user_manager()
    if mgr.get_user(username):
        mgr.update_user(username, password=password, role=role)
        return JsonResponse({"ok": True, "updated": True, "username": username})
    mgr.add_user(username, password, role, tenant_id=tenant)
    return JsonResponse({"ok": True, "created": True, "username": username})
