# HANDOFF — Plateforme GOOD ENGINEERS (Forage · Mine · Portail)

> Document de passation pour continuer le développement (Claude Code ou autre).
> Dernière mise à jour : 2026-10-18.

## 1. Vue d'ensemble

SaaS multi-tenant pour sociétés minières, composé de **3 applications** déployées
sur un **Coolify auto-hébergé** (VPS Contabo).

| App | Rôle | Stack | Dépôt GitHub | URL publique |
|-----|------|-------|--------------|--------------|
| **Forage** | Forage / drilling | Node/Express + SQLite | `donaldulrich90-ctrl/DRILLING-GE` | https://gedrilling.duckdns.org |
| **Mine** | Mining | Django + SQLite/JSON par tenant | `donaldulrich90-ctrl/GEMINING-1` | https://gemining.duckdns.org |
| **Portail** | Console client consolidée + personnel | Django (ORM + migrations) | `donaldulrich90-ctrl/good-engineers-portail` | https://geportail.duckdns.org |

Propriétaire GitHub : **donaldulrich90-ctrl**. Branche par défaut : **main**.

## 2. Déploiement (Coolify)

- **Coolify** : `http://37.60.243.107:8000` (auto-hébergé sur le VPS). Projet **« My first project »**, environnement **production**.
- **UUID des applications** :
  - Forage (gedrilling) : `c1bc2nr5yjnrzkv7f0o6iydk`
  - Mine (gemining) : `b5pfvomd4fen3xg20w6k1md8`
  - Portail (geportail) : `fqo7r7pdaoubpdague25hznq`
- **Déployer** = bouton **Redeploy** sur la page de l'app → Coolify récupère le dernier `main` et reconstruit l'image. **Un seul build à la fois.**
- **Portail** : `migrate` + `collectstatic` au démarrage (Dockerfile) ; base SQLite persistante sur volume `/app/data/portail.db`. Les migrations Django s'appliquent donc automatiquement au redéploiement.
- **Forage/Mine** : données persistantes via volumes (uploads, `GE_DATA_ROOT`, bases SQLite par tenant).

### Pièges opérationnels connus
- La session Coolify du navigateur **expire** → se reconnecter.
- Le site en **HTTP sur IP** demande une **ré-autorisation** d'accès dans le navigateur.
- Si Coolify ne répond pas (`ERR_CONNECTION_TIMED_OUT`) : **redémarrer le VPS** depuis Contabo (les apps publiques peuvent rester up même si le panneau :8000 est down).
- Le pont vers le PC (contrôle du navigateur) peut se couper ; les builds Coolify se terminent côté serveur indépendamment.

## 3. Workflow de développement

1. `git checkout main && git fetch origin main && git reset --hard origin/main`
2. `git checkout -b feat/xxx`
3. Coder, **valider la syntaxe** (`node -c` pour Forage ; `python3 -m py_compile` pour Django ; vérifier l'équilibre des balises de templates).
4. Commit + push.
5. **Ouvrir la PR via l'API REST** (le GraphQL est bloqué dans ces sessions) :
   `gh api -X POST repos/OWNER/REPO/pulls -f title=... -f head=feat/xxx -f base=main -f body=...`
6. **Squash-merge** : `gh api -X PUT repos/OWNER/REPO/pulls/N/merge -f merge_method=squash`
7. **Redeploy** l'app concernée dans Coolify.

## 4. Architecture — points clés

### Forage (Node/Express, SQLite)
- Modules de routes : `require('./routes/X')(app, { db, getEnterpriseId })` dans `server.js`.
- Multi-tenant : `getEnterpriseId(req)` (en-tête `X-Enterprise-Id`). Rôles via `req.auth`.
- Uploads : `multer` → `/uploads/...` (servi en statique).
- **SPA** : `plateforme-forage.html` (~23 000 lignes, fichier unique). Appels API via la fonction globale **`apiRequest(endpoint, method, data)`** (de `api-client.js`) qui préfixe `/api` et ajoute `X-Enterprise-Id`. Aussi `window.API.*`.
  - Un onglet = un bouton nav `showMainView('x')` + un `<div id="mainView-x">` + `'x'` dans le tableau `views` + un cas dans `renderView`.
  - Valider tout le JS inline : extraire les `<script>` sans `src` et `node -c`.
- **API service** (pour le Portail) : `ge-metrics.js`, protégée par en-tête `X-Service-Key`, accès DB via `getDb()`.

### Mine (Django)
- Données par tenant : `core.storage.load_tenant_json/save_tenant_json` (JSON) et `core.db.get_connection(tenant)` (SQLite, `row_factory=Row`).
- Onglets : `core/permissions.py` → `TABS` (clé, label, permission, slug) ; `webcore/views.py` → `_VIEW_BY_SLUG` + `tab_view` ; nav via `context_processors.py`.
- **Règle critique** : les templates Django **refusent les variables/clés commençant par `_`** (provoque un 500). Ne jamais nommer une clé de contexte ou de dict `_xxx`.
- **API service** : `webcore/ge_service_views.py`, en-tête `X-Service-Key`, routes `api/service/...`.

### Portail (Django ORM + migrations)
- Modèles : `Entreprise`, `Profil`, `Employe`, `Pointage`, `RapportCommentaire`, `JetonConsomme` (`portal/models.py`).
- Consomme Forage/Mine via `settings.FORAGE_BASE_URL` / `settings.MINE_BASE_URL` + en-tête `X-Service-Key` (`portal/services.py` → `fetch_*`).
- SSO vers les apps : `portal/sso.py` (`mint_token`).
- Migrations dans `portal/migrations/` (dernière : `0006_employe_empreinte`).

## 5. Fonctionnalités livrées (cette série de travaux)

- **Logo de l'entreprise abonnée** (Forage/Mine/Portail) : téléversement + affichage page d'accueil/sidebar. (Forage utilise `companyLogo` ou `enterprises.logo` ; Mine `branding.json` ; Portail `Entreprise.logo` data-URI.)
- **Sous-traitants & location de machines** (Forage + Mine, consolidé Portail) :
  - Tables/stores : sous-traitants, machines louées (tarif + unité heure/jour/mètre/forfait), relevé d'usage mensuel, back-charges.
  - **Paiement mensuel = tarif × usage réel − back-charges** ; back-charges imputables **au sous-traitant** ou **à l'entreprise**, avec **justificatif joint** ; **bénéfice net**.
  - Forage : `routes/soustraitants.js`. Mine : `webcore/views.py` (`soustraitants_view`, JSON par tenant) + `templates/soustraitants.html`.
  - API service : `/api/service/soustraitants` (Forage) et `/api/service/soustraitants/` (Mine) → vue consolidée Portail (`portal/views.py:soustraitants_view`, `portal/templates/portal/soustraitants.html`).
- **Allocation machine → sous-traitant propriétaire** :
  - Forage : colonne `drills.subcontractorId` + endpoint ciblé `PUT /api/drills/:id/subcontractor` + onglet « Allocation foreuses » + champ au formulaire de création.
  - Mine : `machine_owners.json` par tenant + onglet « Allocation machines ».
- **Personnel par équipe & rotation + matricules auto** (Portail) : `Entreprise.matricule_prefix/seq`, `equipes`, `rotations` ; `Employe.equipe/rotation` ; génération matricule `PREFIXE-0001`. Migration `0005`.
- **Postes miniers complets** : `Employe.POSTES_SUGGERES` élargi (direction, géologie, topo, opérations, forage/minage, traitement, labo, maintenance, HSE, logistique, sécurité, support).
- **Biométrie — base posée** (Portail) : `Employe.empreinte_template` (gabarit), `empreinte_doigt`, `empreinte_enrolee` ; actions POST `empreinte_save` / `empreinte_reset` ; colonne « Empreinte » dans Personnel. Migration `0006`. **La capture n'est pas encore branchée** (voir §6).

## 6. À FAIRE (prochaines étapes)

### 6.1 Empreinte digitale — pointage biométrique (PRIORITÉ, en cours)
- **Matériel retenu** : lecteur USB **DigitalPersona U.are.U 4500** (pas encore acheté au 2026-10-18).
- **Prérequis PC de pointage** : pilote du lecteur + **DigitalPersona Lite Client** (agent local gratuit qui expose le lecteur au navigateur).
- **À construire (et à TESTER lecteur branché)** :
  1. **Enrôlement** : bouton « Capturer l'empreinte » dans la fiche employé (Portail Personnel) → via le WebSDK DigitalPersona (`@digitalpersona/devices`), capturer le gabarit (FMD) → `POST action=empreinte_save` (déjà prêt) qui stocke dans `Employe.empreinte_template` et met `empreinte_enrolee=True`. **Chiffrer le gabarit au repos** (champ prévu « chiffré » — ajouter le chiffrement, clé via settings/env).
  2. **Pointage par empreinte** : page de pointage → capture → **identification (1:N)** ou **vérification (1:1)**. ⚠️ **Le matching ne se fait pas dans le navigateur** : prévoir un moteur côté serveur (SDK serveur DigitalPersona — orienté Windows — ou **SourceAFIS** open-source sur image d'empreinte). À valider sur le vrai lecteur. Enregistrer le pointage (`Pointage`) sur correspondance.
- **Important** : ne pas livrer de code de capture non testé (risque de casser la page Personnel). Brancher la capture **uniquement** une fois le lecteur disponible, en testant via le pont sur le PC.

### 6.2 Backlog (demandes plus anciennes à traiter)
- **Facture** : tenir compte du **contrat lié** et des **entrées d'ingénierie** (désignation + métrage foré), le tout **« en un seul bloc »**.
- **SST / HSE** : module non fonctionnel → le **mettre sur le Portail**, partagé entre Mine et Forage.
- **Assignement des foreuses aux contrats** : instable → fiabiliser.

## 7. Divers utiles
- Comptes de service / clés : `X-Service-Key` (dans les settings de chaque app + `settings.SERVICE_API_KEY` du Portail). Ne pas committer de secrets.
- FCFA (XOF) partout pour les montants.
- Attribution des commits (convention de ces sessions) :
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

## 8. Automatiser le déploiement (pour Claude Code / CLI)

Claude Code peut **committer, pousser, ouvrir une PR et la fusionner** sans souci.
Pour le **déploiement**, Coolify n'a pas de « bouton » en CLI, mais 3 options :

### Option A — Auto-déploiement au push (recommandé)
Chaque push sur `main` redéploie automatiquement. À configurer **une fois par app** :
1. Dans Coolify : app → **Webhooks** → section **Manual Git Webhooks → GitHub**.
   - **Payload URL** (identique pour toutes les apps) : `http://37.60.243.107:8000/webhooks/source/github/events/manual`
   - **Secret** : le « GitHub Webhook Secret » affiché pour CETTE app (cliquer sur l'œil pour le révéler). Il est **propre à chaque app**.
2. Sur GitHub : dépôt → **Settings → Webhooks → Add webhook** :
   - Payload URL = l'URL ci-dessus
   - Content type = `application/json`
   - Secret = le secret de l'app
   - Events = **Just the push event**
3. Désormais `git push origin main` redéploie l'app. (GitHub doit pouvoir joindre `37.60.243.107:8000` — c'est public, donc OK.)

> Astuce : le bouton **« Webhook Configuration on GitHub »** dans Coolify ouvre la page GitHub pré-remplie.

### Option B — API de déploiement Coolify (déclenchement explicite)
Créer un **token API Coolify** (Coolify → Keys & Tokens / Security → API Tokens), puis :
```
curl "http://37.60.243.107:8000/api/v1/deploy?uuid=<APP_UUID>&force=false" \
     -H "Authorization: Bearer <COOLIFY_API_TOKEN>"
```
UUID des apps :
- Forage (gedrilling) : `c1bc2nr5yjnrzkv7f0o6iydk`
- Mine (gemining) : `b5pfvomd4fen3xg20w6k1md8`
- Portail (geportail) : `fqo7r7pdaoubpdague25hznq`

### Option C — Webhook de déploiement (auth requise)
L'app expose aussi une URL « Deploy Webhook (auth required) » (`/api/v1/deploy?uuid=...`),
à appeler avec le même token Bearer que l'option B.

### Conditions
- La machine qui exécute Claude Code (ou GitHub pour l'option A) doit pouvoir **joindre `37.60.243.107:8000`**. Sur ton PC/VPS : OK. Dans un bac à sable cloud restreint : peut être bloqué.
- **Ne jamais committer** les secrets (webhook secret, token API) dans le dépôt. Les garder en variable d'environnement / gestionnaire de secrets.
